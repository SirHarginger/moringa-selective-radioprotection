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

Execution (``workers``): replicates and truth sets are independent tasks, each seeded
only by (base seed, scenario, number), so results do not depend on the number of worker
processes or on the order in which tasks finish. Workers only compute; the parent
process alone writes checkpoints, atomically. ``workers`` is therefore not part of the
study manifest and may change between resumed sessions.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
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
from radiosensitivity_ml.parallel import check_workers, execute_tasks
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
    pilot_run_id: str

    def root(self, pilot: bool) -> Path:
        """Folder of the full run (``run_id``) or of the pilot (``pilot_run_id``)."""
        return self.output_dir / (self.pilot_run_id if pilot else self.run_id)


def study_from_mapping(data: Mapping[str, object]) -> StudyConfig:
    """Build a StudyConfig (strict keys). ``pilot_run_id`` defaults to ``<run_id>_pilot``."""
    allowed = {
        "schema_version", "run_id", "pilot_run_id", "experiment_config", "scenarios", "nsim",
        "n_truth", "truth_test_records", "repeats", "copula_components", "base_seed",
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
    run_id = str(data["run_id"])
    pilot_run_id = str(data.get("pilot_run_id") or f"{run_id}_pilot")
    if pilot_run_id == run_id:
        raise ValueError("pilot_run_id must differ from run_id")
    return StudyConfig(
        run_id=run_id,
        pilot_run_id=pilot_run_id,
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


def truth_set(
    scenario: gen.Scenario,
    number: int,
    study: StudyConfig,
    experiment: ExperimentConfig,
    inputs: ExperimentInputs,
    copula: gen.Copula,
    tissue_effects: Mapping[str, float],
    signal_map: gen.SignalMap,
) -> float:
    """One Monte Carlo truth draw: the procedures trained on ~(K-1)/K of the cohort.

    Seeded only by (base seed, scenario, number), so draws are independent tasks. Each
    fresh test record is its own component, so the plain mean of its errors is the
    component-weighted estimand.
    """
    table = inputs.population.table
    components = np.array(sorted(table["component_id"].unique()))
    n_train = round(len(components) * (experiment.k_outer - 1) / experiment.k_outer)
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
        (1.0 / sizes).to_numpy() if experiment.component_weighting else np.ones(len(train_table))
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
    return float(np.mean(errors["M1"] - errors["M2"]))


def aggregate_truth(values: list[float]) -> dict[str, float]:
    """Monte Carlo truth and its MCSE from the truth draws, in draw-number order."""
    mcse_truth = (
        float(np.std(values, ddof=1) / np.sqrt(len(values))) if len(values) > 1 else float("nan")
    )
    return {"truth": float(np.mean(values)), "truth_mcse": mcse_truth, "n_truth": len(values)}


def truth_value(
    scenario: gen.Scenario,
    study: StudyConfig,
    experiment: ExperimentConfig,
    inputs: ExperimentInputs,
    copula: gen.Copula,
    tissue_effects: Mapping[str, float],
    signal_map: gen.SignalMap,
) -> dict[str, float]:
    """Monte Carlo truth over ``study.n_truth`` draws, computed serially."""
    values = [
        truth_set(scenario, n, study, experiment, inputs, copula, tissue_effects, signal_map)
        for n in range(study.n_truth)
    ]
    return aggregate_truth(values)


def mcse(p: float, n: int) -> float:
    return float(np.sqrt(p * (1 - p) / n))


MAX_NONFINITE_SHARE = 0.01  # a method with more non-finite bounds is disqualified


def summarise(
    results: pd.DataFrame,
    truths: Mapping[str, Mapping[str, float]],
    null_names: set[str],
    shares: Mapping[str, Mapping[str, float]] | None = None,
) -> pd.DataFrame:
    """Operating characteristics per scenario and method.

    Also records the normalised variance shares of each scenario (logit scale), the
    number of non-finite bounds, and a truth-precision check: ``truth_mcse_flag`` is set
    when truth_mcse > 0.1 x the SD of the replicate estimates, in which case coverage at
    truth -/+ 2 truth_mcse is the reported sensitivity (the adoption rule is unchanged).
    A non-finite lower bound counts as non-coverage; see ``adopt`` for disqualification.
    """
    rows = []
    pairs = [(s, m) for s in results["scenario"].unique() for m in METHODS]
    for scenario, method in pairs:
        part = results[results["scenario"] == scenario]
        lower, upper = part[f"{method}_lower"], part[f"{method}_upper"]
        n = len(part)
        truth = float(truths[scenario]["truth"])
        truth_mcse = float(truths[scenario]["truth_mcse"])
        coverage = float((lower <= truth).mean())
        nonfinite = int((~np.isfinite(lower) | ~np.isfinite(upper)).sum())
        estimate_sd = float(part["estimate"].std(ddof=1))
        rows.append(
            {
                "scenario": scenario,
                "method": method,
                "n_replicates": n,
                **{f"share_{k}": v for k, v in (shares or {}).get(scenario, {}).items()},
                "truth": truth,
                "truth_mcse": truth_mcse,
                "truth_mcse_flag": bool(truth_mcse > 0.1 * estimate_sd),
                "coverage_at_truth_minus_2mcse": float((lower <= truth - 2 * truth_mcse).mean()),
                "coverage_at_truth_plus_2mcse": float((lower <= truth + 2 * truth_mcse).mean()),
                "n_nonfinite_bounds": nonfinite,
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
    A method with non-finite bounds in more than 1% of any scenario's replicates is
    disqualified.
    """
    coverage_floor = (1 - alpha) - 2 * mcse(1 - alpha, nsim)
    fpr_ceiling = alpha + 2 * mcse(alpha, nsim)
    qualifying = []
    for method, part in summary.groupby("method"):
        fpr = part["false_positive_rate"].dropna()
        finite_ok = True
        if "n_nonfinite_bounds" in part:
            share = part["n_nonfinite_bounds"] / part["n_replicates"]
            finite_ok = bool((share <= MAX_NONFINITE_SHARE).all())
        if (
            finite_ok
            and (part["one_sided_coverage"] >= coverage_floor).all()
            and (fpr <= fpr_ceiling).all()
        ):
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


# ------------------------------------------------------------------ task execution


@dataclass(frozen=True)
class SimulationContext:
    """Immutable inputs shared by every task (sent once to each worker process)."""

    study: StudyConfig
    experiment: ExperimentConfig
    inputs: ExperimentInputs
    copula: gen.Copula
    signal_map: gen.SignalMap
    scenarios: Mapping[str, gen.Scenario]
    tissue_effects: Mapping[str, Mapping[str, float]]


@dataclass(frozen=True)
class SimTask:
    """One independent unit of work: a truth draw or a replicate."""

    kind: str  # "truth" or "replicate"
    scenario: str
    number: int


def run_sim_task(context: SimulationContext, task: SimTask) -> object:
    """Compute one task (pure: depends only on the context and the task)."""
    scenario = context.scenarios[task.scenario]
    shared = (
        context.study, context.experiment, context.inputs, context.copula,
        context.tissue_effects[task.scenario], context.signal_map,
    )  # fmt: skip
    if task.kind == "replicate":
        return replicate(scenario, task.number, *shared)
    if task.kind == "truth":
        return truth_set(scenario, task.number, *shared)
    raise ValueError(f"unknown task kind {task.kind!r}")


# ------------------------------------------------------------------------- study


def replicate_path(root: Path, scenario: str, number: int) -> Path:
    return root / "replicates" / f"{scenario}_{number:04d}.json"


def run_study(
    study: StudyConfig,
    experiment: ExperimentConfig,
    inputs: ExperimentInputs,
    resume: bool,
    pilot: bool,
    log: Callable[[str], None] = print,
    workers: int = 1,
) -> Path:
    """Run (or resume) the study; returns the folder holding results and the decision.

    Phases: (1) verify every existing checkpoint; (2) compute the missing truth draws and
    replicates (``workers`` processes; the parent writes each replicate, and each truth
    once all its draws are in, atomically and write-once); (3) reload every checkpoint in
    scenario/replicate order and summarise. Interrupted truth draws are recomputed on
    resume (identical values, as every draw is seeded by its number).
    """
    check_workers(workers)
    root = study.root(pilot)
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
    context = SimulationContext(
        study, experiment, inputs, copula, signal_map,
        scenarios={s.name: s for s in study.scenarios},
        tissue_effects={
            s.name: gen.draw_tissue_effects(inputs.population.lineages, s, study.base_seed)
            for s in study.scenarios
        },
    )  # fmt: skip

    def truth_path(name: str) -> Path:
        return root / f"truth_{name}.json"

    def truth_identity(name: str) -> dict[str, object]:
        return {"scenario": name, "n_truth": n_truth, "base_seed": study.base_seed}

    def replicate_identity(scenario: gen.Scenario, number: int) -> dict[str, object]:
        seed = replicate_seed(study, scenario, number)
        return {"scenario": scenario.name, "replicate": number, "seed": seed}

    # (1) verify existing checkpoints before any computation; list the missing work
    tasks: list[SimTask] = []
    for scenario in study.scenarios:
        if truth_path(scenario.name).exists():
            load_checked(truth_path(scenario.name), truth_identity(scenario.name))
        else:
            tasks.extend(SimTask("truth", scenario.name, n) for n in range(n_truth))
        for number in range(n_rep):
            path = replicate_path(root, scenario.name, number)
            if path.exists():
                load_checked(path, replicate_identity(scenario, number))
            else:
                tasks.append(SimTask("replicate", scenario.name, number))

    # (2) compute; only this (parent) process writes
    seconds: dict[str, list[float]] = {"replicate": [], "truth_set": []}
    draws: dict[str, dict[int, float]] = {}
    draw_seconds: dict[str, list[float]] = {}
    n_replicate_tasks = sum(t.kind == "replicate" for t in tasks)

    def handle(task: SimTask, value: object, elapsed: float) -> None:
        if task.kind == "replicate":
            write_once_or_compare(
                replicate_path(root, task.scenario, task.number), json.dumps(value)
            )
            seconds["replicate"].append(elapsed)
            log(
                f"{task.scenario} replicate {task.number + 1}/{n_rep} ({elapsed:.0f}s; "
                f"{len(seconds['replicate'])}/{n_replicate_tasks} this session)"
            )
            return
        collected = draws.setdefault(task.scenario, {})
        collected[task.number] = float(value)  # type: ignore[arg-type]
        seconds["truth_set"].append(elapsed)
        draw_seconds.setdefault(task.scenario, []).append(elapsed)
        if len(collected) == n_truth:
            truth = aggregate_truth([collected[n] for n in range(n_truth)])
            record = {**truth, **truth_identity(task.scenario)}
            write_once_or_compare(truth_path(task.scenario), json.dumps(record, sort_keys=True))
            mean_set = float(np.mean(draw_seconds[task.scenario]))
            log(f"{task.scenario}: truth computed ({mean_set:.0f}s per truth set)")

    log(f"{len(tasks)} tasks to compute with {workers} worker(s)")
    started = time.monotonic()
    execute_tasks(tasks, run_sim_task, context, workers, handle)  # type: ignore[arg-type]
    wall_clock = time.monotonic() - started
    if tasks:  # a resume with nothing left to compute keeps the previous record
        write_runtime(root / "runtime.json", seconds, study, pilot, workers, wall_clock)

    # (3) reload every checkpoint in a fixed order (independent of completion order)
    truths: dict[str, dict[str, float]] = {
        s.name: load_checked(truth_path(s.name), truth_identity(s.name))  # type: ignore[misc]
        for s in study.scenarios
    }
    results = [
        load_checked(replicate_path(root, s.name, n), replicate_identity(s, n))
        for s in study.scenarios
        for n in range(n_rep)
    ]
    if pilot:
        # Runtime only (protocol §13 budget rule): no operating characteristics are
        # computed or written, so nothing about method performance can be inspected.
        decision = {
            "adopted_method": "PILOT ONLY - no decision",
            "note": "pilot runs measure runtime only; see runtime.json",
        }
        write_once_or_compare(root / "decision.json", json.dumps(decision, indent=2))
        return root
    table = pd.DataFrame(results)
    nulls = {s.name for s in study.scenarios if s.is_null}
    shares = {s.name: s.shares() for s in study.scenarios}
    summary = summarise(table, truths, nulls, shares)
    write_once_or_compare(root / "operating_characteristics.csv", summary.to_csv(index=False))
    decision = adopt(summary, study.nsim, experiment.alpha_one_sided, study.repeats)
    write_once_or_compare(root / "decision.json", json.dumps(decision, indent=2, sort_keys=True))
    return root


def write_runtime(
    path: Path,
    seconds: Mapping[str, list[float]],
    study: StudyConfig,
    pilot: bool,
    workers: int = 1,
    wall_clock_seconds: float | None = None,
) -> None:
    """Runtime record of the latest session that computed anything, for the §13 budget
    rule (timings of work finished in earlier sessions are not re-measured).

    Per-task means are seconds of ONE worker process per task (CPU-hour units).
    ``effective_parallelism`` = summed task seconds / wall-clock seconds; wall-clock
    cost = CPU-hour cost / effective_parallelism (wall-clock units, at these workers).
    """

    def mean(values: list[float]) -> float | None:
        return float(np.mean(values)) if values else None

    task_seconds = float(sum(seconds["replicate"]) + sum(seconds["truth_set"]))
    record = {
        "pilot": pilot,
        "n_scenarios": len(study.scenarios),
        "simulated_repeats": study.repeats,
        "seconds_per_replicate_mean": mean(seconds["replicate"]),
        "seconds_per_truth_set_mean": mean(seconds["truth_set"]),
        "n_replicates_timed": len(seconds["replicate"]),
        "n_truth_sets_timed": len(seconds["truth_set"]),
        "workers": workers,
        "logical_cores": os.cpu_count(),
        "wall_clock_seconds": wall_clock_seconds,
        "task_seconds_total": task_seconds,
        "effective_parallelism": (
            task_seconds / wall_clock_seconds if wall_clock_seconds and task_seconds else None
        ),
        "environment": ck.environment_record(),
    }
    ck.atomic_write_text(path, json.dumps(record, indent=2, sort_keys=True))
