"""Unit tests for the Phase 03 pipeline building blocks (no model fitting unless marked).

SYNTHETIC SOFTWARE-TEST DATA ONLY: every table, identifier, expression value and outcome
below is invented to exercise the code. Nothing here is a scientific observation and
nothing may appear in a manuscript.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from radiosensitivity_ml.config import ExperimentConfigError, experiment_from_mapping
from radiosensitivity_ml.data import analysis_table as at
from radiosensitivity_ml.evaluation import intervals as iv
from radiosensitivity_ml.evaluation import metrics as mt
from radiosensitivity_ml.evaluation import splits as sp
from radiosensitivity_ml.evaluation.report import verdict
from radiosensitivity_ml.explainability import stability as st
from radiosensitivity_ml.features.gene_sets import GeneSetScorer, random_gene_set_collection
from radiosensitivity_ml.models import checkpoints as ck
from radiosensitivity_ml.models.baselines import TissueRidge, one_hot
from radiosensitivity_ml.models.run import check_scale_rows, control_seed, permuted_within_tissue
from radiosensitivity_ml.simulation import generator as gen
from radiosensitivity_ml.simulation.study import adopt, load_checked, write_once_or_compare


def synthetic_population(n_components: int = 30, seed: int = 0) -> pd.DataFrame:
    """SYNTHETIC population: 4 lineages, a few two-record components."""
    rng = np.random.default_rng(seed)
    rows = []
    row = 2
    for c in range(n_components):
        lineage = ["L_A", "L_B", "L_C", "L_D"][c % 4]
        for _ in range(2 if c % 7 == 0 else 1):
            rows.append(
                {
                    "row_number": row,
                    "depmap_id": f"ACH-9{row:05d}",
                    "component_id": f"G:{c:03d}",
                    "lineage": lineage,
                    "primary_disease": f"{lineage}_d{int(rng.integers(2))}",
                }
            )
            row += 1
    table = pd.DataFrame(rows).set_index("row_number")
    table["stratum"] = at.stratum_labels(table, 5)
    return table


# ------------------------------------------------------------------- splits


def test_splits_never_split_a_component_and_are_deterministic() -> None:
    population = synthetic_population()
    first = sp.make_splits(population, k_outer=3, k_inner=2, repeats=2, seed=7)
    second = sp.make_splits(population, k_outer=3, k_inner=2, repeats=2, seed=7)
    pd.testing.assert_frame_equal(first, second)
    sp.check_splits(first, population)  # raises if a component is split
    other = sp.make_splits(population, k_outer=3, k_inner=2, repeats=2, seed=8)
    assert not first.equals(other)


def test_split_function_takes_no_outcome() -> None:
    assert sp.split_function_takes_no_outcome()


def test_check_splits_detects_a_split_component() -> None:
    population = synthetic_population()
    table = sp.make_splits(population, 3, 2, 1, 1)
    pair = population[population.duplicated("component_id", keep=False)].index[:2]
    bad = table.copy()
    mask = (bad["row_number"] == pair[0]) & (bad["outer_fold"] == 0)
    bad.loc[mask, "role"] = "train" if bad.loc[mask, "role"].iloc[0] == "test" else "test"
    bad.loc[mask & (bad["role"] == "train"), "inner_fold"] = 0
    with pytest.raises(sp.SplitError):
        sp.check_splits(bad, population)


def test_loto_never_trains_on_the_held_out_lineage() -> None:
    population = synthetic_population()
    table = sp.loto_splits(population, ["L_A", "L_B"], k_inner=2, seed=0)
    for fold, lineage in enumerate(["L_A", "L_B"]):
        part = table[table["outer_fold"] == fold]
        train_lineages = population.loc[part.loc[part["role"] == "train", "row_number"], "lineage"]
        assert lineage not in set(train_lineages)


def test_extend_splits_keeps_primary_assignments() -> None:
    population = synthetic_population()
    primary = population.iloc[:-4]
    added = population.iloc[-4:]
    base = sp.make_splits(primary, 3, 2, 2, 3)
    extended = sp.extend_splits(base, added, 3, 2, 3)
    merged = extended.merge(base, on=["repeat", "outer_fold", "row_number"], suffixes=("", "_base"))
    assert (merged["role"] == merged["role_base"]).all()
    sp.check_splits(extended.reset_index(drop=True), population)


def test_extend_splits_keeps_added_relatives_with_their_component() -> None:
    population = synthetic_population()
    pair_component = population[population.duplicated("component_id", keep=False)][
        "component_id"
    ].iloc[0]
    pair_rows = list(population.index[population["component_id"] == pair_component])
    primary = population.drop(index=pair_rows[1])  # one member is primary, the other is added
    added = population.loc[[pair_rows[1]]]
    base = sp.make_splits(primary, 3, 2, 2, 3)
    lookup = {pair_component: pair_rows[0]}
    extended = sp.extend_splits(base, added, 3, 2, 3, primary_component_rows=lookup)
    sp.check_splits(extended.reset_index(drop=True), population)  # pair never split


# -------------------------------------------------------------- features


def test_gene_set_scorer_learns_only_from_training_rows() -> None:
    rng = np.random.default_rng(1)
    genes = [f"G{i}" for i in range(12)]
    train = pd.DataFrame(rng.normal(size=(10, 12)), columns=genes)
    test = pd.DataFrame(rng.normal(size=(5, 12)), columns=genes)
    sets = {"SET1": genes[:6], "SET2": genes[6:]}
    scorer = GeneSetScorer(sets).fit(train)
    before = scorer.mean_.copy()
    scorer.transform(test * 100)  # transforming test rows never changes learned state
    pd.testing.assert_series_equal(before, scorer.mean_)
    refit = GeneSetScorer(sets).fit(pd.concat([train, test * 100]))
    assert not np.allclose(refit.mean_, before)


def test_random_gene_sets_are_size_matched_and_seeded() -> None:
    rng = np.random.default_rng(2)
    expression = pd.DataFrame(rng.normal(size=(8, 40)), columns=[f"G{i}" for i in range(40)])
    sets = {"SET1": [f"G{i}" for i in range(5)], "SET2": [f"G{i}" for i in range(5, 12)]}
    first = random_gene_set_collection(sets, expression, seed=3)
    assert [len(v) for v in first.values()] == [5, 7]
    assert first == random_gene_set_collection(sets, expression, seed=3)


def test_one_hot_unknown_category_is_all_zero_and_unscaled() -> None:
    values = pd.Series(["L_A", "L_B", "L_UNSEEN"])
    frame = one_hot(values, ["L_A", "L_B"], "lineage")
    assert frame.loc[2].sum() == 0
    assert set(np.unique(frame.to_numpy())) <= {0.0, 1.0}


@pytest.mark.model_fit
def test_unseen_lineage_falls_back_to_intercept() -> None:
    X = pd.DataFrame({"lineage": ["L_A"] * 4 + ["L_B"] * 4})
    y = np.array([0.2, 0.25, 0.22, 0.21, 0.6, 0.62, 0.58, 0.61])
    model = TissueRidge(lineages=("L_A", "L_B", "L_C"), alpha=1.0).fit(X, y)
    assert "lineage=L_C" in model.unseen_
    pred = model.predict(pd.DataFrame({"lineage": ["L_C"]}))
    assert pred[0] == pytest.approx(model.ridge_.intercept_)


# ---------------------------------------------------------------- outcome


def test_transforms_drop_only_undefined_boundaries_and_never_clip() -> None:
    y = pd.Series([0.0, 0.3, 1.0, 0.7])
    raw, dropped = at.transform_outcome(y, "raw")
    assert dropped == 0 and list(raw) == [0.0, 0.3, 1.0, 0.7]
    neglog, dropped = at.transform_outcome(y, "neglog")
    assert dropped == 1 and len(neglog) == 3
    logit, dropped = at.transform_outcome(y, "logit")
    assert dropped == 2 and len(logit) == 2


def test_stratum_pools_only_small_lineages() -> None:
    population = synthetic_population(n_components=30)
    counts = population.groupby("lineage")["component_id"].nunique()
    labels = at.stratum_labels(population, min_components=8)
    for lineage, n in counts.items():
        expected = lineage if n >= 8 else at.STRATUM_POOLED
        assert set(labels[population["lineage"] == lineage]) == {expected}


# ---------------------------------------------------------------- metrics


def toy_predictions() -> pd.DataFrame:
    """SYNTHETIC predictions: component G1 has two records, G2 one; two repeats."""
    rows = []
    for repeat in (0, 1):
        for row, comp, y, a, b in (
            (2, "G1", 0.5, 0.4, 0.2),
            (3, "G1", 0.5, 0.5, 0.5),
            (4, "G2", 0.3, 0.3, 0.6),
        ):
            for model, pred in (("M2", a), ("M1", b)):
                rows.append(
                    {
                        "row_number": row, "depmap_id": f"X{row}", "component_id": comp,
                        "lineage": "L", "scale": "raw", "model_id": model, "variant": "real",
                        "repeat": repeat, "outer_fold": 0, "y_true": y, "y_pred": pred,
                    }
                )  # fmt: skip
    return pd.DataFrame(rows)


def test_component_weighted_delta_mae_matches_hand_calculation() -> None:
    diffs = mt.paired_differences(toy_predictions(), "M2", "M1", "raw")
    summary = mt.delta_mae(diffs)
    # record d: row2 = |0.5-0.2| - |0.5-0.4| = 0.2; row3 = 0; row4 = 0.3 - 0 = 0.3
    # component: G1 = mean(0.2, 0) = 0.1; G2 = 0.3 -> component-weighted = 0.2
    assert summary["estimate"] == pytest.approx(0.2)
    assert summary["record_weighted_estimate"] == pytest.approx(0.5 / 3)
    assert summary["n_components"] == 2 and summary["repeats"] == 2


def test_paired_differences_require_identical_records() -> None:
    predictions = toy_predictions()
    broken = predictions.drop(predictions.index[(predictions["model_id"] == "M1")][:1])
    with pytest.raises(ValueError):
        mt.paired_differences(broken, "M2", "M1", "raw")


def test_prediction_clip_rule_applies_to_raw_scale_only() -> None:
    predictions = toy_predictions().assign(y_pred=1.4)
    predictions.loc[0, "scale"] = "logit"
    clipped = mt.prepare(predictions, clip_raw=True)
    assert clipped.loc[0, "y_pred"] == 1.4
    assert (clipped.loc[1:, "y_pred"] == 1.0).all()


# --------------------------------------------------------------- intervals


def test_nadeau_bengio_formula() -> None:
    values = np.array([0.01, 0.03, -0.01, 0.02, 0.00])
    interval = iv.nadeau_bengio(0.01, values, n_train=4.0, n_test=1.0, alpha=0.05)
    from scipy import stats

    half = stats.t.ppf(0.95, 4) * np.sqrt((1 / 5 + 1 / 4) * values.var(ddof=1))
    assert interval.lower == pytest.approx(0.01 - half)
    assert interval.upper == pytest.approx(0.01 + half)


def test_bootstrap_is_deterministic_and_descriptive() -> None:
    values = np.linspace(-0.1, 0.2, 20)
    assert iv.component_bootstrap(values, seed=1) == iv.component_bootstrap(values, seed=1)
    assert iv.component_bootstrap(values).method == "component_bootstrap"


# ------------------------------------------------------------------ config


def minimal_config(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "schema_version": 1,
        "run_id": "SYNTHETIC",
        "inputs": {
            "qc_dir": "q",
            "qc_sha256": {},
            "clarifi": "c",
            "clarifi_manifest": "m",
            "expression": "e",
            "gene_sets": "g",
            "gene_sets_sha256": None,
        },
        "population": "primary",
        "scales": ["raw"],
        "models": ["M1"],
        "grids": {"M1": {"alpha": [1.0]}},
        "validation": {"k_outer": 5, "k_inner": 5, "repeats": 2},
        "seeds": {"base_seed": 1},
        "fit": {"component_weighting": True},
        "predictions": {"clip_raw_to_unit_interval": True},
        "inference": {"method": "not_assessable", "alpha_one_sided": 0.05},
    }
    data.update(overrides)
    return data


def test_config_accepts_valid_and_rejects_invalid() -> None:
    config = experiment_from_mapping(minimal_config())
    assert config.k_outer == 5 and len(config.sha256) == 64
    bad_cases = [
        minimal_config(typo_key=1),
        minimal_config(scales=["linear"]),
        minimal_config(models=["M9"]),
        minimal_config(models=["M1", "M2"]),  # missing grid for M2
        minimal_config(validation={"k_outer": 1, "k_inner": 5, "repeats": 2}),
        minimal_config(inference={"method": "bates"}),
        minimal_config(inference={"method": "nadeau_bengio"}),  # adopted method needs decision file
        minimal_config(inference={"method": "not_assessable", "decision_file": "d.json"}),  # no sha
        minimal_config(inference={"method": "not_assessable", "bh_q": 0.0}),
        minimal_config(inference={"method": "not_assessable", "typo": 1}),
        minimal_config(controls={"permuted_outcome": 10}),  # controls need an M2 grid
    ]
    for case in bad_cases:
        with pytest.raises(ExperimentConfigError):
            experiment_from_mapping(case)


# ------------------------------------------------------------ checkpoints


def test_task_seed_does_not_depend_on_the_key() -> None:
    a = ck.make_task("context-1", 5, "raw", "M2", 0, 1)
    b = ck.make_task("context-2", 5, "raw", "M2", 0, 1)
    assert a.seed == b.seed and a.key != b.key
    assert ck.make_task("context-1", 5, "raw", "M2", 0, 1) == a


def write_toy_task(store: ck.RunStore, task: ck.Task) -> pd.DataFrame:
    predictions = toy_predictions().iloc[:2][list(ck.PREDICTION_COLUMNS)]
    store.write_task(task, predictions, {"synthetic": True}, {"note": "SYNTHETIC"})
    return predictions


def test_task_checkpoints_are_atomic_verified_and_never_overwritten(tmp_path: Path) -> None:
    store = ck.RunStore(tmp_path / "run")
    store.create({"run_id": "SYNTHETIC"})
    task = ck.make_task("ctx", 1, "raw", "M2", 0, 0)
    predictions = write_toy_task(store, task)
    rows = set(predictions["row_number"])
    assert store.is_complete(task, rows)
    assert not store.is_complete(task, rows | {99})  # wrong row set
    with pytest.raises(ck.CheckpointError):
        write_toy_task(store, task)
    (store.task_dir(task) / "predictions.parquet").write_bytes(b"corrupted")
    assert not store.is_complete(task, rows)
    moved = store.reject(task)
    assert moved.exists() and not store.task_dir(task).exists()


def test_prediction_schema_is_enforced(tmp_path: Path) -> None:
    store = ck.RunStore(tmp_path / "run")
    store.create({"run_id": "SYNTHETIC"})
    task = ck.make_task("ctx", 1, "raw", "M2", 0, 0)
    with pytest.raises(ck.CheckpointError):
        store.write_task(task, pd.DataFrame({"row_number": [1]}), {}, {})


def test_run_folder_is_never_reused_without_resume(tmp_path: Path) -> None:
    store = ck.RunStore(tmp_path / "run")
    store.create({"run_id": "SYNTHETIC", "config_sha256": "a"})
    with pytest.raises(ck.CheckpointError):
        store.create({"run_id": "SYNTHETIC"})
    assert store.incompatibilities({"config_sha256": "b"}) == ["config_sha256"]


def test_partial_task_folders_are_discarded(tmp_path: Path) -> None:
    store = ck.RunStore(tmp_path / "run")
    store.create({"run_id": "SYNTHETIC"})
    (store.tasks_dir / "abc.partial").mkdir()
    assert store.discard_partials() == 1


def test_split_table_is_verified_not_regenerated(tmp_path: Path) -> None:
    store = ck.RunStore(tmp_path / "run")
    store.create({"run_id": "SYNTHETIC"})
    table = sp.make_splits(synthetic_population(), 3, 2, 1, 1)
    digest = store.save_splits(table)
    pd.testing.assert_frame_equal(store.load_splits(digest), table)
    with pytest.raises(ck.CheckpointError):
        store.load_splits("0" * 64)


# ----------------------------------------------------------- explainability


def test_component_permutation_moves_whole_components() -> None:
    components = np.array(["G1", "G1", "G2", "G3", "G3"])
    source = st.component_permutation(components, np.random.default_rng(0))
    for component in ("G1", "G3"):
        donors = {components[s] for s in source[components == component]}
        assert len(donors) == 1


def test_bh_and_empirical_p() -> None:
    real = pd.Series({"A": 1.0, "B": 0.1})
    null = pd.DataFrame({"d1": [0.2, 0.3], "d2": [0.1, 0.5]}, index=["A", "B"])
    missing = null.assign(d3=[np.nan, np.nan])  # a missing draw never shrinks p
    pd.testing.assert_series_equal(st.empirical_p(real, missing), st.empirical_p(real, null))
    p = st.empirical_p(real, null)
    assert p["A"] == pytest.approx(1 / 3) and p["B"] == pytest.approx(1.0)
    assert list(st.benjamini_hochberg(pd.Series([0.001, 0.5]), q=0.05)) == [True, False]
    assert st.rbo(["a", "b"], ["a", "b"]) == pytest.approx((1 - 0.9) * (1 + 0.9))


# ---------------------------------------------------------------- simulation


def test_scenario_shares_are_validated_and_normalised() -> None:
    with pytest.raises(ValueError):
        gen.Scenario("bad", 0.6, -0.1, 0.1, 0.2, 0.0, 1.0)  # negative effect_k
    with pytest.raises(ValueError):
        gen.Scenario("bad", 0.6, 0.5, 0.1, 0.0, 0.0, 1.0)  # effect_k needs noise > 0
    scenario = gen.Scenario("s", tissue_share=0.35, effect_k=0.5, component_share=0.05,
                            noise_share=0.2, logit_mean=0.0, logit_sd=1.0)  # fmt: skip
    shares = scenario.shares()
    assert sum(shares.values()) == pytest.approx(1.0)
    assert shares["expression"] / shares["noise"] == pytest.approx(0.25)  # k^2
    assert gen.Scenario("n", 0.35, 0.0, 0.05, 0.2, 0.0, 1.0).is_null


def test_copula_is_lineage_conditional_and_bounded_by_residual_range() -> None:
    rng = np.random.default_rng(4)
    lineage = pd.Series(["A"] * 15 + ["B"] * 15)
    real = pd.DataFrame(rng.gamma(2.0, size=(30, 15)), columns=[f"G{i}" for i in range(15)])
    real.loc[lineage == "B"] += 10.0  # SYNTHETIC lineage shift
    copula = gen.fit_copula(real, lineage, n_components=5)
    labels = ["A"] * 25 + ["B"] * 25
    sample = gen.sample_expression(copula, labels, np.random.default_rng(5))
    assert sample.shape == (50, 15)
    assert sample.iloc[25:].mean().mean() - sample.iloc[:25].mean().mean() == pytest.approx(
        10.0, abs=1.5
    )
    residual_low = copula.sorted_residuals[0] + copula.centroids.loc["A"].to_numpy()
    assert (sample.iloc[:25].to_numpy() >= residual_low - 1e-9).all()


def test_signal_map_is_fixed_once_fitted() -> None:
    rng = np.random.default_rng(6)
    genes = [f"G{i}" for i in range(12)]
    reference = pd.DataFrame(rng.normal(size=(200, 12)), columns=genes)
    sets = {"S1": tuple(genes[:6]), "S2": tuple(genes[6:])}
    signal_map = gen.fit_signal_map(reference, sets, gen.expression_direction(2, 1))
    assert np.std(signal_map.unit_signal(reference)) == pytest.approx(1.0)
    rows = reference.iloc[:3]
    # a row's signal does not depend on which other rows are scored with it
    np.testing.assert_allclose(signal_map.unit_signal(rows), signal_map.unit_signal(reference)[:3])


def test_adoption_rule() -> None:
    def row(method: str, scenario: str, coverage: float, fpr: float, width: float) -> dict:
        return {
            "scenario": scenario, "method": method, "one_sided_coverage": coverage,
            "false_positive_rate": fpr, "mean_width": width, "mean_sd_between_repeats": 0.001,
        }  # fmt: skip

    summary = pd.DataFrame(
        [
            row("nadeau_bengio", "null", 0.95, 0.05, 0.04),
            row("nadeau_bengio", "weak", 0.94, np.nan, 0.04),
            row("naive_component_t", "null", 0.80, 0.20, 0.02),
            row("naive_component_t", "weak", 0.82, np.nan, 0.02),
        ]
    )
    decision = adopt(summary, nsim=500, alpha=0.05, simulated_repeats=10)
    assert decision["adopted_method"] == "nadeau_bengio"
    assert decision["repeats"] == 10 and decision["recheck_required"] is False
    failing = summary.assign(one_sided_coverage=0.5)
    assert (
        adopt(failing, nsim=500, alpha=0.05, simulated_repeats=10)["adopted_method"]
        == "not_assessable"
    )
    noisy = adopt(
        summary.assign(mean_sd_between_repeats=1.0), nsim=500, alpha=0.05, simulated_repeats=10
    )
    assert noisy["repeats"] is None and noisy["repeats_status"] == "R_rule_not_met"
    assert noisy["recheck_required"] is True
    # more than 1% non-finite bounds in any scenario disqualifies a method
    unstable = summary.assign(n_replicates=500, n_nonfinite_bounds=[6, 0, 0, 0])
    assert (
        adopt(unstable, nsim=500, alpha=0.05, simulated_repeats=10)["adopted_method"]
        == "not_assessable"
    )


def test_simulation_checkpoints_are_verified(tmp_path: Path) -> None:
    path = tmp_path / "rep.json"
    path.write_text(json.dumps({"scenario": "a", "replicate": 0, "seed": 5}))
    assert load_checked(path, {"scenario": "a", "seed": 5})["replicate"] == 0
    with pytest.raises(ck.CheckpointError):
        load_checked(path, {"scenario": "a", "seed": 6})
    target = tmp_path / "decision.json"
    write_once_or_compare(target, "x")
    write_once_or_compare(target, "x")
    with pytest.raises(ck.CheckpointError):
        write_once_or_compare(target, "y")


# ------------------------------------------------------------ controls / report


def test_permutation_control_moves_whole_components_within_lineage() -> None:
    population = synthetic_population(n_components=40)
    y = pd.Series(np.arange(len(population), dtype=float), index=population.index)  # SYNTHETIC
    permuted = permuted_within_tissue(y, population["lineage"], population["component_id"], seed=3)
    for _, part in population.groupby("lineage"):  # values reassigned within lineage only
        assert set(permuted.loc[part.index]) <= set(y.loc[part.index])
    for _, part in population.groupby("component_id"):
        donors = {
            population.loc[y.index[y == v][0], "component_id"] for v in permuted.loc[part.index]
        }
        assert len(donors) == 1
    again = permuted_within_tissue(y, population["lineage"], population["component_id"], seed=3)
    pd.testing.assert_series_equal(permuted, again)


def test_control_seed_depends_only_on_the_draw() -> None:
    assert control_seed(1, "perm_0001") == control_seed(1, "perm_0001")
    assert control_seed(1, "perm_0001") != control_seed(1, "perm_0002")


def test_only_the_primary_comparison_gets_a_verdict() -> None:
    positive = iv.Interval("nadeau_bengio", 0.02, 0.01, 0.03, 0.05)
    negative = iv.Interval("nadeau_bengio", -0.03, -0.05, -0.01, 0.05)
    assert verdict(positive, primary=True).startswith("gain shown")
    assert verdict(negative, primary=True) == "no gain shown"
    assert verdict(positive, primary=False).startswith("descriptive")
    assert verdict(None, primary=True).startswith("descriptive")


def test_scale_rows_are_recorded_then_verified(tmp_path: Path) -> None:
    path = tmp_path / "scale_rows.json"
    outcomes = {"raw": pd.Series([0.1, 0.2], index=[2, 3])}  # SYNTHETIC
    check_scale_rows(path, outcomes, resume=False)
    check_scale_rows(path, outcomes, resume=True)
    with pytest.raises(ck.CheckpointError):
        check_scale_rows(path, {"raw": pd.Series([0.1], index=[2])}, resume=True)


def test_json_roundtrip_of_task_record_matches_dataclass(tmp_path: Path) -> None:
    task = ck.make_task("ctx", 1, "raw", "M2", 0, 0, "perm_0001")
    from dataclasses import asdict

    assert json.loads(json.dumps(asdict(task))) == asdict(task)
