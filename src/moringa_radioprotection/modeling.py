from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors, rdMolDescriptors
from rdkit.Chem.Scaffolds import MurckoScaffold

from moringa_radioprotection.nci import clean_nsc_id


def _read_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required table not found: {path}")
    return pd.read_csv(path)


def _coerce_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _scaffold_metadata(row: pd.Series) -> tuple[str, bool, str]:
    """Return an explicit Bemis-Murcko scaffold or reproducible fallback."""
    smiles = row.get("canonical_smiles")
    chemical_group_id = str(row.get("chemical_group_id", "UNKNOWN"))
    if not isinstance(smiles, str) or not smiles.strip():
        return f"FALLBACK_CHEMICAL_GROUP:{chemical_group_id}", True, "chemical_group_id"
    mol = Chem.MolFromSmiles(smiles.strip())
    if mol is None:
        return f"FALLBACK_CHEMICAL_GROUP:{chemical_group_id}", True, "chemical_group_id"
    scaffold = MurckoScaffold.GetScaffoldForMol(mol)
    if scaffold is None or scaffold.GetNumAtoms() == 0:
        canonical_smiles = Chem.MolToSmiles(mol, canonical=True)
        return f"FALLBACK_CANONICAL_SMILES:{canonical_smiles}", True, "canonical_smiles"
    return Chem.MolToSmiles(scaffold, canonical=True), False, "none"


def _structure_identity(row: pd.Series) -> str:
    inchikey = row.get("inchikey")
    if pd.notna(inchikey) and str(inchikey).strip():
        return str(inchikey).strip()
    canonical = row.get("canonical_smiles")
    if pd.notna(canonical) and str(canonical).strip():
        return str(canonical).strip()
    return "UNKNOWN"


def _chemical_group_id_for_identity(identity: str) -> str:
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:12]
    return f"chem_{digest}"


