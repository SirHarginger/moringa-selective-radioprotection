"""Baseline estimators: global mean (M0) and tissue-of-origin ridge (M1).

Inputs are DataFrames with a ``lineage`` column (and, for the granular variant,
``primary_disease``). Tissue categories are fixed in advance from the eligible metadata
(never learned from a fold), one-hot encoded with no reference level and NOT scaled;
the intercept is not penalised (sklearn Ridge). A category absent from the training
fold has an all-zero column, receives coefficient 0, and its predictions fall back to
the intercept.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.linear_model import Ridge


def one_hot(values: pd.Series, categories: Sequence[str], prefix: str) -> pd.DataFrame:
    """Fixed-category one-hot (no reference level). Unknown values give all-zero rows."""
    frame = pd.DataFrame(0.0, index=values.index, columns=[f"{prefix}={c}" for c in categories])
    for category in categories:
        frame.loc[values == category, f"{prefix}={category}"] = 1.0
    return frame


class GlobalMean(RegressorMixin, BaseEstimator):
    """M0: the (weighted) training mean."""

    def fit(self, X: pd.DataFrame, y: pd.Series, sample_weight: np.ndarray | None = None):
        self.mean_ = float(np.average(np.asarray(y, dtype=float), weights=sample_weight))
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.full(len(X), self.mean_)


class TissueRidge(RegressorMixin, BaseEstimator):
    """M1: ridge on fixed one-hot tissue categories (partial pooling toward the mean).

    ``lineages``: all lineage categories of the analysis population.
    ``diseases``: if given, primary-disease dummies are added (granular sensitivity
    T-S1), with the same single penalty.
    """

    def __init__(
        self,
        lineages: Sequence[str] = (),
        diseases: Sequence[str] = (),
        alpha: float = 1.0,
    ):
        self.lineages = lineages
        self.diseases = diseases
        self.alpha = alpha

    def design(self, X: pd.DataFrame) -> pd.DataFrame:
        parts = [one_hot(X["lineage"], self.lineages, "lineage")]
        if self.diseases:
            parts.append(one_hot(X["primary_disease"], self.diseases, "disease"))
        return pd.concat(parts, axis=1)

    def fit(self, X: pd.DataFrame, y: pd.Series, sample_weight: np.ndarray | None = None):
        if not self.lineages:
            raise ValueError("TissueRidge needs the fixed lineage category list")
        design = self.design(X)
        self.unseen_ = tuple(c for c in design.columns if design[c].sum() == 0)
        self.ridge_ = Ridge(alpha=self.alpha, fit_intercept=True)
        self.ridge_.fit(design.to_numpy(), np.asarray(y, dtype=float), sample_weight=sample_weight)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self.ridge_.predict(self.design(X).to_numpy())
