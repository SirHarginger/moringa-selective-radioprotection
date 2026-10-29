"""Offset models: a baseline plus a penalised model of its residuals (protocol §9).

``OffsetModel.fit`` refits the baseline and then the residual model on the SAME rows,
so every inner-tuning fit and every outer fit uses a baseline that never saw its
validation or test rows. The residual model sees standardised gene-set scores; the
scorer and the scaler are fitted on the training rows only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import ElasticNet
from sklearn.preprocessing import StandardScaler

from radiosensitivity_ml.features.gene_sets import GeneSetScorer
from radiosensitivity_ml.models.baselines import one_hot


class OffsetModel(RegressorMixin, BaseEstimator):
    """Baseline + ElasticNet on training-fitted gene-set scores of the baseline residuals."""

    def __init__(
        self,
        baseline: BaseEstimator | None = None,
        scorer: GeneSetScorer | None = None,
        alpha: float = 0.01,
        l1_ratio: float = 0.5,
        random_state: int = 0,
    ):
        self.baseline = baseline
        self.scorer = scorer
        self.alpha = alpha
        self.l1_ratio = l1_ratio
        self.random_state = random_state

    def residual_model(self) -> ElasticNet:
        """Unfitted residual model with this estimator's parameters.

        The single definition used by ``fit`` and by the cached inner-loop tuning
        (``models.run.inner_errors_cached``), so both always fit the same model.
        """
        return ElasticNet(
            alpha=self.alpha, l1_ratio=self.l1_ratio, random_state=self.random_state, max_iter=10000
        )

    def fit(self, X: pd.DataFrame, y: pd.Series, sample_weight: np.ndarray | None = None):
        y = np.asarray(y, dtype=float)
        self.baseline_ = clone(self.baseline).fit(X, y, sample_weight=sample_weight)
        residual = y - self.baseline_.predict(X)
        self.scorer_ = clone(self.scorer).fit(X)
        scores = self.scorer_.transform(X)
        self.scaler_ = StandardScaler().fit(scores)
        self.feature_names_ = list(scores.columns)
        self.enet_ = self.residual_model()
        self.enet_.fit(self.scaler_.transform(scores), residual, sample_weight=sample_weight)
        return self

    def features(self, X: pd.DataFrame) -> np.ndarray:
        """Standardised scores used by the residual model (for importance computations)."""
        return self.scaler_.transform(self.scorer_.transform(X))

    def predict_from_features(self, X: pd.DataFrame, features: np.ndarray) -> np.ndarray:
        """Prediction with given (possibly permuted) standardised scores."""
        return self.baseline_.predict(X) + self.enet_.predict(features)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self.predict_from_features(X, self.features(X))


class TissueScoreForest(RegressorMixin, BaseEstimator):
    """M3 (optional, secondary): random forest on lineage one-hot + training-fitted scores."""

    def __init__(
        self,
        lineages: tuple[str, ...] = (),
        scorer: GeneSetScorer | None = None,
        min_samples_leaf: int = 5,
        max_features: float = 0.33,
        n_estimators: int = 500,
        random_state: int = 0,
    ):
        self.lineages = lineages
        self.scorer = scorer
        self.min_samples_leaf = min_samples_leaf
        self.max_features = max_features
        self.n_estimators = n_estimators
        self.random_state = random_state

    def _design(self, X: pd.DataFrame) -> pd.DataFrame:
        return pd.concat(
            [one_hot(X["lineage"], self.lineages, "lineage"), self.scorer_.transform(X)], axis=1
        )

    def fit(self, X: pd.DataFrame, y: pd.Series, sample_weight: np.ndarray | None = None):
        self.scorer_ = clone(self.scorer).fit(X)
        design = self._design(X)
        self.feature_names_ = list(design.columns)
        self.forest_ = RandomForestRegressor(
            n_estimators=self.n_estimators,
            min_samples_leaf=self.min_samples_leaf,
            max_features=self.max_features,
            random_state=self.random_state,
            n_jobs=1,
        ).fit(design.to_numpy(), np.asarray(y, dtype=float), sample_weight=sample_weight)
        return self

    def features(self, X: pd.DataFrame) -> np.ndarray:
        return self._design(X).to_numpy()

    def predict_from_features(self, X: pd.DataFrame, features: np.ndarray) -> np.ndarray:
        return self.forest_.predict(features)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self.forest_.predict(self.features(X))
