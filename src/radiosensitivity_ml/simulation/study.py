"""Coverage study for the interval candidates (protocol §13; ADEMP), investigator-run.

For each scenario:
- truth: the expected component-weighted paired dMAE of the procedures M2 vs M1
  trained on ~(K-1)/K of a cohort with the real structure, estimated by Monte Carlo
  over ``n_truth`` fresh training sets, each scored on a large fresh test set whose
  rows are real (lineage, primary_disease) pairs drawn with probability 1/|component|;
  its Monte Carlo SE is recorded;
- replicates: a fresh synthetic dataset with the REAL tissue/component structure, the
  exact nested-CV pipeline, and every candidate interval.
Performance per method: one-sided lower-bound coverage, false-positive rate (null
scenario: LB > 0), mean width, bias, Monte Carlo SEs. Adoption follows the frozen rule
in ``adopt``. Each replicate and truth is checkpointed (write-once JSON whose seed and
scenario are verified on reuse), so ``--resume`` skips finished work after checking that
the study manifest is unchanged.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

from radiosensitivity_ml.config import ExperimentConfig, config_sha256
from radiosensitivity_ml.evaluation import intervals as iv
from radiosensitivity_ml.evaluation import metrics as mt
from radiosensitivity_ml.evaluation import splits as sp
from radiosensitivity_ml.models import checkpoints as ck
from radiosensitivity_ml.models.registry import build_model
from radiosensitivity_ml.models.run import ExperimentInputs, code_sha256, tune_and_fit
from radiosensitivity_ml.simulation import generator as gen

METHODS = ("nadeau_bengio", "naive_component_t")  # candidates; bootstrap is descriptive


@dataclass(frozen=True)
class StudyConfig:
    """Validated simulation settings (configs/simulation.yaml)."""

    run_id: str
    scenarios: tuple[gen.Scenario, ...]
    nsim: int
    n_truth: int
    truth_test_records: int
    repeats: int
    copula_components: int
    base_seed: int
    pilot_replicates: int
    output_dir: Path
    raw: Mapping[str, object]


def study_from_mapping(data: Mapping[str, object]) -> StudyConfig:
    """Build a StudyConfig (strict keys)."""
    allowed = {
        "schema_version", "run_id", "experiment_config", "scenarios", "nsim", "n_truth",
        "truth_test_records", "repeats", "copula_components", "base_seed",
        "pilot_replicates", "adoption_rule", "output_dir",
    }  # fmt: skip
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"unknown simulation keys: {sorted(unknown)}")
    scenarios = tuple(gen.Scenario(**s) for s in data["scenarios"])  # type: ignore[union-attr]
    if not any(s.is_null for s in scenarios):
        raise ValueError("at least one null scenario (effect_k: 0) is required")
    names = [s.name for s in scenarios]
    if len(set(names)) != len(names):
        raise ValueError("scenario names must be unique")
    return StudyConfig(
        run_id=str(data["run_id"]),
        scenarios=scenarios,
        nsim=int(data["nsim"]),  # type: ignore[arg-type]
        n_truth=int(data["n_truth"]),  # type: ignore[arg-type]
        truth_test_records=int(data["truth_test_records"]),  # type: ignore[arg-type]
        repeats=int(data["repeats"]),  # type: ignore[arg-type]
        copula_components=int(data["copula_components"]),  # type: ignore[arg-type]
        base_seed=int(data["base_seed"]),  # type: ignore[arg-type]
        pilot_replicates=int(data["pilot_replicates"]),  # type: ignore[arg-type]
        output_dir=Path(str(data.get("output_dir", "results/simulation"))),
        raw=dict(data),
    )


def cv_predictions(
    experiment: ExperimentConfig,
    inputs: ExperimentInputs,
    features: pd.DataFrame,
    y: pd.Series,
    splits: pd.DataFrame,
    models: tuple[str, ...] = ("M1", "M2"),
) -> pd.DataFrame:
    """Out-of-fold predictions with the exact protocol pipeline (tuning inside folds)."""
    table = inputs.population.table
    weights = inputs.population.component_weights()
    rows = []
    for (repeat, fold), part in splits.groupby(["repeat", "outer_fold"]):
        train = part[part["role"] == "train"]
        test_rows = part.loc[part["role"] == "test", "row_number"].to_numpy()
        train_rows = train["row_number"].to_numpy()
        for model_id in models:
            seed = ck.stable_int(experiment.base_seed, "sim", model_id, repeat, fold)
            model = build_model(model_id, inputs.population.lineages, inputs.gene_sets, seed)
            fitted, _, _ = tune_and_fit(
                model,
                experiment.grids[model_id],
                features.loc[train_rows],
                y.loc[train_rows].to_numpy(),
                weights.loc[train_rows].to_numpy(),
                train["inner_fold"].to_numpy(),
                clip=experiment.clip_raw_predictions,
            )
            rows.append(
                pd.DataFrame(
                    {
                        "row_number": test_rows,
                        "depmap_id": table.loc[test_rows, "depmap_id"].to_numpy(),
                        "component_id": table.loc[test_rows, "component_id"].to_numpy(),
                        "lineage": table.loc[test_rows, "lineage"].to_numpy(),
                        "scale": "raw",
                        "model_id": model_id,
                        "variant": "real",
                        "repeat": repeat,
                        "outer_fold": fold,
                        "y_true": y.loc[test_rows].to_numpy(),
                        "y_pred": fitted.predict(features.loc[test_rows]),
                    }
                )
            )
    return pd.concat(rows, ignore_index=True)


def synthetic_features(
    copula: gen.Copula, meta: pd.DataFrame, rng: np.random.Generator
) -> pd.DataFrame:
    """Synthetic lineage-conditional expression for rows with real lineage labels."""
    expression = gen.sample_expression(copula, list(meta["lineage"]), rng)
    expression.index = meta.index
    return pd.concat([meta[["lineage", "primary_disease"]], expression], axis=1)


def reference_signal_map(
    study: StudyConfig, inputs: ExperimentInputs, copula: gen.Copula, direction: np.ndarray
) -> gen.SignalMap:
    """Signal map fitted once on a large reference synthetic sample of the real mix."""
    rng = np.random.default_rng(ck.stable_int(study.base_seed, "signal_reference"))
    meta = sample_metadata(inputs, study.truth_test_records, rng)
    reference = synthetic_features(copula, meta, rng).drop(columns=["lineage", "primary_disease"])
    return gen.fit_signal_map(reference, inputs.gene_sets, direction)


def replicate_seed(study: StudyConfig, scenario: gen.Scenario, number: int) -> int:
    return ck.stable_int(study.base_seed, scenario.name, number)


def sample_metadata(inputs: ExperimentInputs, n: int, rng: np.random.Generator) -> pd.DataFrame:
    """n real (lineage, primary_disease) pairs, drawn with probability 1/|component|."""
    table = inputs.population.table
    weights = inputs.population.component_weights().to_numpy()
    rows = rng.choice(len(table), size=n, p=weights / weights.sum())
    meta = table.iloc[rows][["lineage", "primary_disease"]].reset_index(drop=True)
    meta.index = pd.RangeIndex(n)
    return meta


def replicate(
    scenario: gen.Scenario,
    number: int,
    study: StudyConfig,
    experiment: ExperimentConfig,
    inputs: ExperimentInputs,
    copula: gen.Copula,
    tissue_effects: Mapping[str, float],
    signal_map: gen.SignalMap,
) -> dict[str, object]:
    """One synthetic dataset analysed exactly like the real one."""
    seed = replicate_seed(study, scenario, number)
    rng = np.random.default_rng(seed)
    table = inputs.population.table
    features = synthetic_features(copula, table, rng)
    genes = features.drop(columns=["lineage", "primary_disease"])
    y = pd.Series(
        gen.simulate_outcome(
            genes, table["lineage"], table["component_id"], scenario, signal_map,
            tissue_effects, rng,
        ),
        index=table.index,
    )  # fmt: skip
    splits = sp.make_splits(table, experiment.k_outer, experiment.k_inner, study.repeats, seed)
    predictions = mt.prepare(
        cv_predictions(experiment, inputs, features, y, splits), experiment.clip_raw_predictions
    )
    summary = mt.delta_mae(mt.paired_differences(predictions, "M2", "M1", "raw"))
    result: dict[str, object] = {
        "scenario": scenario.name,
        "replicate": number,
        "seed": seed,
        "estimate": summary["estimate"],
        "sd_between_repeats": float(summary["per_repeat"].std(ddof=1)),  # type: ignore[union-attr]
    }
    for interval in iv.candidate_intervals(summary, experiment.alpha_one_sided, seed):
        result[f"{interval.method}_lower"] = interval.lower
        result[f"{interval.method}_upper"] = interval.upper
    return result


def truth_value(
    scenario: gen.Scenario,
    study: StudyConfig,
    experiment: ExperimentConfig,
    inputs: ExperimentInputs,
    copula: gen.Copula,
    tissue_effects: Mapping[str, float],
    signal_map: gen.SignalMap,
) -> dict[str, float]:
    """Monte Carlo truth and its MCSE: procedures trained on ~(K-1)/K of the cohort.

    Each fresh test record is its own component, so the plain mean of its errors is the
    component-weighted estimand.
    """
    table = inputs.population.table
    components = np.array(sorted(table["component_id"].unique()))
    n_train = round(len(components) * (experiment.k_outer - 1) / experiment.k_outer)
    values = []
    for number in range(study.n_truth):
        rng = np.random.default_rng(ck.stable_int(study.base_seed, "truth", scenario.name, number))
        keep = rng.choice(components, size=n_train, replace=False)
        train_table = table[table["component_id"].isin(keep)]
        features = synthetic_features(copula, train_table, rng)
        y = gen.simulate_outcome(
            features.drop(columns=["lineage", "primary_disease"]), train_table["lineage"],
            train_table["component_id"], scenario, signal_map, tissue_effects, rng,
        )  # fmt: skip
        sizes = train_table.groupby("component_id")["depmap_id"].transform("size")
        weights = (
            (1.0 / sizes).to_numpy()
            if experiment.component_weighting
            else np.ones(len(train_table))
        )
        inner = sp.make_splits(train_table, experiment.k_inner, 2, 1, int(rng.integers(1 << 30)))
        inner_fold = (
            inner[inner["role"] == "test"]
            .set_index("row_number")
            .loc[train_table.index, "outer_fold"]
            .to_numpy()
        )
        test_meta = sample_metadata(inputs, study.truth_test_records, rng)
        test_features = synthetic_features(copula, test_meta, rng)
        y_test = gen.simulate_outcome(
            test_features.drop(columns=["lineage", "primary_disease"]), test_meta["lineage"],
            [f"t{i}" for i in test_meta.index], scenario, signal_map, tissue_effects, rng,
        )  # fmt: skip
        errors = {}
        for model_id in ("M1", "M2"):
            seed = ck.stable_int(study.base_seed, "truth_model", scenario.name, number, model_id)
            model = build_model(model_id, inputs.population.lineages, inputs.gene_sets, seed)
            fitted, _, _ = tune_and_fit(
                model, experiment.grids[model_id], features, y, weights, inner_fold,
                clip=experiment.clip_raw_predictions,
            )  # fmt: skip
            pred = fitted.predict(test_features)
            if experiment.clip_raw_predictions:
                pred = np.clip(pred, 0, 1)
            errors[model_id] = np.abs(y_test - pred)
        values.append(float(np.mean(errors["M1"] - errors["M2"])))
    mcse_truth = (
        float(np.std(values, ddof=1) / np.sqrt(len(values))) if len(values) > 1 else float("nan")
    )
    return {"truth": float(np.mean(values)), "truth_mcse": mcse_truth, "n_truth": len(values)}


def mcse(p: float, n: int) -> float:
    return float(np.sqrt(p * (1 - p) / n))


def summarise(
    results: pd.DataFrame, truths: Mapping[str, Mapping[str, float]], null_names: set[str]
) -> pd.DataFrame:
    """Operating characteristics per scenario and method."""
    rows = []
    pairs = [(s, m) for s in results["scenario"].unique() for m in METHODS]
    for scenario, method in pairs:
        part = results[results["scenario"] == scenario]
        lower, upper = part[f"{method}_lower"], part[f"{method}_upper"]
        n = len(part)
        truth = float(truths[scenario]["truth"])
        coverage = float((lower <= truth).mean())
        rows.append(
            {
                "scenario": scenario,
                "method": method,
                "n_replicates": n,
                "truth": truth,
                "truth_mcse": float(truths[scenario]["truth_mcse"]),
                "one_sided_coverage": coverage,
                "coverage_mcse": mcse(coverage, n),
                "false_positive_rate": float((lower > 0).mean())
                if scenario in null_names
                else np.nan,
                "mean_width": float((upper - lower).mean()),
                "bias": float(part["estimate"].mean() - truth),
                "mean_sd_between_repeats": float(part["sd_between_repeats"].mean()),
            }
        )
    return pd.DataFrame(rows)


def adopt(
    summary: pd.DataFrame,
    nsim: int,
    alpha: float,
    simulated_repeats: int,
    repeats_options: tuple[int, ...] = (10, 20, 50),
) -> dict[str, object]:
    """Frozen adoption rule (protocol §13):

    qualify if, in every scenario, coverage >= (1 - alpha) - 2*MCSE(1 - alpha, nsim) and,
    in null scenarios, false-positive rate <= alpha + 2*MCSE(alpha, nsim); adopt the
    qualifier with the smallest mean width; none -> "not_assessable". R: smallest option
    with max mean SD between repeats / sqrt(R) <= 10% of the adopted mean half-width. If
    no option meets it, ``repeats`` is None and ``repeats_status`` is "R_rule_not_met"
    (an investigator decision, never a silent default). Coverage was simulated at
    ``simulated_repeats``; if the adopted R differs, ``recheck_required`` is True.
    """
    coverage_floor = (1 - alpha) - 2 * mcse(1 - alpha, nsim)
    fpr_ceiling = alpha + 2 * mcse(alpha, nsim)
    qualifying = []
    for method, part in summary.groupby("method"):
        fpr = part["false_positive_rate"].dropna()
        if (part["one_sided_coverage"] >= coverage_floor).all() and (fpr <= fpr_ceiling).all():
            qualifying.append((float(part["mean_width"].mean()), method))
    base = {
        "coverage_floor": coverage_floor,
        "fpr_ceiling": fpr_ceiling,
        "simulated_repeats": simulated_repeats,
    }
    if not qualifying:
        return {"adopted_method": "not_assessable", **base}
    width, method = min(qualifying)
    sd = float(summary.loc[summary["method"] == method, "mean_sd_between_repeats"].max())
    repeats = next((r for r in repeats_options if sd / np.sqrt(r) <= 0.1 * width / 2), None)
    return {
        "adopted_method": method,
        "repeats": None if repeats is None else int(repeats),
        "repeats_status": "R_rule_not_met" if repeats is None else "R_rule_met",
        "recheck_required": repeats is None or int(repeats) != simulated_repeats,
        "qualifying_methods": [m for _, m in sorted(qualifying)],
        **base,
    }


def load_checked(path: Path, expected: Mapping[str, object]) -> dict[str, object]:
    """A stored checkpoint JSON whose identifying fields must equal ``expected``."""
    stored = json.loads(path.read_text(encoding="utf-8"))
    wrong = [k for k, v in expected.items() if stored.get(k) != v]
    if wrong:
        raise ck.CheckpointError(f"{path}: {wrong} differ from this study; start a new run_id")
    return stored


def write_once_or_compare(path: Path, text: str) -> None:
    """Write a result file once; on a later run it must be byte-identical."""
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise ck.CheckpointError(
                f"{path} exists with different content; it is never overwritten"
            )
        return
    ck.atomic_write_text(path, text)


def run_study(
    study: StudyConfig,
    experiment: ExperimentConfig,
    inputs: ExperimentInputs,
    resume: bool,
    pilot: bool,
    log: Callable[[str], None] = print,
) -> Path:
    """Run (or resume) the study; returns the folder holding results and the decision."""
    root = study.output_dir / (study.run_id + ("_pilot" if pilot else ""))
    manifest = {
        "study_config_sha256": config_sha256(study.raw),
        "experiment_config_sha256": experiment.sha256,
        "code_sha256": code_sha256(),
        "inputs_sha256": inputs.inputs_sha256,
        "environment": ck.environment_record(),
        "pilot": pilot,
    }
    manifest_path = root / "study_manifest.json"
    if root.exists() and not resume:
        raise ck.CheckpointError(f"{root} exists; use --resume or a new run_id")
    if resume:
        stored = json.loads(manifest_path.read_text(encoding="utf-8"))
        differences = [k for k in manifest if stored.get(k) != manifest[k]]
        if differences:
            raise ck.CheckpointError(f"incompatible study checkpoint: {differences} changed")
    else:
        (root / "replicates").mkdir(parents=True)
        ck.atomic_write_text(manifest_path, json.dumps(manifest, indent=2, sort_keys=True))
    genes = sorted({g for members in inputs.gene_sets.values() for g in members})
    copula = gen.fit_copula(
        inputs.features[genes], inputs.population.table["lineage"], study.copula_components
    )
    direction = gen.expression_direction(len(inputs.gene_sets), study.base_seed)
    signal_map = reference_signal_map(study, inputs, copula, direction)
    n_rep = study.pilot_replicates if pilot else study.nsim
    n_truth = 2 if pilot else study.n_truth
    truth_study = replace(study, n_truth=n_truth)
    truths: dict[str, dict[str, float]] = {}
    results = []
    for scenario in study.scenarios:
        effects = gen.draw_tissue_effects(inputs.population.lineages, scenario, study.base_seed)
        truth_path = root / f"truth_{scenario.name}.json"
        identity = {"scenario": scenario.name, "n_truth": n_truth, "base_seed": study.base_seed}
        if truth_path.exists():
            truths[scenario.name] = load_checked(truth_path, identity)  # type: ignore[assignment]
        else:
            started = time.monotonic()
            truth = truth_value(
                scenario, truth_study, experiment, inputs, copula, effects, signal_map
            )
            truths[scenario.name] = {**truth, **identity}  # type: ignore[dict-item]
            ck.atomic_write_text(truth_path, json.dumps(truths[scenario.name], sort_keys=True))
            log(
                f"{scenario.name}: truth {truth['truth']:.5f} (MCSE {truth['truth_mcse']:.5f}; "
                f"{time.monotonic() - started:.0f}s)"
            )
        for number in range(n_rep):
            path = root / "replicates" / f"{scenario.name}_{number:04d}.json"
            seed = replicate_seed(study, scenario, number)
            if path.exists():
                results.append(
                    load_checked(
                        path, {"scenario": scenario.name, "replicate": number, "seed": seed}
                    )
                )
                continue
            started = time.monotonic()
            result = replicate(
                scenario, number, study, experiment, inputs, copula, effects, signal_map
            )
            ck.atomic_write_text(path, json.dumps(result))
            results.append(result)
            log(
                f"{scenario.name} replicate {number + 1}/{n_rep} ({time.monotonic() - started:.0f}s)"
            )
    table = pd.DataFrame(results)
    nulls = {s.name for s in study.scenarios if s.is_null}
    summary = summarise(table, truths, nulls)
    write_once_or_compare(root / "operating_characteristics.csv", summary.to_csv(index=False))
    decision = (
        {"adopted_method": "PILOT ONLY - no decision", "note": "pilot runs measure runtime only"}
        if pilot
        else adopt(summary, study.nsim, experiment.alpha_one_sided, study.repeats)
    )
    write_once_or_compare(root / "decision.json", json.dumps(decision, indent=2, sort_keys=True))
    return root
