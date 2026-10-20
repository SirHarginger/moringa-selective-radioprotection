from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from scipy import stats

from moringa_radioprotection.nci import clean_nsc_id, read_excel_from_zip


MEASURED_TARGETS = {
    "MCF7": "BR:MCF7",
    "DU145": "PR:DU-145",
}


def _coerce_numeric(series: Any) -> pd.Series:
    """Coerce raw CellMiner response values to numeric while preserving missing entries."""
    if series is None:
        return pd.Series(dtype=float)
    cleaned = series.astype(str).str.strip()
    cleaned = cleaned.replace({"NA": "", "N/A": "", "na": "", "nan": "", "NaN": "", "None": "", "null": ""})
    return pd.to_numeric(cleaned, errors="coerce")


def load_raw_activity_frame(config: dict[str, Any]) -> pd.DataFrame:
    """Load the raw CellMiner NCI-60 workbook without modifying the archive."""
    raw_dir = Path(config.get("paths", {}).get("raw_data", "data/raw")) / "nci60"
    archive = raw_dir / "DTP_NCI60_RAW.zip"
    if not archive.exists():
        raise FileNotFoundError(f"Required raw NCI archive missing: {archive}")

    frame = read_excel_from_zip(archive, "output/DTP_NCI60_RAW.xlsx", "all", 10)
    return frame.copy()


def _response_columns(frame: pd.DataFrame) -> list[str]:
    """Collect the CellMiner raw-response columns across the NCI-60 profile."""
    candidates = []
    for column_name in frame.columns:
        if not isinstance(column_name, str):
            continue
        if ":" not in column_name:
            continue
        if column_name.lower().startswith(("total ", "failure ", "drug ", "nsc ", "pubchem ", "experiment ")):
            continue
        candidates.append(column_name)
    return sorted(set(candidates))


