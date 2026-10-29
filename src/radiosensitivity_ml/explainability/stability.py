"""Gene-set importance and its stability (protocol §14 G-stab, §16).

Importance: grouped permutation importance on OUTER-TEST rows of each saved task. A
feature column is permuted by component (all records of a component receive the
values of one other component's records), and importance is the increase in
component-weighted MAE. Models are never refitted here.

Stability across tasks: mean pairwise Kendall tau of importance ranks, top-k Jaccard
and rank-biased overlap (RBO, p = 0.9).

Null comparison per gene set: p = (1 + #{null >= real}) / (1 + N) against each null
family (permuted outcome; random gene sets), Benjamini-Hochberg within each family at
q = 0.05. An attribution statement is permitted only if the primary comparison showed
a gain (G-pred, Option B) AND the set is significant against BOTH nulls.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
from scipy import stats

from radiosensitivity_ml.evaluation.metrics import weighted_mae
from radiosensitivity_ml.models.offset import OffsetModel


def component_permutation(components: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Index array giving, for each row, the row whose features it receives."""
    unique = list(dict.fromkeys(components))
    rows_of = {c: np.flatnonzero(components == c) for c in unique}
    shuffled = [unique[i] for i in rng.permutation(len(unique))]
    source = np.empty(len(components), dtype=int)
    for target, donor in zip(unique, shuffled, strict=True):
        donor_rows = rows_of[donor]
        for position, row in enumerate(rows_of[target]):
            source[row] = donor_rows[position % len(donor_rows)]
    return source


def permutation_importance(
    model: object,
    X: pd.DataFrame,
    y: np.ndarray,
    components: np.ndarray,
    n_repeats: int,
    seed: int,
) -> pd.Series:
    """Mean increase in component-weighted MAE when one feature is permuted by component.

    For an OffsetModel the baseline prediction does not depend on the permuted scores, so
    it is computed once and reused: ``baseline + enet.predict(features)`` is exactly the
    expression of ``OffsetModel.predict_from_features`` (same operations, same order), so
    the importances are bit-identical to recomputing it for every permutation.
    """
    rng = np.random.default_rng(seed)
    sizes = pd.Series(components).map(pd.Series(components).value_counts()).to_numpy()
    weights = 1.0 / sizes
    features = model.features(X)  # type: ignore[attr-defined]
    if isinstance(model, OffsetModel):
        offset = model.baseline_.predict(X)

        def predict(values: np.ndarray) -> np.ndarray:
            return offset + model.enet_.predict(values)
    else:

        def predict(values: np.ndarray) -> np.ndarray:
            return model.predict_from_features(X, values)  # type: ignore[attr-defined]

    base = weighted_mae(y, predict(features), weights)
    out = {}
    for j, name in enumerate(model.feature_names_):  # type: ignore[attr-defined]
        increases = []
        for _ in range(n_repeats):
            permuted = features.copy()
            permuted[:, j] = features[component_permutation(components, rng), j]
            increases.append(weighted_mae(y, predict(permuted), weights) - base)
        out[name] = float(np.mean(increases))
    return pd.Series(out, name="importance")


def rbo(a: list[str], b: list[str], p: float = 0.9) -> float:
    """Rank-biased overlap (truncated, Webber et al. 2010 form) of two rankings."""
    depth = min(len(a), len(b))
    total = 0.0
    for d in range(1, depth + 1):
        total += p ** (d - 1) * len(set(a[:d]) & set(b[:d])) / d
    return float((1 - p) * total)


def stability(importance: pd.DataFrame, top_k: int = 10) -> dict[str, float]:
    """Pairwise stability over tasks; ``importance`` has one column per task."""
    rankings = [list(importance[c].sort_values(ascending=False).index) for c in importance.columns]
    taus, jaccards, rbos = [], [], []
    for i, j in itertools.combinations(range(importance.shape[1]), 2):
        taus.append(stats.kendalltau(importance.iloc[:, i], importance.iloc[:, j]).statistic)
        a, b = set(rankings[i][:top_k]), set(rankings[j][:top_k])
        jaccards.append(len(a & b) / len(a | b))
        rbos.append(rbo(rankings[i], rankings[j]))
    return {
        "n_tasks": int(importance.shape[1]),
        "mean_kendall_tau": float(np.nanmean(taus)) if taus else float("nan"),
        "mean_top_k_jaccard": float(np.mean(jaccards)) if jaccards else float("nan"),
        "mean_rbo": float(np.mean(rbos)) if rbos else float("nan"),
        "top_k": top_k,
    }


MIN_NULL_DRAWS = 1000  # protocol §15: fewer completed draws -> G-stab infeasible


def empirical_p(real: pd.Series, null: pd.DataFrame) -> pd.Series:
    """p = (1 + #{null >= real}) / (1 + N) per feature; ``null`` has one column per draw.

    N counts only the valid (non-missing) null values of that feature, so a missing draw
    can never make a p-value smaller.
    """
    valid = null.notna()
    exceed = (null.ge(real, axis=0) & valid).sum(axis=1)
    return (1 + exceed) / (1 + valid.sum(axis=1))


def benjamini_hochberg(p: pd.Series, q: float = 0.05) -> pd.Series:
    """Boolean BH step-up rejections at level q ("BH-adjusted"; PRDS is not guaranteed
    for importance p-values of correlated, competing sets, so this is not claimed to
    control the FDR exactly)."""
    ordered = p.sort_values()
    m = len(ordered)
    thresholds = q * np.arange(1, m + 1) / m
    below = np.flatnonzero(ordered.to_numpy() <= thresholds)
    cutoff = ordered.iloc[below.max()] if below.size else -1.0
    return p <= cutoff


def gene_set_tests(
    real: pd.Series,
    null_permuted: pd.DataFrame,
    null_random: pd.DataFrame,
    gate_passed: bool,
    q: float = 0.05,
    min_draws: int = MIN_NULL_DRAWS,
) -> pd.DataFrame:
    """Per-set p-values against both nulls, BH decisions and the attribution flag.

    ``real`` is the tested statistic: mean importance over the outer folds of repeat 0,
    the same equal-weight fold mean used for every null draw. The permuted-outcome null
    tests 'importance exceeds the within-tissue permuted-outcome reference'; the random
    null tests 'exceeds size- and expression-matched random gene sets'. Neither is a
    set-specific causal or conditional association test. Attribution additionally needs
    at least ``min_draws`` completed draws of each null (G-stab feasibility, §15).
    """
    table = pd.DataFrame({"tested_importance_repeat0": real})
    feasible = True
    for name, null in (("permuted_outcome", null_permuted), ("random_sets", null_random)):
        aligned = null.reindex(real.index)
        table[f"n_draws_{name}"] = aligned.notna().sum(axis=1) if null.shape[1] else 0
        if null.shape[1] == 0:
            table[f"p_{name}"] = np.nan
            table[f"bh_{name}"] = False
            feasible = False
            continue
        p = empirical_p(real, aligned)
        table[f"p_{name}"] = p
        table[f"bh_{name}"] = benjamini_hochberg(p, q)
        feasible = feasible and bool((table[f"n_draws_{name}"] >= min_draws).all())
    table["g_stab_feasible"] = feasible
    table["attribution_permitted"] = (
        gate_passed & feasible & table["bh_permuted_outcome"] & table["bh_random_sets"]
    )
    return table
