"""Grouped, stratified split tables built from metadata only (protocol §10).

``make_splits`` takes the population table and NO outcome. It returns a long table
with one row per (repeat, outer_fold, record): role "train" or "test", and for
training rows an inner fold number (test rows: -1). Groups are relationship
components, so no component ever appears on both sides of an outer or inner split.
The table is written once, hashed, and verified (never regenerated) on resume.
"""

from __future__ import annotations

import inspect

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

SPLIT_COLUMNS = ("repeat", "outer_fold", "row_number", "role", "inner_fold")


class SplitError(ValueError):
    """Raised when a split table violates the grouping rules."""


def _sgkf(n_splits: int, seed: int) -> StratifiedGroupKFold:
    return StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed % (2**32))


def make_splits(
    population: pd.DataFrame, k_outer: int, k_inner: int, repeats: int, seed: int
) -> pd.DataFrame:
    """Repeated grouped stratified outer folds, each with grouped inner folds.

    ``population`` needs columns component_id and stratum, indexed by row_number.
    """
    rows = population.index.to_numpy()
    groups = population["component_id"].to_numpy()
    strata = population["stratum"].to_numpy()
    records = []
    for repeat in range(repeats):
        outer = _sgkf(k_outer, seed + 1000 * repeat)
        for fold, (train, test) in enumerate(outer.split(rows, strata, groups)):
            inner_fold = np.full(len(train), -1)
            inner = _sgkf(k_inner, seed + 1000 * repeat + fold + 1)
            for k, (_, val) in enumerate(inner.split(train, strata[train], groups[train])):
                inner_fold[val] = k
            for idx, inner_k in zip(train, inner_fold, strict=True):
                records.append((repeat, fold, int(rows[idx]), "train", int(inner_k)))
            for idx in test:
                records.append((repeat, fold, int(rows[idx]), "test", -1))
    table = pd.DataFrame.from_records(records, columns=list(SPLIT_COLUMNS))
    check_splits(table, population)
    return table.sort_values(["repeat", "outer_fold", "row_number"]).reset_index(drop=True)


def check_splits(table: pd.DataFrame, population: pd.DataFrame) -> None:
    """Fail unless every outer fold partitions the records and no component is split."""
    component = population["component_id"]
    for (repeat, fold), part in table.groupby(["repeat", "outer_fold"]):
        if sorted(part["row_number"]) != sorted(population.index):
            raise SplitError(f"repeat {repeat} fold {fold}: records missing or duplicated")
        sides = part.assign(component=component.loc[part["row_number"]].to_numpy())
        if (sides.groupby("component")["role"].nunique() > 1).any():
            raise SplitError(f"repeat {repeat} fold {fold}: a component is split")
        train = sides[sides["role"] == "train"]
        if (train.groupby("component")["inner_fold"].nunique() > 1).any():
            raise SplitError(
                f"repeat {repeat} fold {fold}: a component is split across inner folds"
            )
        if (train["inner_fold"] < 0).any():
            raise SplitError(f"repeat {repeat} fold {fold}: training row without inner fold")
    for repeat, part in table[table["role"] == "test"].groupby("repeat"):
        if part["row_number"].duplicated().any() or len(part) != len(population):
            raise SplitError(f"repeat {repeat}: test folds do not partition the records")


def check_no_component_split(table: pd.DataFrame, population: pd.DataFrame) -> None:
    """Weaker check for split tables that do not partition all records (tier b)."""
    component = population["component_id"]
    for (repeat, fold), part in table.groupby(["repeat", "outer_fold"]):
        sides = part.assign(component=component.loc[part["row_number"]].to_numpy())
        if (sides.groupby("component")["role"].nunique() > 1).any():
            raise SplitError(f"repeat {repeat} fold {fold}: a component is split")
        train = sides[sides["role"] == "train"]
        if (train.groupby("component")["inner_fold"].nunique() > 1).any():
            raise SplitError(
                f"repeat {repeat} fold {fold}: a component is split across inner folds"
            )


def loto_splits(
    population: pd.DataFrame, lineages: list[str], k_inner: int, seed: int
) -> pd.DataFrame:
    """Tier (b): hold out one qualifying lineage at a time; inner folds on the rest."""
    records = []
    for fold, lineage in enumerate(lineages):
        test_mask = (population["lineage"] == lineage).to_numpy()
        train_rows = population.index[~test_mask]
        train_pop = population.loc[train_rows]
        inner_fold = np.full(len(train_rows), -1)
        inner = _sgkf(k_inner, seed + fold + 1)
        splits = inner.split(train_rows, train_pop["stratum"], train_pop["component_id"])
        for k, (_, val) in enumerate(splits):
            inner_fold[val] = k
        for row, inner_k in zip(train_rows, inner_fold, strict=True):
            records.append((0, fold, int(row), "train", int(inner_k)))
        for row in population.index[test_mask]:
            records.append((0, fold, int(row), "test", -1))
    table = pd.DataFrame.from_records(records, columns=list(SPLIT_COLUMNS))
    check_no_component_split(table, population)
    return table


def extend_splits(
    table: pd.DataFrame,
    added: pd.DataFrame,
    k_outer: int,
    k_inner: int,
    seed: int,
    primary_component_rows: dict[str, int] | None = None,
) -> pd.DataFrame:
    """Sensitivity populations that ADD components keep every primary assignment.

    An added record whose component already exists in the primary splits copies that
    component's assignment (so related lines never straddle a split). Each NEW component
    (metadata only, ordered by component_id) is placed by a seeded round-robin within its
    stratum: outer fold per repeat, then an inner fold where it is training data.
    """
    rng = np.random.default_rng(seed)
    records = []
    lookup = primary_component_rows or {}
    base_component = {
        int(row): lookup[c] for row, c in added["component_id"].items() if c in lookup
    }
    for row, existing in base_component.items():
        donor = table[table["row_number"] == existing]
        for rec in donor.itertuples():
            records.append(
                (int(rec.repeat), int(rec.outer_fold), int(row), rec.role, int(rec.inner_fold))
            )
    added = added.drop(index=list(base_component))
    components = sorted(added["component_id"].unique())
    for repeat in sorted(table["repeat"].unique()):
        offsets = {s: int(rng.integers(k_outer)) for s in sorted(added["stratum"].unique())}
        counters: dict[str, int] = {}
        for component in components:
            members = added[added["component_id"] == component]
            stratum = members["stratum"].iloc[0]
            position = counters.get(stratum, 0)
            counters[stratum] = position + 1
            test_fold = (offsets[stratum] + position) % k_outer
            for fold in range(k_outer):
                role = "test" if fold == test_fold else "train"
                inner = -1 if role == "test" else (position + fold) % k_inner
                for row in members.index:
                    records.append((int(repeat), fold, int(row), role, inner))
    extra = pd.DataFrame.from_records(records, columns=list(SPLIT_COLUMNS))
    return pd.concat([table, extra]).sort_values(["repeat", "outer_fold", "row_number"])


def drop_records(table: pd.DataFrame, keep_rows: set[int]) -> pd.DataFrame:
    """Sensitivity populations that REMOVE records reuse the frozen splits minus rows."""
    return table[table["row_number"].isin(keep_rows)].reset_index(drop=True)


def split_function_takes_no_outcome() -> bool:
    """True if make_splits has no outcome-like parameter (checked by a unit test)."""
    names = set(inspect.signature(make_splits).parameters)
    return not names & {"y", "outcome", "target", "msf2"}