def _hash_profile(row: pd.Series, response_columns: list[str]) -> str:
    """Hash the complete raw NCI-60 profile while treating placeholder strings as missing."""
    payload: dict[str, str | float | None] = {}
    placeholder_values = {"", "-", "--", "blank", "na", "n/a", "nan", "none", "null"}
    for column_name in response_columns:
        value = row.get(column_name, None)
        if value is None:
            payload[column_name] = None
            continue
        if isinstance(value, str):
            normalized = value.strip()
            if normalized.lower() in placeholder_values:
                payload[column_name] = None
                continue
            try:
                payload[column_name] = float(normalized)
            except ValueError:
                payload[column_name] = None
            continue
        if pd.isna(value):
            payload[column_name] = None
        else:
            payload[column_name] = float(value)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def prepare_raw_activity_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize the raw activity workbook for auditing, preserving raw values and provenance."""
    prepared = frame.copy()
    prepared["nsc_id"] = prepared["NSC #"].map(clean_nsc_id)
    prepared["drug_name"] = prepared["Drug name"]
    prepared["pubchem_sid"] = prepared["PubChem SID"]
    prepared["total_probes"] = pd.to_numeric(prepared.get("Total probes", pd.Series([pd.NA] * len(prepared))), errors="coerce")
    prepared["total_after_quality_control"] = pd.to_numeric(prepared.get("Total after quality control", pd.Series([pd.NA] * len(prepared))), errors="coerce")
    prepared["failure_reason"] = prepared.get("Failure reason", pd.Series([pd.NA] * len(prepared)))
    prepared["experiment_name"] = prepared.get("Experiment name", pd.Series([pd.NA] * len(prepared)))
    prepared["row_level_qc_status_available"] = False

    for target_name, column_name in MEASURED_TARGETS.items():
        prepared[f"raw_{target_name.lower()}_neglog10_gi50"] = _coerce_numeric(prepared[column_name])
        prepared[f"{target_name.lower()}_raw_available"] = prepared[f"raw_{target_name.lower()}_neglog10_gi50"].notna()

    prepared["raw_record_count"] = 1
    return prepared


def _meaningful_failure_reason_mask(series: pd.Series) -> pd.Series:
    """Identify failure-reason entries that are meaningful rather than placeholder values."""
    placeholder_values = {"", "-", "--", "blank", "na", "n/a", "nan", "none", "null"}
    cleaned = series.fillna("").astype(str).str.strip().str.lower()
    return cleaned.ne("") & (~cleaned.isin(placeholder_values))


def summarize_raw_activity(frame: pd.DataFrame) -> pd.DataFrame:
    """Audit-level summary for the raw NCI-60 activity dataset with explicit row-vs-NSC semantics."""
    raw = prepare_raw_activity_table(frame)
    raw_rows_by_nsc = raw.groupby("nsc_id").size().rename("raw_row_count")
    nsc_mcf7 = raw.groupby("nsc_id")["raw_mcf7_neglog10_gi50"].apply(lambda s: s.notna().any())
    nsc_du145 = raw.groupby("nsc_id")["raw_du145_neglog10_gi50"].apply(lambda s: s.notna().any())
    rows_with_total_after_quality_control = int(raw["total_after_quality_control"].notna().sum())
    nscs_with_total_after_quality_control = int(raw.groupby("nsc_id")["total_after_quality_control"].apply(lambda s: s.notna().any()).sum())
    rows_with_meaningful_failure_reason = int(_meaningful_failure_reason_mask(raw["failure_reason"]).sum())
    nscs_with_meaningful_failure_reason = int(raw.groupby("nsc_id")["failure_reason"].apply(lambda s: _meaningful_failure_reason_mask(s).any()).sum())

    rows = {
        "total_raw_records": int(len(raw)),
        "unique_nsc_ids": int(raw["nsc_id"].dropna().nunique()),
        "mcf7_nonmissing_raw_rows": int(raw["raw_mcf7_neglog10_gi50"].notna().sum()),
        "du145_nonmissing_raw_rows": int(raw["raw_du145_neglog10_gi50"].notna().sum()),
        "raw_nscs_with_mcf7": int(nsc_mcf7.sum()),
        "raw_nscs_with_du145": int(nsc_du145.sum()),
        "raw_nscs_with_both": int((nsc_mcf7 & nsc_du145).sum()),
        "raw_rows_per_nsc_mean": float(raw_rows_by_nsc.mean()),
        "raw_rows_per_nsc_median": float(raw_rows_by_nsc.median()),
        "raw_rows_per_nsc_min": float(raw_rows_by_nsc.min()),
        "raw_rows_per_nsc_max": float(raw_rows_by_nsc.max()),
        "mcf7_missing_rows": int(raw["raw_mcf7_neglog10_gi50"].isna().sum()),
        "du145_missing_rows": int(raw["raw_du145_neglog10_gi50"].isna().sum()),
        "row_level_qc_status_available": False,
        "rows_with_total_after_quality_control": rows_with_total_after_quality_control,
        "nscs_with_total_after_quality_control": nscs_with_total_after_quality_control,
        "rows_with_meaningful_failure_reason": rows_with_meaningful_failure_reason,
        "nscs_with_meaningful_failure_reason": nscs_with_meaningful_failure_reason,
    }
    return pd.DataFrame({"metric": list(rows.keys()), "value": list(rows.values())})


def build_raw_activity_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Candidate per-NSC raw activity summary for auditing only; no final modeling target choice is made."""
    raw = prepare_raw_activity_table(frame)
    summary = raw.groupby("nsc_id", dropna=False).agg(
        n_raw=("nsc_id", "size"),
        mean_raw_neglog10_gi50_mcf7=("raw_mcf7_neglog10_gi50", "mean"),
        median_raw_neglog10_gi50_mcf7=("raw_mcf7_neglog10_gi50", "median"),
        std_raw_neglog10_gi50_mcf7=("raw_mcf7_neglog10_gi50", "std"),
        min_raw_neglog10_gi50_mcf7=("raw_mcf7_neglog10_gi50", "min"),
        max_raw_neglog10_gi50_mcf7=("raw_mcf7_neglog10_gi50", "max"),
        range_raw_neglog10_gi50_mcf7=("raw_mcf7_neglog10_gi50", lambda s: s.max() - s.min()),
        mean_raw_neglog10_gi50_du145=("raw_du145_neglog10_gi50", "mean"),
        median_raw_neglog10_gi50_du145=("raw_du145_neglog10_gi50", "median"),
        std_raw_neglog10_gi50_du145=("raw_du145_neglog10_gi50", "std"),
        min_raw_neglog10_gi50_du145=("raw_du145_neglog10_gi50", "min"),
        max_raw_neglog10_gi50_du145=("raw_du145_neglog10_gi50", "max"),
        range_raw_neglog10_gi50_du145=("raw_du145_neglog10_gi50", lambda s: s.max() - s.min()),
    ).reset_index()
    return summary.sort_values("nsc_id", na_position="last").reset_index(drop=True)


