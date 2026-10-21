"""Synthetic data generator for the coverage simulation (protocol §13, ADEMP "D").

Expression is lineage-conditional: each lineage's centroid (mean of the REAL eligible
expression of that lineage; features only, never outcomes) plus a residual drawn from a
Gaussian copula fitted to the real within-lineage residuals. The copula has a low-rank
correlation (top principal components of the normal scores) plus independent parts, and
maps back through each gene's empirical residual quantiles. Synthetic rows therefore keep
correlated predictors, realistic marginals and the confounding of expression with tissue.

Outcome (logit scale), then back-transformed to (0, 1):
    logit(y) = mu + tissue_effect[lineage] + expression_signal + component_effect + noise
The expression signal is a FIXED function of expression (``SignalMap``: gene-set scorer,
score standardisation and signal scale fitted once on a reference synthetic sample), so
the truth and every replicate share one data-generating mechanism.

Scenario strength is ``effect_k``: before normalisation, expression share = k^2 x noise
share (k = signal SD / noise SD). The four shares are then normalised to sum to 1.
mu and the total logit SD are scenario parameters set in configs/simulation.yaml; no
input is a summary of real CLARIFi outcomes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats
from scipy.special import expit

from radiosensitivity_ml.features.gene_sets import GeneSetScorer


@dataclass(frozen=True)
class Scenario:
    """One data-generating scenario.

    ``tissue_share``, ``component_share`` and ``noise_share`` are unnormalised weights;
    the expression weight is ``effect_k**2 * noise_share``. ``shares`` normalises all four.
    """

    name: str
    tissue_share: float
    effect_k: float
    component_share: float
    noise_share: float
    logit_mean: float
    logit_sd: float

    def __post_init__(self) -> None:
        weights = (self.tissue_share, self.component_share, self.noise_share, self.effect_k)
        if min(weights) < 0:
            raise ValueError(f"{self.name}: shares and effect_k must be >= 0")
        if self.noise_share <= 0:
            raise ValueError(f"{self.name}: noise_share must be > 0 (effect_k is relative to it)")
        if self.logit_sd <= 0:
            raise ValueError(f"{self.name}: logit_sd must be > 0")

    @property
    def is_null(self) -> bool:
        return self.effect_k == 0

    def shares(self) -> dict[str, float]:
        """Normalised variance shares (sum to 1) of the four components."""
        raw = {
            "tissue": self.tissue_share,
            "expression": self.effect_k**2 * self.noise_share,
            "component": self.component_share,
            "noise": self.noise_share,
        }
        total = sum(raw.values())
        return {k: v / total for k, v in raw.items()}


@dataclass(frozen=True)
class Copula:
    """Lineage centroids plus a Gaussian copula over within-lineage residuals."""

    genes: tuple[str, ...]
    centroids: pd.DataFrame  # lineage x gene
    sorted_residuals: np.ndarray  # n x p, each column sorted (empirical quantiles)
    loadings: np.ndarray  # k x p
    residual_sd: np.ndarray  # p


def fit_copula(expression: pd.DataFrame, lineage: pd.Series, n_components: int) -> Copula:
    """Fit centroids and the residual copula (rows = models, columns = genes)."""
    lineage = lineage.loc[expression.index]
    centroids = expression.groupby(lineage).mean()
    residuals = expression.to_numpy(dtype=float) - centroids.loc[lineage].to_numpy(dtype=float)
    n = residuals.shape[0]
    ranks = stats.rankdata(residuals, axis=0)
    z = stats.norm.ppf(ranks / (n + 1))
    z = (z - z.mean(axis=0)) / np.where(z.std(axis=0) > 0, z.std(axis=0), 1.0)
    _, singular, vt = np.linalg.svd(z, full_matrices=False)
    k = min(n_components, len(singular))
    loadings = (singular[:k, None] / np.sqrt(n - 1)) * vt[:k]
    explained = (loadings**2).sum(axis=0)
    residual_sd = np.sqrt(np.clip(1.0 - explained, 0.01, None))
    return Copula(
        tuple(expression.columns), centroids, np.sort(residuals, axis=0), loadings, residual_sd
    )


def sample_expression(
    copula: Copula, lineages: Sequence[str], rng: np.random.Generator
) -> pd.DataFrame:
    """Synthetic expression profiles, one per given lineage label."""
    n = len(lineages)
    k, p = copula.loadings.shape
    z = (
        rng.standard_normal((n, k)) @ copula.loadings
        + rng.standard_normal((n, p)) * copula.residual_sd
    )
    z /= np.sqrt((copula.loadings**2).sum(axis=0) + copula.residual_sd**2)
    u = stats.norm.cdf(z)
    m = copula.sorted_residuals.shape[0]
    positions = np.clip(u * (m - 1), 0, m - 1)
    low = np.floor(positions).astype(int)
    high = np.minimum(low + 1, m - 1)
    frac = positions - low
    cols = np.arange(p)
    residual = (
        copula.sorted_residuals[low, cols] * (1 - frac) + copula.sorted_residuals[high, cols] * frac
    )
    centroid = copula.centroids.loc[list(lineages)].to_numpy(dtype=float)
    return pd.DataFrame(centroid + residual, columns=list(copula.genes))


def expression_direction(n_sets: int, seed: int) -> np.ndarray:
    """Fixed random unit direction over the standardised gene-set scores."""
    direction = np.random.default_rng(seed).standard_normal(n_sets)
    return direction / np.linalg.norm(direction)


@dataclass(frozen=True)
class SignalMap:
    """Fixed map expression -> unit-variance signal (fitted once per study)."""

    scorer: GeneSetScorer
    score_mean: np.ndarray
    score_sd: np.ndarray
    direction: np.ndarray
    signal_sd: float

    def unit_signal(self, expression: pd.DataFrame) -> np.ndarray:
        scores = self.scorer.transform(expression).to_numpy()
        return ((scores - self.score_mean) / self.score_sd) @ self.direction / self.signal_sd


def fit_signal_map(
    reference: pd.DataFrame, gene_sets: Mapping[str, Sequence[str]], direction: np.ndarray
) -> SignalMap:
    """Fit the scorer, score standardisation and signal scale on a reference sample."""
    scorer = GeneSetScorer(dict(gene_sets)).fit(reference)
    scores = scorer.transform(reference).to_numpy()
    mean = scores.mean(axis=0)
    sd = scores.std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    raw = ((scores - mean) / sd) @ direction
    signal_sd = float(raw.std()) if raw.std() > 0 else 1.0
    return SignalMap(scorer, mean, sd, direction, signal_sd)


def simulate_outcome(
    expression: pd.DataFrame,
    lineage: Sequence[str],
    component: Sequence[str],
    scenario: Scenario,
    signal_map: SignalMap,
    tissue_effects: Mapping[str, float],
    rng: np.random.Generator,
) -> np.ndarray:
    """Synthetic outcome in (0, 1) for the given rows."""
    total = scenario.logit_sd**2
    shares = scenario.shares()
    signal = signal_map.unit_signal(expression) * np.sqrt(shares["expression"] * total)
    tissue = np.array([tissue_effects[t] for t in lineage])
    components = pd.Series(list(component))
    comp_effect = components.map(
        {c: rng.normal(0, np.sqrt(shares["component"] * total)) for c in components.unique()}
    ).to_numpy()
    noise = rng.normal(0, np.sqrt(shares["noise"] * total), len(lineage))
    return expit(scenario.logit_mean + tissue + signal + comp_effect + noise)


def draw_tissue_effects(lineages: Sequence[str], scenario: Scenario, seed: int) -> dict[str, float]:
    """Tissue effects for one scenario (fixed across replicates, so the truth is defined)."""
    rng = np.random.default_rng(seed)
    sd = np.sqrt(scenario.shares()["tissue"]) * scenario.logit_sd
    return {t: float(rng.normal(0, sd)) for t in sorted(lineages)}
