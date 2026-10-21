"""Candidate interval procedures for the paired component-weighted dMAE (protocol §13).

Convention (one-sided alpha = 0.05): the one-sided lower bound LB is the lower end of
the two-sided (1 - 2*alpha) = 90% interval; a superiority statement requires LB > 0
AND an interval method adopted by the simulation rule. None of these procedures is
assumed valid: adoption follows only from the investigator-run coverage simulation.

I1  Nadeau-Bengio corrected resampled t over the J = R*K per-fold values.
I3  naive component t-interval over components (repeat-averaged), a reference that is
    expected to undercover because training sets overlap.
I2  (Bates-Hastie-Tibshirani nested CV) is NOT implemented; under the protocol's
    fallback it is dropped from the candidates (decision log D03.02).
Component bootstrap: descriptive only, never adopted.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats


@dataclass(frozen=True)
class Interval:
    """A two-sided (1 - 2*alpha) interval and its one-sided lower bound."""

    method: str
    estimate: float
    lower: float
    upper: float
    alpha_one_sided: float

    @property
    def one_sided_lower(self) -> float:
        return self.lower


def nadeau_bengio(
    estimate: float,
    fold_values: np.ndarray,
    n_train: float,
    n_test: float,
    alpha: float = 0.05,
) -> Interval:
    """I1: corrected variance (1/J + n_test/n_train) * s^2, t with J - 1 df."""
    values = np.asarray(fold_values, dtype=float)
    j = values.size
    if j < 2:
        raise ValueError("need at least two fold values")
    variance = (1.0 / j + n_test / n_train) * values.var(ddof=1)
    half = stats.t.ppf(1 - alpha, j - 1) * np.sqrt(variance)
    return Interval("nadeau_bengio", estimate, estimate - half, estimate + half, alpha)


def naive_component_t(component_means: np.ndarray, alpha: float = 0.05) -> Interval:
    """I3: t-interval over component values averaged across repeats."""
    values = np.asarray(component_means, dtype=float)
    c = values.size
    estimate = float(values.mean())
    half = stats.t.ppf(1 - alpha, c - 1) * values.std(ddof=1) / np.sqrt(c)
    return Interval("naive_component_t", estimate, estimate - half, estimate + half, alpha)


def component_bootstrap(
    component_means: np.ndarray, alpha: float = 0.05, n_boot: int = 2000, seed: int = 0
) -> Interval:
    """Descriptive percentile bootstrap over components (never adopted)."""
    values = np.asarray(component_means, dtype=float)
    rng = np.random.default_rng(seed)
    draws = rng.choice(values, size=(n_boot, values.size), replace=True).mean(axis=1)
    lower, upper = np.quantile(draws, [alpha, 1 - alpha])
    return Interval("component_bootstrap", float(values.mean()), float(lower), float(upper), alpha)


def nb_sizes(per_fold: pd.DataFrame) -> tuple[float, float]:
    """Average numbers of training and test components per outer fold."""
    totals = per_fold.groupby("repeat")["n_components"].sum()
    n_test = float(per_fold["n_components"].mean())
    n_train = float(totals.mean() - n_test)
    return n_train, n_test


def candidate_intervals(summary: dict[str, object], alpha: float, seed: int = 0) -> list[Interval]:
    """All implemented candidates plus the descriptive bootstrap for one dMAE summary."""
    per_fold: pd.DataFrame = summary["per_fold"]  # type: ignore[assignment]
    component_means = summary["component_mean_over_repeats"].to_numpy()  # type: ignore[union-attr]
    n_train, n_test = nb_sizes(per_fold)
    return [
        nadeau_bengio(float(summary["estimate"]), per_fold["D"].to_numpy(), n_train, n_test, alpha),  # type: ignore[arg-type]
        naive_component_t(component_means, alpha),
        component_bootstrap(component_means, alpha, seed=seed),
    ]