def build_raw_replicate_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Per-NSC replicate-level summary showing whether repeated rows are identical or variable."""
    raw = prepare_raw_activity_table(frame)
    summary = raw.groupby("nsc_id", dropna=False).agg(
        raw_row_count=("nsc_id", "size"),
        mcf7_nonmissing_rows=("raw_mcf7_neglog10_gi50", lambda s: int(s.notna().sum())),
        du145_nonmissing_rows=("raw_du145_neglog10_gi50", lambda s: int(s.notna().sum())),
        mcf7_unique_values=("raw_mcf7_neglog10_gi50", lambda s: int(s.dropna().nunique())),
        du145_unique_values=("raw_du145_neglog10_gi50", lambda s: int(s.dropna().nunique())),
        mcf7_all_identical=("raw_mcf7_neglog10_gi50", lambda s: bool(s.dropna().nunique() == 1) if s.notna().any() else False),
        du145_all_identical=("raw_du145_neglog10_gi50", lambda s: bool(s.dropna().nunique() == 1) if s.notna().any() else False),
    ).reset_index()
    return summary.sort_values("nsc_id", na_position="last").reset_index(drop=True)


def build_raw_replicate_variability(frame: pd.DataFrame) -> pd.DataFrame:
    """Detailed replicate variability for each NSC and target without collapsing duplicates."""
    raw = prepare_raw_activity_table(frame)
    all_rows: list[pd.DataFrame] = []
    for target_name, column_name in MEASURED_TARGETS.items():
        values = raw[["nsc_id", column_name]].copy()
        values["target"] = target_name
        values["raw_value"] = _coerce_numeric(values[column_name])
        values = values.dropna(subset=["nsc_id", "raw_value"]).copy()
        per_nsc = values.groupby("nsc_id").agg(
            raw_row_count=("raw_value", "size"),
            mean_raw_neglog10_gi50=("raw_value", "mean"),
            median_raw_neglog10_gi50=("raw_value", "median"),
            std_raw_neglog10_gi50=("raw_value", "std"),
            min_raw_neglog10_gi50=("raw_value", "min"),
            max_raw_neglog10_gi50=("raw_value", "max"),
            range_raw_neglog10_gi50=("raw_value", lambda s: s.max() - s.min()),
            all_identical=("raw_value", lambda s: bool(s.nunique() == 1) if s.size > 1 else False),
            target=("target", "first"),
        ).reset_index()
        all_rows.append(per_nsc)
    variability = pd.concat(all_rows, ignore_index=True)
    return variability[["nsc_id", "target", "raw_row_count", "mean_raw_neglog10_gi50", "median_raw_neglog10_gi50", "std_raw_neglog10_gi50", "min_raw_neglog10_gi50", "max_raw_neglog10_gi50", "range_raw_neglog10_gi50", "all_identical"]].sort_values(["target", "nsc_id"]).reset_index(drop=True)


def _raw_profile_identity_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Audit whether repeated rows for one NSC represent identical full NCI-60 profiles."""
    raw = prepare_raw_activity_table(frame)
    response_columns = _response_columns(raw)
    if not response_columns:
        return pd.DataFrame(columns=["nsc_id", "raw_row_count", "unique_experiment_names", "unique_full_activity_profiles", "all_full_profiles_identical"])

    rows: list[dict[str, Any]] = []
    for nsc_id, group in raw.groupby("nsc_id", dropna=False):
        if pd.isna(nsc_id):
            continue
        unique_experiment_names = int(group["experiment_name"].dropna().nunique())
        profile_set = set()
        for _, row in group.iterrows():
            profile_set.add(_hash_profile(row, response_columns))
        rows.append(
            {
                "nsc_id": str(nsc_id),
                "raw_row_count": int(len(group)),
                "unique_experiment_names": unique_experiment_names,
                "unique_full_activity_profiles": int(len(profile_set)),
                "all_full_profiles_identical": bool(len(profile_set) == 1),
            }
        )
    return pd.DataFrame(rows).sort_values("nsc_id").reset_index(drop=True)


