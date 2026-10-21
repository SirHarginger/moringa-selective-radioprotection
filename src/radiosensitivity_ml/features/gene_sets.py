"""Gene-set scores fitted on training rows only (protocol §6, §8).

``GeneSetScorer`` z-scores each gene with the mean and SD of the TRAINING rows passed
to ``fit`` and returns, per set, the mean z-score of its genes present in the matrix.
Nothing about the outcome is used. Random gene-set collections for the negative
control are size-matched and expression-level-matched using feature values only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

PROLIFERATION_SETS = ("HALLMARK_E2F_TARGETS", "HALLMARK_G2M_CHECKPOINT")
EXPECTED_HALLMARK_SETS = 50


class GeneSetError(ValueError):
    """Raised for a malformed GMT file or unusable gene sets."""


def parse_gmt(path: Path) -> dict[str, tuple[str, ...]]:
    """Read a GMT file: name <tab> description <tab> gene1 <tab> gene2 ..."""
    sets: dict[str, tuple[str, ...]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) < 3:
            raise GeneSetError(f"malformed GMT line: {line[:60]!r}")
        if fields[0] in sets:
            raise GeneSetError(f"duplicate gene set {fields[0]}")
        sets[fields[0]] = tuple(dict.fromkeys(g for g in fields[2:] if g))
    return sets


def mapped_sets(
    sets: Mapping[str, Sequence[str]], genes: Sequence[str], min_genes: int = 5
) -> tuple[dict[str, tuple[str, ...]], dict[str, int]]:
    """Restrict each set to genes present in the matrix; report unmapped counts."""
    available = set(genes)
    out, unmapped = {}, {}
    for name, members in sets.items():
        present = tuple(g for g in members if g in available)
        unmapped[name] = len(members) - len(present)
        if len(present) < min_genes:
            raise GeneSetError(f"{name}: only {len(present)} genes map to the matrix")
        out[name] = present
    return out, unmapped


class GeneSetScorer(BaseEstimator, TransformerMixin):
    """Mean z-score per gene set; gene means/SDs learned from training rows only.

    ``gene_sets`` maps set name -> genes (already mapped to matrix columns).
    ``combine`` optionally averages all sets into one column (used for the
    proliferation score) named ``combine``.
    """

    def __init__(self, gene_sets: Mapping[str, Sequence[str]], combine: str | None = None):
        self.gene_sets = gene_sets
        self.combine = combine

    def fit(self, X: pd.DataFrame, y: object = None) -> GeneSetScorer:
        genes = sorted({g for members in self.gene_sets.values() for g in members})
        values = X[genes]
        self.genes_ = genes
        self.mean_ = values.mean(axis=0)
        sd = values.std(axis=0, ddof=0)
        self.sd_ = sd.where(sd > 0, 1.0)  # constant genes contribute 0
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        z = (X[self.genes_] - self.mean_) / self.sd_
        scores = pd.DataFrame(
            {name: z[list(members)].mean(axis=1) for name, members in self.gene_sets.items()},
            index=X.index,
        )
        if self.combine:
            return scores.mean(axis=1).to_frame(self.combine)
        return scores

    def get_feature_names_out(self, input_features: object = None) -> np.ndarray:
        names = [self.combine] if self.combine else list(self.gene_sets)
        return np.asarray(names, dtype=object)


def random_gene_set_collection(
    sets: Mapping[str, Sequence[str]],
    expression: pd.DataFrame,
    seed: int,
    n_bins: int = 10,
) -> dict[str, tuple[str, ...]]:
    """Size- and expression-level-matched random sets (negative control).

    Genes are binned by mean expression over all rows (feature values only, no
    outcome; declared in protocol §15); each real gene is replaced by a random gene from
    its bin, without reuse inside a set. The real set NAMES are kept (positions match the
    real sets), so model construction and null comparisons line up. Deterministic for a
    given seed.
    """
    rng = np.random.default_rng(seed)
    means = expression.mean(axis=0)
    bins = pd.qcut(means.rank(method="first"), n_bins, labels=False)
    by_bin = {b: list(means.index[bins == b]) for b in range(n_bins)}
    out = {}
    for name, members in sets.items():
        chosen: list[str] = []
        for gene in members:
            pool = [g for g in by_bin[int(bins[gene])] if g not in chosen]
            chosen.append(pool[int(rng.integers(len(pool)))])
        out[name] = tuple(chosen)
    return out
