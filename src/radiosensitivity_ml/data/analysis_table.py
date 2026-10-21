"""Analysis population (from the frozen identifier QC) and outcome loading.

Two deliberately separate steps:
1. ``load_population`` reads only QC metadata (no outcome) and is used to build splits.
2. ``load_outcome`` reads mSF2 and is called only after the split table exists and its
   hash is recorded (protocol §10). It never clips or imputes; on transformed scales it
   drops records at mathematically undefined boundaries and reports how many.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from radiosensitivity_ml.data.provenance import (
    ProvenanceError,
    file_sha256,
    manifest_file_sha256,
)

STRATUM_POOLED = "other solid (pooled)"


@dataclass(frozen=True)
class Population:
    """Eligible records, indexed by CLARIFi row number (stable record key)."""

    table: pd.DataFrame  # columns: depmap_id, component_id, lineage, primary_disease, stratum
    name: str
    qc_sha256: dict[str, str]

    @property
    def lineages(self) -> tuple[str, ...]:
        """Sorted lineage categories present in the population (fixed from metadata)."""
        return tuple(sorted(self.table["lineage"].unique()))

    def component_weights(self) -> pd.Series:
        """Weight 1/|component| per record, so every component sums to 1."""
        sizes = self.table.groupby("component_id")["depmap_id"].transform("size")
        return 1.0 / sizes


def verify_qc_files(qc_dir: Path, expected: dict[str, str]) -> dict[str, str]:
    """Check the frozen QC files against the hashes recorded in the config."""
    observed = {}
    for name, digest in expected.items():
        path = qc_dir / name
        if not path.is_file():
            raise ProvenanceError(f"missing QC file {path}")
        observed[name] = file_sha256(path)
        if observed[name] != digest:
            raise ProvenanceError(f"{path} differs from its recorded SHA-256")
    return observed


def stratum_labels(table: pd.DataFrame, min_components: int) -> pd.Series:
    """Stratification label: lineage if it has >= min_components components, else pooled."""
    per_lineage = table.groupby("lineage")["component_id"].nunique()
    keep = set(per_lineage[per_lineage >= min_components].index)
    return table["lineage"].where(table["lineage"].isin(keep), STRATUM_POOLED)


def select_population(eligibility: pd.DataFrame, name: str, stranded: set[str]) -> pd.DataFrame:
    """Rows of eligibility.csv belonging to the named population (metadata only)."""
    primary = eligibility["eligible_primary"].astype(str) == "True"
    if name == "primary":
        mask = primary
    elif name == "retaining_problematic":
        mask = eligibility["eligible_retaining_problematic"].astype(str) == "True"
    elif name == "stranded_excluded":
        mask = primary & ~eligibility["depmap_id"].isin(stranded)
    elif name == "identity_sound":
        raise NotImplementedError(
            "identity_sound needs the 'Misclassified.' problem-text rule (protocol P-S5); "
            "add it to the QC outputs before use"
        )
    else:
        raise ValueError(f"unknown population {name}")
    return eligibility[mask]


def load_population(
    qc_dir: Path,
    qc_sha256: dict[str, str],
    name: str = "primary",
    min_components: int = 10,
    stranded_ids: frozenset[str] = frozenset(),
) -> Population:
    """Load the analysis population from frozen QC outputs (no outcome is read)."""
    observed = verify_qc_files(qc_dir, qc_sha256)
    eligibility = pd.read_csv(qc_dir / "eligibility.csv", dtype=str)
    rows = select_population(eligibility, name, set(stranded_ids))
    table = pd.DataFrame(
        {
            "depmap_id": rows["depmap_id"].to_numpy(),
            "component_id": rows["component_id"].to_numpy(),
            "lineage": rows["oncotree_lineage"].to_numpy(),
            "primary_disease": rows["oncotree_primary_disease"].to_numpy(),
        },
        index=pd.Index(rows["row_number"].astype(int).to_numpy(), name="row_number"),
    ).sort_index()
    if table.empty:
        raise ProvenanceError(f"population {name!r} is empty")
    table["stratum"] = stratum_labels(table, min_components)
    return Population(table=table, name=name, qc_sha256=observed)


def transform_outcome(values: pd.Series, scale: str) -> tuple[pd.Series, int]:
    """Apply the outcome scale; drop undefined boundary values; never clip.

    raw: 0 <= y <= 1 kept as is. neglog: -ln(y), drops y == 0. logit: drops y in {0, 1}.
    Returns (transformed values, number of records dropped).
    """
    if scale == "raw":
        return values.astype(float), 0
    if scale == "neglog":
        keep = values > 0
        return -np.log(values[keep]), int((~keep).sum())
    if scale == "logit":
        keep = (values > 0) & (values < 1)
        kept = values[keep]
        return np.log(kept / (1 - kept)), int((~keep).sum())
    raise ValueError(f"unknown scale {scale}")


def load_outcome(clarifi: Path, clarifi_manifest: Path, population: Population) -> pd.Series:
    """Raw mSF2 for the population's records, indexed by row number.

    Verifies CLARIFi against its manifest. Fails on any invalid value (the QC already
    excluded invalid records, so this would indicate a changed file).
    """
    expected = manifest_file_sha256(clarifi_manifest, str(clarifi))
    if file_sha256(clarifi) != expected:
        raise ProvenanceError(f"{clarifi} differs from the SHA-256 in {clarifi_manifest}")
    frame = pd.read_csv(clarifi, dtype=str)
    frame.index = pd.RangeIndex(2, len(frame) + 2, name="row_number")  # CLARIFi line numbers
    ids = frame.loc[population.table.index, "Depmap ID"].str.strip()
    if not (ids.to_numpy() == population.table["depmap_id"].to_numpy()).all():
        raise ProvenanceError("CLARIFi row numbers no longer match the QC population")
    values = frame.loc[population.table.index, "mSF2"].astype(float)
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in values):
        raise ProvenanceError("invalid mSF2 value in the analysis population")
    return values.rename("msf2")