def build_raw_profile_identity_audit(frame: pd.DataFrame) -> pd.DataFrame:
    """Return per-NSC identity audit for the full raw NCI-60 response profile."""
    return _raw_profile_identity_table(frame)


def build_raw_profile_identity_summary(identity_audit: pd.DataFrame) -> pd.DataFrame:
    """Summarize how many profile rows are genuine duplicates versus different raw profiles."""
    if identity_audit.empty:
        return pd.DataFrame({
            "metric": [
                "total_nscs",
                "nscs_with_multiple_rows",
                "multirow_nscs_with_identical_profiles",
                "multirow_nscs_with_different_profiles",
                "proportion_multirow_identical",
            ],
            "value": [0, 0, 0, 0, float("nan")],
        })

    ns_count = len(identity_audit)
    multi_row_mask = identity_audit["raw_row_count"] > 1
    multi_row = int(multi_row_mask.sum())
    identical = int(((multi_row_mask) & identity_audit["all_full_profiles_identical"]).sum())
    different = int(((multi_row_mask) & (~identity_audit["all_full_profiles_identical"])) .sum())
    summary = {
        "total_nscs": ns_count,
        "nscs_with_multiple_rows": multi_row,
        "multirow_nscs_with_identical_profiles": identical,
        "multirow_nscs_with_different_profiles": different,
        "proportion_multirow_identical": float(identical / multi_row) if multi_row else float("nan"),
    }
    return pd.DataFrame({"metric": list(summary.keys()), "value": list(summary.values())})


def build_raw_processed_overlap(raw_frame: pd.DataFrame, prepared_frame: pd.DataFrame) -> pd.DataFrame:
    """Calculate processed overlap metrics restricted to the processed cohort."""
    raw = prepare_raw_activity_table(raw_frame)
    processed = prepared_frame.copy()
    processed["nsc_id"] = processed["nsc_id"].map(clean_nsc_id)

    processed_nsc = set(processed["nsc_id"].dropna().astype(str).tolist())
    raw_subset = raw[raw["nsc_id"].dropna().astype(str).isin(processed_nsc)].copy()
    raw_nsc = set(raw_subset["nsc_id"].dropna().astype(str).tolist())

    counts = {
        "processed_nsc_count": int(len(processed_nsc)),
        "processed_nscs_present_in_raw": int(len(raw_nsc.intersection(processed_nsc))),
        "processed_nscs_with_raw_mcf7": int(raw_subset[raw_subset["raw_mcf7_neglog10_gi50"].notna()]["nsc_id"].dropna().nunique()),
        "processed_nscs_with_raw_du145": int(raw_subset[raw_subset["raw_du145_neglog10_gi50"].notna()]["nsc_id"].dropna().nunique()),
        "processed_nscs_with_raw_both": int(raw_subset[(raw_subset["raw_mcf7_neglog10_gi50"].notna()) & (raw_subset["raw_du145_neglog10_gi50"].notna())]["nsc_id"].dropna().nunique()),
        "processed_valid_structure_nscs_with_raw_both": int(
            processed[processed["structure_valid"].fillna(False)]["nsc_id"].dropna().astype(str).isin(
                set(raw_subset[(raw_subset["raw_mcf7_neglog10_gi50"].notna()) & (raw_subset["raw_du145_neglog10_gi50"].notna())]["nsc_id"].dropna().astype(str).tolist())
            ).sum()
        ),
    }
    return pd.DataFrame({"metric": list(counts.keys()), "value": list(counts.values())})