def build_cancer_modeling_table(config: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Join paired processed responses with the NSC-level raw activity summary and keep only the fully observed modeling cohort."""
    interim_dir = Path(config.get("paths", {}).get("interim_data", "data/interim"))
    paired = _read_table(interim_dir / "nci_paired_response.csv")
    raw_summary = _read_table(interim_dir / "nci_raw_activity_summary.csv")

    paired = paired.copy()
    paired["nsc_id"] = paired["nsc_id"].map(clean_nsc_id)
    raw_summary = raw_summary.copy()
    raw_summary["nsc_id"] = raw_summary["nsc_id"].map(clean_nsc_id)
    # Missing summary keys cannot match a usable paired record and repeated
    # missing values violate pandas' many-to-one merge validation. Preserve the
    # real key column, discard only unusable keys, and fail clearly if an
    # upstream summary ever contains multiple rows for a valid NSC identifier.
    raw_summary = raw_summary.dropna(subset=["nsc_id"]).copy()
    duplicate_nsc_ids = raw_summary.loc[
        raw_summary["nsc_id"].duplicated(keep=False),
        "nsc_id",
    ].drop_duplicates()
    if not duplicate_nsc_ids.empty:
        examples = ", ".join(duplicate_nsc_ids.astype(str).head(5))
        raise ValueError(f"Raw activity summary contains duplicate NSC identifiers: {examples}")

    raw_columns = [
        "median_raw_neglog10_gi50_mcf7",
        "median_raw_neglog10_gi50_du145",
        "mean_raw_neglog10_gi50_mcf7",
        "mean_raw_neglog10_gi50_du145",
    ]
    for column in raw_columns:
        if column not in raw_summary.columns:
            continue
        raw_summary[column] = _coerce_numeric(raw_summary[column])

    modeling = paired.merge(
        raw_summary[["nsc_id", *[c for c in raw_columns if c in raw_summary.columns]]],
        on="nsc_id",
        how="left",
        validate="many_to_one",
    )

    if "median_raw_neglog10_gi50_mcf7" in modeling.columns:
        modeling["mcf7_raw_neglog10_gi50"] = modeling["median_raw_neglog10_gi50_mcf7"]
    elif "mean_raw_neglog10_gi50_mcf7" in modeling.columns:
        modeling["mcf7_raw_neglog10_gi50"] = modeling["mean_raw_neglog10_gi50_mcf7"]
    else:
        modeling["mcf7_raw_neglog10_gi50"] = np.nan

    if "median_raw_neglog10_gi50_du145" in modeling.columns:
        modeling["du145_raw_neglog10_gi50"] = modeling["median_raw_neglog10_gi50_du145"]
    elif "mean_raw_neglog10_gi50_du145" in modeling.columns:
        modeling["du145_raw_neglog10_gi50"] = modeling["mean_raw_neglog10_gi50_du145"]
    else:
        modeling["du145_raw_neglog10_gi50"] = np.nan

    modeling["mcf7_raw_neglog10_gi50"] = _coerce_numeric(modeling["mcf7_raw_neglog10_gi50"])
    modeling["du145_raw_neglog10_gi50"] = _coerce_numeric(modeling["du145_raw_neglog10_gi50"])
    modeling["mcf7_zscore"] = _coerce_numeric(modeling.get("mcf7_zscore", pd.Series(np.nan, index=modeling.index)))
    modeling["du145_zscore"] = _coerce_numeric(modeling.get("du145_zscore", pd.Series(np.nan, index=modeling.index)))

    base_columns = [
        "nsc_id",
        "drug_name",
        "pubchem_sid",
        "canonical_smiles",
        "inchikey",
        "mcf7_raw_neglog10_gi50",
        "du145_raw_neglog10_gi50",
        "mcf7_zscore",
        "du145_zscore",
        "total_experiments",
        "total_after_quality_control",
    ]
    for column in base_columns:
        if column not in modeling.columns:
            modeling[column] = np.nan

    filter_steps = [
        ("source_records", len(modeling)),
        ("valid_structure_records", int(modeling["canonical_smiles"].notna().sum())),
        ("with_mcf7_raw_activity", int(modeling["mcf7_raw_neglog10_gi50"].notna().sum())),
        ("with_du145_raw_activity", int(modeling["du145_raw_neglog10_gi50"].notna().sum())),
        ("with_mcf7_processed_zscore", int(modeling["mcf7_zscore"].notna().sum())),
        ("with_du145_processed_zscore", int(modeling["du145_zscore"].notna().sum())),
    ]

    modeling = modeling[
        modeling["canonical_smiles"].notna()
        & modeling["mcf7_raw_neglog10_gi50"].notna()
        & modeling["du145_raw_neglog10_gi50"].notna()
        & modeling["mcf7_zscore"].notna()
        & modeling["du145_zscore"].notna()
    ].copy()

    filter_steps.append(("final_modeling_cohort", int(len(modeling))))
    filter_report = pd.DataFrame({"step": [name for name, _ in filter_steps], "n_records": [count for _, count in filter_steps]})
    return modeling[base_columns].reset_index(drop=True), filter_report


def build_duplicate_resolution_table(modeling: pd.DataFrame, config: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Audit exact identities and exclude only absolute-response discordance from the primary cohort."""
    absolute_threshold = float(config.get("duplicate_absolute_discordance_threshold", 1.0))
    zscore_threshold = float(config.get("duplicate_secondary_zscore_discordance_threshold", 1.0))
    groups: list[dict[str, Any]] = []

    for _, row in modeling.iterrows():
        identity = _structure_identity(row)
        if identity == "UNKNOWN":
            continue
        chemical_group_id = _chemical_group_id_for_identity(identity)
        groups.append({
            "chemical_group_id": chemical_group_id,
            "identity": identity,
            "nsc_id": row["nsc_id"],
            "canonical_smiles": row["canonical_smiles"],
            "inchikey": row.get("inchikey"),
            "mcf7_raw_neglog10_gi50": float(row["mcf7_raw_neglog10_gi50"]),
            "du145_raw_neglog10_gi50": float(row["du145_raw_neglog10_gi50"]),
            "mcf7_zscore": float(row["mcf7_zscore"]),
            "du145_zscore": float(row["du145_zscore"]),
        })

    if not groups:
        empty = pd.DataFrame(columns=[
            "chemical_group_id",
            "identity",
            "source_nsc_count",
            "source_nsc_ids",
            "canonical_smiles",
            "inchikey",
            "mcf7_raw_neglog10_gi50_range",
            "du145_raw_neglog10_gi50_range",
            "mcf7_zscore_range",
            "du145_zscore_range",
            "primary_absolute_response_discordant",
            "secondary_zscore_response_discordant",
        ])
        primary_columns = [
            "chemical_group_id",
            "nsc_id",
            "source_nsc_count",
            "source_nsc_ids",
            "canonical_smiles",
            "inchikey",
            "mcf7_raw_neglog10_gi50",
            "du145_raw_neglog10_gi50",
            "mcf7_zscore",
            "du145_zscore",
            "primary_absolute_response_discordant",
            "secondary_zscore_response_discordant",
        ]
        return empty, pd.DataFrame(columns=primary_columns)

    audit = pd.DataFrame(groups)
    audit["source_nsc_ids"] = audit["nsc_id"].map(str)
    grouped = audit.groupby("chemical_group_id", dropna=False, as_index=False)

    duplicate_rows = []
    unique_rows = []
    for chemical_group_id, group in grouped:
        group = group.sort_values("nsc_id").reset_index(drop=True)
        source_nsc_ids = sorted(str(value) for value in group["nsc_id"].dropna().unique())
        canonical_smiles = group["canonical_smiles"].dropna().iloc[0] if group["canonical_smiles"].notna().any() else None
        inchikey = group["inchikey"].dropna().iloc[0] if group["inchikey"].notna().any() else None
        mcf7_range = float(group["mcf7_raw_neglog10_gi50"].max() - group["mcf7_raw_neglog10_gi50"].min())
        du145_range = float(group["du145_raw_neglog10_gi50"].max() - group["du145_raw_neglog10_gi50"].min())
        mcf7_z_range = float(group["mcf7_zscore"].max() - group["mcf7_zscore"].min())
        du145_z_range = float(group["du145_zscore"].max() - group["du145_zscore"].min())
        primary_absolute_discordant = bool(
            mcf7_range > absolute_threshold or du145_range > absolute_threshold
        )
        secondary_zscore_discordant = bool(
            mcf7_z_range > zscore_threshold or du145_z_range > zscore_threshold
        )

        row = {
            "chemical_group_id": chemical_group_id,
            "identity": group["identity"].iloc[0],
            "source_nsc_count": int(len(source_nsc_ids)),
            "source_nsc_ids": "; ".join(source_nsc_ids),
            "canonical_smiles": canonical_smiles,
            "inchikey": inchikey,
            "mcf7_raw_neglog10_gi50_range": mcf7_range,
            "du145_raw_neglog10_gi50_range": du145_range,
            "mcf7_zscore_range": mcf7_z_range,
            "du145_zscore_range": du145_z_range,
            "primary_absolute_response_discordant": primary_absolute_discordant,
            "secondary_zscore_response_discordant": secondary_zscore_discordant,
        }
        duplicate_rows.append(row)

        unique_rows.append({
            "chemical_group_id": chemical_group_id,
            "nsc_id": source_nsc_ids[0],
            "source_nsc_count": int(len(source_nsc_ids)),
            "source_nsc_ids": "; ".join(source_nsc_ids),
            "canonical_smiles": canonical_smiles,
            "inchikey": inchikey,
            "mcf7_raw_neglog10_gi50": float(group["mcf7_raw_neglog10_gi50"].median()),
            "du145_raw_neglog10_gi50": float(group["du145_raw_neglog10_gi50"].median()),
            "mcf7_zscore": float(group["mcf7_zscore"].median()),
            "du145_zscore": float(group["du145_zscore"].median()),
            "primary_absolute_response_discordant": primary_absolute_discordant,
            "secondary_zscore_response_discordant": secondary_zscore_discordant,
        })

    duplicate_resolution = pd.DataFrame(duplicate_rows)
    all_group_medians = pd.DataFrame(unique_rows)
    primary_unique_chemicals = all_group_medians.loc[
        ~all_group_medians["primary_absolute_response_discordant"]
    ].copy()
    return duplicate_resolution, primary_unique_chemicals


def build_discordant_duplicate_audit(duplicate_resolution: pd.DataFrame) -> pd.DataFrame:
    """Return only groups excluded for primary absolute-response discordance."""
    columns = [
        "chemical_group_id",
        "source_nsc_count",
        "source_nsc_ids",
        "canonical_smiles",
        "inchikey",
        "mcf7_raw_range",
        "du145_raw_range",
        "mcf7_zscore_range",
        "du145_zscore_range",
        "primary_absolute_response_discordant",
        "secondary_zscore_response_discordant",
    ]
    if duplicate_resolution.empty:
        return pd.DataFrame(columns=columns)

    discordant = duplicate_resolution.loc[
        duplicate_resolution["primary_absolute_response_discordant"].fillna(False)
    ].copy()
    discordant = discordant.rename(
        columns={
            "mcf7_raw_neglog10_gi50_range": "mcf7_raw_range",
            "du145_raw_neglog10_gi50_range": "du145_raw_range",
        }
    )
    return discordant[columns].sort_values("chemical_group_id").reset_index(drop=True)


def build_secondary_zscore_discordant_audit(duplicate_resolution: pd.DataFrame) -> pd.DataFrame:
    """Preserve secondary z-score-discordant groups without affecting primary-cohort membership."""
    columns = [
        "chemical_group_id",
        "source_nsc_count",
        "source_nsc_ids",
        "canonical_smiles",
        "inchikey",
        "mcf7_raw_range",
        "du145_raw_range",
        "mcf7_zscore_range",
        "du145_zscore_range",
        "primary_absolute_response_discordant",
        "secondary_zscore_response_discordant",
    ]
    if duplicate_resolution.empty:
        return pd.DataFrame(columns=columns)

    discordant = duplicate_resolution.loc[
        duplicate_resolution["secondary_zscore_response_discordant"].fillna(False)
    ].copy()
    discordant = discordant.rename(
        columns={
            "mcf7_raw_neglog10_gi50_range": "mcf7_raw_range",
            "du145_raw_neglog10_gi50_range": "du145_raw_range",
        }
    )
    return discordant[columns].sort_values("chemical_group_id").reset_index(drop=True)


def add_boundary_flags(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Add assay-boundary flags for later sensitivity analysis without censoring the main cohort."""
    boundaries = config.get("assay_boundaries", {})
    mcf7_lower = float(boundaries.get("mcf7_lower", 4.0))
    mcf7_upper = float(boundaries.get("mcf7_upper", 8.0))
    du145_lower = float(boundaries.get("du145_lower", 4.0))
    du145_upper = float(boundaries.get("du145_upper", 8.0))

    frame = frame.copy()
    frame["mcf7_at_lower_boundary"] = _coerce_numeric(frame["mcf7_raw_neglog10_gi50"]).eq(mcf7_lower)
    frame["du145_at_lower_boundary"] = _coerce_numeric(frame["du145_raw_neglog10_gi50"]).eq(du145_lower)
    frame["mcf7_at_upper_boundary"] = _coerce_numeric(frame["mcf7_raw_neglog10_gi50"]).eq(mcf7_upper)
    frame["du145_at_upper_boundary"] = _coerce_numeric(frame["du145_raw_neglog10_gi50"]).eq(du145_upper)
    return frame


def attach_reconstruction_qc(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Join reconstruction diagnostics by NSC and add sensitivity-analysis flags without filtering the main cohort."""
    table_dir = Path(config.get("paths", {}).get("tables", "results/tables"))
    reconstruction_path = table_dir / "nci_raw_zscore_reconstruction.csv"
    if not reconstruction_path.exists():
        return frame

    reconstruction = pd.read_csv(reconstruction_path)
    if reconstruction.empty:
        return frame
    reconstruction = reconstruction.copy()
    reconstruction["nsc_id"] = reconstruction["nsc_id"].map(clean_nsc_id)
    reconstruction["abs_error_ddof0"] = _coerce_numeric(reconstruction.get("abs_error_ddof0", pd.Series(np.nan, index=reconstruction.index)))
    reconstruction["abs_error_ddof1"] = _coerce_numeric(reconstruction.get("abs_error_ddof1", pd.Series(np.nan, index=reconstruction.index)))

    reshape = []
    for target_name in ("MCF7", "DU145"):
        target_frame = reconstruction[reconstruction["target"] == target_name].copy()
        if target_frame.empty:
            continue
        collapsed = target_frame.groupby("nsc_id", as_index=False).agg(
            reconstruction_abs_error_ddof0=("abs_error_ddof0", "median"),
        )
        target_field = f"{target_name.lower()}_zscore_reconstruction_abs_error"
        collapsed = collapsed.rename(columns={"reconstruction_abs_error_ddof0": target_field})
        reshape.append(collapsed[["nsc_id", target_field]])

    if not reshape:
        return frame

    merged = frame.copy()
    for part in reshape:
        merged = merged.merge(part, on="nsc_id", how="left", validate="many_to_one")
    for field in ("mcf7_zscore_reconstruction_abs_error", "du145_zscore_reconstruction_abs_error"):
        if field not in merged.columns:
            merged[field] = np.nan
        merged[field] = _coerce_numeric(merged[field])

    thresholds = config.get("reconstruction_error_thresholds", {})
    for threshold_name, value in thresholds.items():
        if threshold_name in {"gt_0_25", "gt_0_50", "gt_1"}:
            threshold_value = float(value)
            flag_column = f"reconstruction_error_{threshold_name}"
            merged[flag_column] = False
            for target_name in ("mcf7", "du145"):
                field = f"{target_name}_zscore_reconstruction_abs_error"
                if field in merged.columns:
                    merged[flag_column] = merged[flag_column] | (merged[field] > threshold_value)
    return merged


def compute_basic_descriptors(unique_chemicals: pd.DataFrame) -> pd.DataFrame:
    descriptors = []
    for _, row in unique_chemicals.iterrows():
        smiles = row.get("canonical_smiles")
        if pd.isna(smiles):
            continue
        mol = Chem.MolFromSmiles(str(smiles))
        if mol is None:
            continue
        descriptors.append({
            "chemical_group_id": row["chemical_group_id"],
            "molecular_weight": float(Descriptors.MolWt(mol)),
            "clogp": float(rdMolDescriptors.CalcCrippenDescriptors(mol)[0]),
            "tpsa": float(Descriptors.TPSA(mol)),
            "h_bond_donors": int(Descriptors.NumHDonors(mol)),
            "h_bond_acceptors": int(Descriptors.NumHAcceptors(mol)),
            "rotatable_bonds": int(Descriptors.NumRotatableBonds(mol)),
            "ring_count": int(rdMolDescriptors.CalcNumRings(mol)),
            "heavy_atom_count": int(Descriptors.HeavyAtomCount(mol)),
            "fraction_csp3": float(rdMolDescriptors.CalcFractionCSP3(mol)),
        })
    return pd.DataFrame(descriptors)


def generate_morgan_fingerprints(unique_chemicals: pd.DataFrame, config: dict[str, Any], output_dir: Path) -> tuple[np.ndarray, pd.DataFrame]:
    output_dir.mkdir(parents=True, exist_ok=True)
    fingerprint_cfg = config.get("molecular_features", {})
    radius = int(fingerprint_cfg.get("radius", 2))
    n_bits = int(fingerprint_cfg.get("n_bits", 2048))
    use_chirality = bool(fingerprint_cfg.get("use_chirality", True))

    rows: list[np.ndarray] = []
    mapping: list[dict[str, Any]] = []
    for row_index, row in unique_chemicals.iterrows():
        smiles = row.get("canonical_smiles")
        if pd.isna(smiles):
            continue
        mol = Chem.MolFromSmiles(str(smiles))
        if mol is None:
            continue
        fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=radius, nBits=n_bits, useChirality=use_chirality)
        rows.append(np.array(fp, dtype=np.uint8))
        mapping.append({"row_index": len(mapping), "chemical_group_id": row["chemical_group_id"]})

    if not rows:
        empty_matrix = np.zeros((0, n_bits), dtype=np.uint8)
        np.savez_compressed(output_dir / "nci_morgan_fingerprints.npz", fingerprints=empty_matrix)
        mapping_df = pd.DataFrame(columns=["row_index", "chemical_group_id"])
        mapping_df.to_csv(output_dir / "nci_morgan_fingerprint_map.csv", index=False)
        return empty_matrix, mapping_df

    matrix = np.vstack(rows)
    np.savez_compressed(output_dir / "nci_morgan_fingerprints.npz", fingerprints=matrix)
    mapping_df = pd.DataFrame(mapping)
    mapping_df.to_csv(output_dir / "nci_morgan_fingerprint_map.csv", index=False)
    return matrix, mapping_df


def _split_fractions(config: dict[str, Any]) -> tuple[list[str], np.ndarray]:
    """Read and validate the configured train/validation/test proportions."""
    split_cfg = config.get("validation", {})
    split_names = ["train", "validation", "test"]
    fractions = np.array(
        [
            float(split_cfg.get("train_fraction", 0.8)),
            float(split_cfg.get("validation_fraction", 0.1)),
            float(split_cfg.get("test_fraction", 0.1)),
        ],
        dtype=float,
    )
    if np.any(fractions <= 0) or not np.isclose(fractions.sum(), 1.0):
        raise ValueError(f"Split fractions must be positive and sum to 1.0: {fractions.tolist()}")
    return split_names, fractions


def _target_scaffold_counts(n_scaffolds: int, fractions: np.ndarray) -> np.ndarray:
    """Allocate indivisible scaffold counts by largest remainder, keeping every split nonempty."""
    if n_scaffolds < len(fractions):
        raise ValueError("At least three distinct scaffold groups are required for a three-way split.")
    raw_counts = fractions * n_scaffolds
    counts = np.floor(raw_counts).astype(int)
    remainder = n_scaffolds - int(counts.sum())
    remainder_order = np.argsort(-(raw_counts - counts), kind="stable")
    for index in remainder_order[:remainder]:
        counts[index] += 1
    for index in np.flatnonzero(counts == 0):
        donor = int(np.argmax(counts))
        counts[donor] -= 1
        counts[index] += 1
    return counts


def _select_scaffold_assignments(
    scaffold_groups: pd.DataFrame,
    fractions: np.ndarray,
    seed: int,
) -> dict[str, str]:
    """Select the seeded group shuffle best balancing molecule and scaffold proportions."""
    split_names = ["train", "validation", "test"]
    ordered = scaffold_groups.sort_values("scaffold").reset_index(drop=True)
    n_scaffolds = len(ordered)
    target_scaffold_counts = _target_scaffold_counts(n_scaffolds, fractions)
    scaffold_sizes = ordered["molecules"].to_numpy(dtype=int)
    total_molecules = int(scaffold_sizes.sum())
    candidate_count = max(256, min(2048, n_scaffolds))
    rng = np.random.default_rng(seed)

    best_score = float("inf")
    best_assignment: np.ndarray | None = None
    boundaries = np.cumsum(target_scaffold_counts)[:-1]
    for _ in range(candidate_count):
        permutation = rng.permutation(n_scaffolds)
        scaffold_partitions = np.split(permutation, boundaries)
        molecule_fractions = np.array(
            [scaffold_sizes[partition].sum() / total_molecules for partition in scaffold_partitions]
        )
        scaffold_fractions = target_scaffold_counts / n_scaffolds
        molecule_deviation = (molecule_fractions - fractions) / fractions
        scaffold_deviation = (scaffold_fractions - fractions) / fractions
        score = float(np.square(molecule_deviation).sum() + np.square(scaffold_deviation).sum())
        if score < best_score:
            assignment = np.empty(n_scaffolds, dtype=object)
            for split_name, partition in zip(split_names, scaffold_partitions):
                assignment[partition] = split_name
            best_score = score
            best_assignment = assignment

    if best_assignment is None:
        raise RuntimeError("Unable to construct a scaffold-group split candidate.")
    return dict(zip(ordered["scaffold"].astype(str), best_assignment))


def assign_scaffold_split(unique_chemicals: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Assign scaffold groups using seeded candidates without consulting target values."""
    output_columns = [
        "chemical_group_id",
        "source_nsc_ids",
        "scaffold",
        "scaffold_is_fallback",
        "scaffold_fallback_type",
        "split",
    ]
    if unique_chemicals.empty:
        return pd.DataFrame(columns=output_columns)

    seed = int(config.get("project", {}).get("random_seed", 42))
    _, fractions = _split_fractions(config)

    split_df = unique_chemicals.copy()
    scaffold_metadata = split_df.apply(_scaffold_metadata, axis=1, result_type="expand")
    scaffold_metadata.columns = ["scaffold", "scaffold_is_fallback", "scaffold_fallback_type"]
    split_df[scaffold_metadata.columns] = scaffold_metadata
    scaffold_groups = split_df.groupby("scaffold", as_index=False).agg(molecules=("chemical_group_id", "count"))
    assignments = _select_scaffold_assignments(scaffold_groups, fractions, seed)
    split_df["split"] = split_df["scaffold"].map(assignments)
    if split_df["split"].isna().any():
        raise RuntimeError("One or more scaffold groups were not assigned to a split.")

    return split_df[output_columns].copy()


def summarize_scaffold_split(split_table: pd.DataFrame, unique_chemicals: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Summarize split balance; response statistics are descriptive and never used for allocation."""
    summary_rows = []
    joined = split_table.merge(unique_chemicals, on="chemical_group_id", how="left", validate="one_to_one")
    total_molecules = len(joined)
    total_scaffolds = int(joined["scaffold"].nunique())
    for split_name in ["train", "validation", "test"]:
        split_cohort = joined[joined["split"] == split_name].copy()
        if split_cohort.empty:
            raise ValueError(f"Scaffold split '{split_name}' is empty.")
        row = {
            "split": split_name,
            "molecules": int(len(split_cohort)),
            "molecule_fraction": float(len(split_cohort) / total_molecules),
            "unique_scaffolds": int(split_cohort["scaffold"].nunique()),
            "scaffold_fraction": float(split_cohort["scaffold"].nunique() / total_scaffolds),
            "bemis_murcko_scaffolds": int(
                split_cohort.loc[~split_cohort["scaffold_is_fallback"], "scaffold"].nunique()
            ),
            "fallback_scaffold_molecules": int(split_cohort["scaffold_is_fallback"].sum()),
            "mcf7_raw_mean": float(split_cohort["mcf7_raw_neglog10_gi50"].mean()),
            "mcf7_raw_sd": float(split_cohort["mcf7_raw_neglog10_gi50"].std(ddof=1)) if len(split_cohort) > 1 else 0.0,
            "du145_raw_mean": float(split_cohort["du145_raw_neglog10_gi50"].mean()),
            "du145_raw_sd": float(split_cohort["du145_raw_neglog10_gi50"].std(ddof=1)) if len(split_cohort) > 1 else 0.0,
            "mcf7_boundary_lower_proportion": float(split_cohort["mcf7_at_lower_boundary"].mean()) if "mcf7_at_lower_boundary" in split_cohort.columns else 0.0,
            "du145_boundary_lower_proportion": float(split_cohort["du145_at_lower_boundary"].mean()) if "du145_at_lower_boundary" in split_cohort.columns else 0.0,
            "mcf7_boundary_upper_proportion": float(split_cohort["mcf7_at_upper_boundary"].mean()) if "mcf7_at_upper_boundary" in split_cohort.columns else 0.0,
            "du145_boundary_upper_proportion": float(split_cohort["du145_at_upper_boundary"].mean()) if "du145_at_upper_boundary" in split_cohort.columns else 0.0,
        }
        for threshold_name in config.get("reconstruction_error_thresholds", {}):
            field = f"reconstruction_error_{threshold_name}"
            row[f"{field}_proportion"] = float(split_cohort[field].mean()) if field in split_cohort.columns else 0.0
        summary_rows.append(row)
    return pd.DataFrame(summary_rows)


def assess_split_leakage(split_table: pd.DataFrame) -> pd.DataFrame:
    """Check scaffold and chemical identity overlap across the train/validation/test groups."""
    required_columns = {"split", "scaffold", "chemical_group_id"}
    missing_columns = required_columns.difference(split_table.columns)
    if missing_columns:
        raise ValueError(f"Split table is missing leakage-audit columns: {sorted(missing_columns)}")
    if split_table["chemical_group_id"].duplicated().any():
        raise ValueError("Chemical group identifiers are duplicated in the scaffold split.")
    if split_table[["scaffold", "split"]].isna().any().any():
        raise ValueError("Scaffold and split assignments must not be missing.")

    splits = {name: set(group["scaffold"].tolist()) for name, group in split_table.groupby("split")}
    chemical_sets = {name: set(group["chemical_group_id"].tolist()) for name, group in split_table.groupby("split")}

    overlap_rows = []
    pairwise = [("train", "validation"), ("train", "test"), ("validation", "test")]
    for left_name, right_name in pairwise:
        left_scaffolds = splits.get(left_name, set())
        right_scaffolds = splits.get(right_name, set())
        left_chemicals = chemical_sets.get(left_name, set())
        right_chemicals = chemical_sets.get(right_name, set())
        overlap_rows.append({
            "comparison": f"{left_name}-{right_name}",
            "scaffold_overlap": int(len(left_scaffolds.intersection(right_scaffolds))),
            "chemical_identity_overlap": int(len(left_chemicals.intersection(right_chemicals))),
        })

    leakage = pd.DataFrame(overlap_rows)
    leakage["forbidden_overlap_detected"] = leakage["scaffold_overlap"].gt(0) | leakage["chemical_identity_overlap"].gt(0)
    return leakage


def validate_dependent_artifact_alignment(
    unique_chemicals: pd.DataFrame,
    descriptors: pd.DataFrame,
    fingerprint_map: pd.DataFrame,
    split_table: pd.DataFrame,
) -> None:
    """Fail if a dependent artifact does not preserve the primary cohort identity and order."""
    expected_ids = unique_chemicals["chemical_group_id"].astype(str).tolist()
    if len(expected_ids) != len(set(expected_ids)):
        raise ValueError("Primary unique-chemical cohort contains duplicate chemical_group_id values.")

    artifact_ids = {
        "descriptor table": descriptors.get("chemical_group_id", pd.Series(dtype=str)).astype(str).tolist(),
        "fingerprint map": fingerprint_map.get("chemical_group_id", pd.Series(dtype=str)).astype(str).tolist(),
        "scaffold split": split_table.get("chemical_group_id", pd.Series(dtype=str)).astype(str).tolist(),
    }
    for artifact_name, observed_ids in artifact_ids.items():
        if observed_ids != expected_ids:
            raise ValueError(f"{artifact_name} chemical_group_id order does not match the primary cohort.")

    expected_row_indices = list(range(len(expected_ids)))
    observed_row_indices = fingerprint_map.get("row_index", pd.Series(dtype=int)).tolist()
    if observed_row_indices != expected_row_indices:
        raise ValueError("Fingerprint map row_index values do not match fingerprint matrix ordering.")


def save_modeling_outputs(config: dict[str, Any], logger: Any) -> None:
    """Create the processed modeling datasets and split artifacts without training a model."""
    processed_dir = Path(config.get("paths", {}).get("processed_data", "data/processed"))
    table_dir = Path(config.get("paths", {}).get("tables", "results/tables"))
    processed_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)

    modeling, filter_report = build_cancer_modeling_table(config)
    modeling_path = processed_dir / "nci_cancer_modeling.csv"
    modeling.to_csv(modeling_path, index=False)
    logger.info("Modeling cohort written to %s", modeling_path)

    duplicate_resolution, unique_chemicals = build_duplicate_resolution_table(modeling, config)
    duplicate_resolution = duplicate_resolution.sort_values("chemical_group_id").reset_index(drop=True)
    unique_chemicals = unique_chemicals.sort_values("chemical_group_id").reset_index(drop=True)
    primary_discordant_groups = build_discordant_duplicate_audit(duplicate_resolution)
    secondary_discordant_groups = build_secondary_zscore_discordant_audit(duplicate_resolution)
    absolute_threshold = float(config.get("duplicate_absolute_discordance_threshold", 1.0))
    zscore_threshold = float(config.get("duplicate_secondary_zscore_discordance_threshold", 1.0))
    logger.info(
        "Configured primary absolute-response discordance threshold: %s log10 GI50 units",
        absolute_threshold,
    )
    logger.info(
        "Configured secondary z-score discordance threshold: %s z-score units (audit only)",
        zscore_threshold,
    )

    duplicate_resolution.to_csv(table_dir / "nci_duplicate_resolution.csv", index=False)
    discordant_path = table_dir / "nci_discordant_duplicate_groups.csv"
    primary_discordant_groups.to_csv(discordant_path, index=False)
    secondary_discordant_path = table_dir / "nci_secondary_zscore_discordant_groups.csv"
    secondary_discordant_groups.to_csv(secondary_discordant_path, index=False)
    logger.info("Duplicate resolution written to %s", table_dir / "nci_duplicate_resolution.csv")
    logger.info("Primary absolute-discordant duplicate-group audit written to %s", discordant_path)
    logger.info("Secondary z-score-discordant duplicate-group audit written to %s", secondary_discordant_path)

    resolution_metrics = [
        ("exact_chemical_groups_before_discordance_filter", int(len(duplicate_resolution))),
        ("primary_absolute_discordant_groups_excluded", int(len(primary_discordant_groups))),
        (
            "source_nsc_records_in_primary_absolute_discordant_groups",
            int(primary_discordant_groups["source_nsc_count"].sum()),
        ),
        ("secondary_zscore_discordant_groups", int(len(secondary_discordant_groups))),
        ("primary_unique_chemical_cohort", int(len(unique_chemicals))),
    ]
    filter_report = pd.concat(
        [
            filter_report,
            pd.DataFrame(resolution_metrics, columns=["step", "n_records"]),
        ],
        ignore_index=True,
    )

    unique_chemicals = add_boundary_flags(unique_chemicals, config)
    unique_chemicals = attach_reconstruction_qc(unique_chemicals, config)
    unique_chemicals = unique_chemicals.sort_values("chemical_group_id").reset_index(drop=True)
    descriptors = compute_basic_descriptors(unique_chemicals)
    fingerprints, fingerprint_map = generate_morgan_fingerprints(unique_chemicals, config, processed_dir)
    split_table = assign_scaffold_split(unique_chemicals, config)

    validate_dependent_artifact_alignment(unique_chemicals, descriptors, fingerprint_map, split_table)
    if fingerprints.shape[0] != len(unique_chemicals):
        raise ValueError("Fingerprint matrix row count does not match the primary unique-chemical cohort.")

    unique_chemicals_path = processed_dir / "nci_cancer_unique_chemicals.csv"
    unique_chemicals.to_csv(unique_chemicals_path, index=False)
    logger.info("Primary unique-chemical modeling table written to %s", unique_chemicals_path)

    descriptors_path = processed_dir / "nci_basic_descriptors.csv"
    descriptors.to_csv(descriptors_path, index=False)
    logger.info("Basic descriptor table written to %s", descriptors_path)
    logger.info("Morgan fingerprint matrix saved to %s with shape %s", processed_dir / "nci_morgan_fingerprints.npz", fingerprints.shape)
    logger.info("Fingerprint mapping saved to %s", processed_dir / "nci_morgan_fingerprint_map.csv")

    split_path = processed_dir / "nci_scaffold_split.csv"
    split_table.to_csv(split_path, index=False)
    logger.info("Scaffold split written to %s", split_path)
    split_seed = int(config.get("project", {}).get("random_seed", 42))
    scaffold_count = int(split_table["scaffold"].nunique())
    candidate_count = max(256, min(2048, scaffold_count))
    logger.info(
        "Scaffold allocation method: deterministic seeded group-shuffle candidates; seed=%d; candidates=%d",
        split_seed,
        candidate_count,
    )

    scaffold_metrics = [
        ("bemis_murcko_scaffolds", int(split_table.loc[~split_table["scaffold_is_fallback"], "scaffold"].nunique())),
        ("scaffold_fallback_molecules", int(split_table["scaffold_is_fallback"].sum())),
    ]
    filter_report = pd.concat(
        [filter_report, pd.DataFrame(scaffold_metrics, columns=["step", "n_records"])],
        ignore_index=True,
    )
    filter_path = table_dir / "nci_cancer_modeling_filter_audit.csv"
    filter_report.to_csv(filter_path, index=False)
    logger.info("Filtering audit written to %s", filter_path)

    summary = summarize_scaffold_split(split_table, unique_chemicals, config)
    summary_path = table_dir / "nci_scaffold_split_summary.csv"
    summary.to_csv(summary_path, index=False)
    logger.info("Split summary written to %s", summary_path)

    leakage = assess_split_leakage(split_table)
    leakage_path = table_dir / "nci_split_leakage_audit.csv"
    leakage.to_csv(leakage_path, index=False)
    logger.info("Leakage audit written to %s", leakage_path)

    if leakage["forbidden_overlap_detected"].any():
        raise ValueError(f"Split leakage detected: {leakage.to_dict(orient='records')}")
