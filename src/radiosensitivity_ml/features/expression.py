"""DepMap expression matrix loading (no transformation, no outcome)."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

GENE_COLUMN = re.compile(r"^(?P<symbol>\S+) \((?P<entrez>\d+)\)$")


class ExpressionFormatError(ValueError):
    """Raised when the matrix does not have the verified 24Q4 layout."""


def gene_symbols(columns: Sequence[str]) -> list[str]:
    """Map 'SYMBOL (Entrez)' column names to symbols; fail on any other form."""
    symbols = []
    for column in columns:
        match = GENE_COLUMN.match(column)
        if not match:
            raise ExpressionFormatError(f"unexpected gene column {column!r}")
        symbols.append(match.group("symbol"))
    return symbols


def load_expression(path: Path, model_ids: Sequence[str]) -> pd.DataFrame:
    """Rows = requested DepMap models (in the given order), columns = gene symbols.

    Values are log2(TPM + 1) exactly as published. Duplicate symbols keep the first
    column (reported via the ``attrs['duplicate_symbols']`` count). Missing models fail.
    """
    frame = pd.read_csv(path, index_col=0)
    symbols = gene_symbols(list(frame.columns))
    frame.columns = symbols
    duplicated = frame.columns.duplicated()
    frame = frame.loc[:, ~duplicated]
    missing = [m for m in model_ids if m not in frame.index]
    if missing:
        raise ExpressionFormatError(f"{len(missing)} models missing from expression: {missing[:3]}")
    out = frame.loc[list(model_ids)].astype(float)
    out.attrs["duplicate_symbols"] = int(duplicated.sum())
    return out