def build_qc_experiment_distribution(frame: pd.DataFrame) -> pd.DataFrame:
    """Summarize the raw workbook's Total after quality control values by experiment count categories."""
    raw = prepare_raw_activity_table(frame)
    qc_values = pd.to_numeric(raw["total_after_quality_control"], errors="coerce").dropna()
    summary = {
        "count_1": int((qc_values == 1).sum()),
        "count_2": int((qc_values == 2).sum()),
        "count_3": int((qc_values == 3).sum()),
        "count_gt_3": int((qc_values > 3).sum()),
        "median_total_after_quality_control": float(qc_values.median()),
        "min_total_after_quality_control": float(qc_values.min()),
        "max_total_after_quality_control": float(qc_values.max()),
    }
    return pd.DataFrame([summary])


def _boundary_counts(values: pd.Series, boundary_values: list[float]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for boundary in boundary_values:
        counts[f"exactly_{boundary}"] = int((values == boundary).sum())
    counts["less_than_or_equal_4"] = int((values <= 4.0).sum())
    counts["greater_than_or_equal_8"] = int((values >= 8.0).sum())
    return counts


def build_boundary_value_audit(frame: pd.DataFrame) -> pd.DataFrame:
    """Report apparent boundary-value counts for MCF7 and DU145 raw activities without censoring values."""
    raw = prepare_raw_activity_table(frame)
    rows = []
    for target_name, column_name in MEASURED_TARGETS.items():
        values = pd.to_numeric(raw[column_name], errors="coerce").dropna()
        counts = _boundary_counts(values, [4.0, 8.0])
        rows.append({"target": target_name, **counts})
    return pd.DataFrame(rows)


def _compute_reconstruction_target(raw_frame: pd.DataFrame, prepared_frame: pd.DataFrame, target_name: str, ddof: int) -> pd.DataFrame:
    """Reconstruct raw within-compound z-scores and compare them to the official processed z-scores."""
    reconstruction = _build_raw_zscore_reconstruction(raw_frame, prepared_frame)
    return _summarize_reconstruction_target(reconstruction, target_name, ddof)


RECONSTRUCTION_COLUMNS = [
    "nsc_id",
    "target",
    "official_zscore",
    "reconstructed_zscore_ddof0",
    "reconstructed_zscore_ddof1",
    "abs_error_ddof0",
    "abs_error_ddof1",
]


def _build_raw_zscore_reconstruction(
    raw_frame: pd.DataFrame,
    prepared_frame: pd.DataFrame,
    identity_audit: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build missing-safe, per-compound z-score reconstructions for both targets."""
    raw = prepare_raw_activity_table(raw_frame)
    processed = prepared_frame.copy()
    processed["nsc_id"] = processed["nsc_id"].map(clean_nsc_id)
    processed = processed.dropna(subset=["nsc_id"]).drop_duplicates(subset=["nsc_id"])

    identity = identity_audit if identity_audit is not None else build_raw_profile_identity_audit(raw_frame)
    valid_nscs = identity.loc[
        identity["all_full_profiles_identical"] & (identity["raw_row_count"] > 0),
        "nsc_id",
    ].astype(str)
    raw_unique = raw[raw["nsc_id"].astype(str).isin(set(valid_nscs))]
    raw_unique = raw_unique.drop_duplicates(subset=["nsc_id"])

    response_columns = _response_columns(raw)
    if not response_columns:
        return pd.DataFrame(columns=RECONSTRUCTION_COLUMNS)

    processed_by_nsc = processed.set_index("nsc_id")
    rows: list[dict[str, float | str]] = []
    for _, row in raw_unique.iterrows():
        nsc_id = row["nsc_id"]
        if nsc_id not in processed_by_nsc.index:
            continue

        # The raw workbook stores numeric values as strings and uses labels such
        # as "na" for missing measurements. Coerce the complete profile once so
        # target values and the mean/SD calculation follow the same rules.
        profile = _coerce_numeric(row.reindex(response_columns)).dropna()
        if profile.empty:
            continue

        processed_row = processed_by_nsc.loc[nsc_id]
        reconstructed_by_ddof: dict[int, pd.Series] = {}
        for profile_ddof in (0, 1):
            sd = profile.std(ddof=profile_ddof)
            if pd.isna(sd) or sd == 0:
                reconstructed_by_ddof[profile_ddof] = pd.Series(0.0, index=profile.index)
            else:
                reconstructed_by_ddof[profile_ddof] = (profile - profile.mean()) / sd

        for target_name, column_name in MEASURED_TARGETS.items():
            if column_name not in profile.index:
                continue
            processed_column = "mcf7_zscore" if target_name == "MCF7" else "du145_zscore"
            official_zscore = pd.to_numeric(processed_row[processed_column], errors="coerce")
            if pd.isna(official_zscore):
                continue

            reconstructed_ddof0 = float(reconstructed_by_ddof[0][column_name])
            reconstructed_ddof1 = float(reconstructed_by_ddof[1][column_name])
            rows.append(
                {
                    "nsc_id": str(nsc_id),
                    "target": target_name,
                    "official_zscore": float(official_zscore),
                    "reconstructed_zscore_ddof0": reconstructed_ddof0,
                    "reconstructed_zscore_ddof1": reconstructed_ddof1,
                    "abs_error_ddof0": abs(float(official_zscore) - reconstructed_ddof0),
                    "abs_error_ddof1": abs(float(official_zscore) - reconstructed_ddof1),
                }
            )

    return pd.DataFrame(rows, columns=RECONSTRUCTION_COLUMNS)


def _summarize_reconstruction_target(reconstruction: pd.DataFrame, target_name: str, ddof: int) -> pd.DataFrame:
    """Summarize one target and SD convention from record-level reconstruction data."""
    if target_name not in MEASURED_TARGETS:
        raise ValueError(f"Unknown reconstruction target: {target_name}")
    if ddof not in (0, 1):
        raise ValueError(f"Unsupported reconstruction ddof: {ddof}")

    reconstructed_column = f"reconstructed_zscore_ddof{ddof}"
    aligned = reconstruction.loc[
        reconstruction["target"] == target_name,
        [reconstructed_column, "official_zscore"],
    ].copy()
    aligned.columns = ["reconstructed", "official"]
    aligned = aligned.apply(pd.to_numeric, errors="coerce").dropna()
    if aligned.empty:
        return pd.DataFrame()

    pearson_r = float("nan")
    spearman_r = float("nan")
    if len(aligned) >= 2 and aligned["reconstructed"].nunique() > 1 and aligned["official"].nunique() > 1:
        pearson_r = float(stats.pearsonr(aligned["reconstructed"], aligned["official"]).statistic)
        spearman_r = float(stats.spearmanr(aligned["reconstructed"], aligned["official"]).statistic)

    errors = aligned["official"] - aligned["reconstructed"]
    return pd.DataFrame(
        [
            {
                "target": target_name,
                "ddof": int(ddof),
                "n": int(len(aligned)),
                "pearson_r": pearson_r,
                "spearman_r": spearman_r,
                "mae": float(errors.abs().mean()),
                "rmse": float((errors**2).mean() ** 0.5),
                "median_absolute_error": float(errors.abs().median()),
                "max_absolute_error": float(errors.abs().max()),
            }
        ]
    )


def build_raw_zscore_reconstruction_summary(
    raw_frame: pd.DataFrame,
    prepared_frame: pd.DataFrame,
    reconstruction_frame: pd.DataFrame | None = None,
    identity_audit: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Compare reconstructed raw-profile z-scores against the official processed z-scores for both SD conventions."""
    reconstruction = (
        reconstruction_frame
        if reconstruction_frame is not None
        else _build_raw_zscore_reconstruction(raw_frame, prepared_frame, identity_audit)
    )
    summary_frames = []
    for ddof in (0, 1):
        for target_name in ("MCF7", "DU145"):
            summary_frames.append(_summarize_reconstruction_target(reconstruction, target_name, ddof))
    populated_frames = [frame for frame in summary_frames if not frame.empty]
    if not populated_frames:
        return pd.DataFrame(
            columns=[
                "target",
                "ddof",
                "n",
                "pearson_r",
                "spearman_r",
                "mae",
                "rmse",
                "median_absolute_error",
                "max_absolute_error",
            ]
        )
    return pd.concat(populated_frames, ignore_index=True)


def build_raw_zscore_reconstruction(
    raw_frame: pd.DataFrame,
    prepared_frame: pd.DataFrame,
    identity_audit: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Record-level comparison between reconstructed and official z-scores for both ddof conventions."""
    return _build_raw_zscore_reconstruction(raw_frame, prepared_frame, identity_audit)
