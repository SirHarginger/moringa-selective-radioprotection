"""The prespecified model family and hyperparameter grids (protocol §9).

| ID  | Model                                                            | Role                       |
|-----|------------------------------------------------------------------|----------------------------|
| M0  | global mean                                                      | floor; new-tissue baseline |
| M1  | tissue ridge                                                     | primary comparator         |
| M1P | M1 + proliferation score (E2F + G2M, one combined score)         | S1 comparator              |
| M2  | M1 offset + elastic net on the 50 Hallmark scores                | primary model              |
| M2P | M1P offset + elastic net on the other 48 Hallmark scores         | S1 model                   |
| M2X | M0 offset + elastic net on the 50 scores (no tissue)             | tier (b) only              |
| M3  | random forest on lineage one-hot + 50 scores                     | optional secondary         |

Grid keys use the estimator's parameter names (``alpha``, ``l1_ratio``,
``baseline__alpha`` ...). Every combination is evaluated in the inner loop.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence

from sklearn.base import BaseEstimator

from radiosensitivity_ml.features.gene_sets import PROLIFERATION_SETS, GeneSetScorer
from radiosensitivity_ml.models.baselines import GlobalMean, TissueRidge
from radiosensitivity_ml.models.offset import OffsetModel, TissueScoreForest

USES_GENE_SETS = {"M1P", "M2", "M2P", "M2X", "M3"}


def build_model(
    model_id: str,
    lineages: Sequence[str],
    gene_sets: Mapping[str, Sequence[str]],
    seed: int,
    diseases: Sequence[str] = (),
) -> BaseEstimator:
    """Unfitted estimator for a model ID with default parameters."""
    tissue = TissueRidge(lineages=tuple(lineages), diseases=tuple(diseases))

    def all_sets() -> GeneSetScorer:
        return GeneSetScorer(dict(gene_sets))

    def proliferation() -> GeneSetScorer:
        return GeneSetScorer({k: gene_sets[k] for k in PROLIFERATION_SETS}, combine="PROLIFERATION")

    def other_sets() -> GeneSetScorer:
        return GeneSetScorer({k: v for k, v in gene_sets.items() if k not in PROLIFERATION_SETS})

    if model_id == "M0":
        return GlobalMean()
    if model_id == "M1":
        return tissue
    if model_id == "M1P":
        return OffsetModel(baseline=tissue, scorer=proliferation(), random_state=seed)
    if model_id == "M2":
        return OffsetModel(baseline=tissue, scorer=all_sets(), random_state=seed)
    if model_id == "M2P":
        base = OffsetModel(baseline=tissue, scorer=proliferation(), random_state=seed)
        return OffsetModel(baseline=base, scorer=other_sets(), random_state=seed)
    if model_id == "M2X":
        return OffsetModel(baseline=GlobalMean(), scorer=all_sets(), random_state=seed)
    if model_id == "M3":
        return TissueScoreForest(lineages=tuple(lineages), scorer=all_sets(), random_state=seed)
    raise ValueError(f"unknown model {model_id}")


def grid_points(grid: Mapping[str, Sequence[object]]) -> list[dict[str, object]]:
    """All parameter combinations, in a fixed order (sorted keys, listed value order).

    The first point is the most regularised by convention of the config files; ties in
    inner-loop error are broken in favour of the earlier point.
    """
    if not grid:
        return [{}]
    keys = sorted(grid)
    return [
        dict(zip(keys, values, strict=True))
        for values in itertools.product(*(grid[k] for k in keys))
    ]
