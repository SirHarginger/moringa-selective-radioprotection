from __future__ import annotations

from pathlib import Path

import pandas as pd
from rdkit import Chem
from rdkit.Chem.Scaffolds import MurckoScaffold
from scipy import stats


def load_prepared_tables(interim_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load the prepared and paired NCI tables from the interim data directory."""
    prepared_path = interim_dir / "nci_cancer_response.csv"
    paired_path = interim_dir / "nci_paired_response.csv"

    if not prepared_path.exists():
        raise FileNotFoundError(f"Prepared NCI table not found: {prepared_path}")
    if not paired_path.exists():
        raise FileNotFoundError(f"Paired NCI response table not found: {paired_path}")

    prepared = pd.read_csv(prepared_path)
    paired = pd.read_csv(paired_path)
    return prepared, paired


def _describe_numeric(series: pd.Series) -> dict[str, float | int]:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return {
            "n": 0,
            "mean": float("nan"),
            "std": float("nan"),
            "median": float("nan"),
            "q1": float("nan"),
            "q3": float("nan"),
            "iqr": float("nan"),
            "min": float("nan"),
            "max": float("nan"),
            "p01": float("nan"),
            "p05": float("nan"),
            "p10": float("nan"),
            "p90": float("nan"),
            "p95": float("nan"),
            "p99": float("nan"),
        }

    q1 = values.quantile(0.25)
    q3 = values.quantile(0.75)
    return {
        "n": int(values.shape[0]),
        "mean": float(values.mean()),
        "std": float(values.std(ddof=1)) if values.shape[0] > 1 else 0.0,
        "median": float(values.median()),
        "q1": float(q1),
        "q3": float(q3),
        "iqr": float(q3 - q1),
        "min": float(values.min()),
        "max": float(values.max()),
        "p01": float(values.quantile(0.01)),
        "p05": float(values.quantile(0.05)),
        "p10": float(values.quantile(0.10)),
        "p90": float(values.quantile(0.90)),
        "p95": float(values.quantile(0.95)),
        "p99": float(values.quantile(0.99)),
    }


def compute_response_summary(paired: pd.DataFrame) -> pd.DataFrame:
    """Return a summary table for the paired MCF7 and DU145 response distributions."""
    rows = []
    for label, column in [("MCF7", "mcf7_zscore"), ("DU145", "du145_zscore")]:
        summary = _describe_numeric(paired[column])
        row = {"cell_line": label, **summary}
        rows.append(row)
    return pd.DataFrame(rows)


def compute_response_correlation(paired: pd.DataFrame) -> pd.DataFrame:
    """Compute the paired-response correlation statistics for the valid-structure cohort."""
    if paired.empty:
        return pd.DataFrame([
            {"n": 0, "pearson_r": float("nan"), "pearson_p": float("nan"), "spearman_r": float("nan"), "spearman_p": float("nan")}
        ])

    x = pd.to_numeric(paired["mcf7_zscore"], errors="coerce").dropna()
    y = pd.to_numeric(paired["du145_zscore"], errors="coerce").dropna()
    aligned = pd.DataFrame({"mcf7_zscore": x, "du145_zscore": y}).dropna()

    if aligned.empty:
        return pd.DataFrame([
            {"n": 0, "pearson_r": float("nan"), "pearson_p": float("nan"), "spearman_r": float("nan"), "spearman_p": float("nan")}
        ])

    pearson = stats.pearsonr(aligned["mcf7_zscore"], aligned["du145_zscore"])
    spearman = stats.spearmanr(aligned["mcf7_zscore"], aligned["du145_zscore"])

    return pd.DataFrame([
        {
            "n": int(len(aligned)),
            "pearson_r": float(pearson.statistic),
            "pearson_p": float(pearson.pvalue),
            "spearman_r": float(spearman.correlation),
            "spearman_p": float(spearman.pvalue),
        }
    ])


def compute_response_difference_summary(paired: pd.DataFrame) -> pd.DataFrame:
    """Summarize the response difference and mean cancer-response distributions."""
    data = paired.copy()
    data["response_difference"] = data["mcf7_zscore"] - data["du145_zscore"]
    data["mean_cancer_response"] = (data["mcf7_zscore"] + data["du145_zscore"]) / 2.0

    rows = []
    for metric_name in ["response_difference", "mean_cancer_response"]:
        row = {"metric": metric_name, **_describe_numeric(data[metric_name])}
        rows.append(row)
    return pd.DataFrame(rows)


def compute_duplicate_structure_audit(paired: pd.DataFrame) -> pd.DataFrame:
    """Audit duplicated canonical structures without deduplicating the dataset."""
    valid = paired.dropna(subset=["canonical_smiles", "inchikey"]).copy()
    valid = valid[valid["canonical_smiles"].astype(str).str.strip() != ""].copy()

    if valid.empty:
        return pd.DataFrame(columns=[
            "canonical_smiles",
            "inchikey",
            "record_count",
            "nsc_ids",
            "drug_names",
            "mcf7_mean",
            "mcf7_std",
            "mcf7_min",
            "mcf7_max",
            "mcf7_range",
            "du145_mean",
            "du145_std",
            "du145_min",
            "du145_max",
            "du145_range",
            "responses_identical",
        ])

    groups = []
    for _, group in valid.groupby("canonical_smiles", dropna=False):
        if len(group) < 2:
            continue
        groups.append(group)

    rows = []
    for group in groups:
        mcf7_values = pd.to_numeric(group["mcf7_zscore"], errors="coerce")
        du145_values = pd.to_numeric(group["du145_zscore"], errors="coerce")
        responses_identical = bool(
            group[["mcf7_zscore", "du145_zscore"]].drop_duplicates().shape[0] == 1
        )
        rows.append(
            {
                "canonical_smiles": group["canonical_smiles"].iloc[0],
                "inchikey": group["inchikey"].iloc[0],
                "record_count": int(len(group)),
                "nsc_ids": "; ".join(str(value) for value in group["nsc_id"].dropna().astype(str).tolist()),
                "drug_names": "; ".join(str(value) for value in group["drug_name"].dropna().astype(str).tolist()),
                "mcf7_mean": float(mcf7_values.mean()),
                "mcf7_std": float(mcf7_values.std(ddof=1)) if len(mcf7_values) > 1 else 0.0,
                "mcf7_min": float(mcf7_values.min()),
                "mcf7_max": float(mcf7_values.max()),
                "mcf7_range": float(mcf7_values.max() - mcf7_values.min()),
                "du145_mean": float(du145_values.mean()),
                "du145_std": float(du145_values.std(ddof=1)) if len(du145_values) > 1 else 0.0,
                "du145_min": float(du145_values.min()),
                "du145_max": float(du145_values.max()),
                "du145_range": float(du145_values.max() - du145_values.min()),
                "responses_identical": responses_identical,
            }
        )

    return pd.DataFrame(rows, columns=[
        "canonical_smiles",
        "inchikey",
        "record_count",
        "nsc_ids",
        "drug_names",
        "mcf7_mean",
        "mcf7_std",
        "mcf7_min",
        "mcf7_max",
        "mcf7_range",
        "du145_mean",
        "du145_std",
        "du145_min",
        "du145_max",
        "du145_range",
        "responses_identical",
    ])


def compute_duplicate_structure_summary(duplicate_audit: pd.DataFrame) -> pd.DataFrame:
    """Return a compact summary of duplicated exact structures."""
    if duplicate_audit.empty:
        return pd.DataFrame({
            "metric": [
                "duplicate_structure_groups",
                "duplicate_records",
                "duplicate_nsc_ids",
                "duplicate_drug_names",
            ],
            "value": [0, 0, 0, 0],
        })

    unique_nsc = set()
    drug_names = set()
    for _, row in duplicate_audit.iterrows():
        unique_nsc.update(str(value).strip() for value in row["nsc_ids"].split(";") if value.strip())
        drug_names.update(str(value).strip() for value in row["drug_names"].split(";") if value.strip())

    return pd.DataFrame({
        "metric": [
            "duplicate_structure_groups",
            "duplicate_records",
            "duplicate_nsc_ids",
            "duplicate_drug_names",
        ],
        "value": [
            int(len(duplicate_audit)),
            int(duplicate_audit["record_count"].sum()),
            int(len(unique_nsc)),
            int(len(drug_names)),
        ],
    })


def compute_qc_experiment_summary(paired: pd.DataFrame) -> pd.DataFrame:
    """Summarize the total_after_quality_control counts without filtering compounds."""
    qc_counts = pd.to_numeric(paired["total_after_quality_control"], errors="coerce").dropna().astype(int)
    if qc_counts.empty:
        return pd.DataFrame([
            {"count_1": 0, "count_2": 0, "count_3": 0, "count_gt_3": 0, "median": float("nan"), "minimum": float("nan"), "maximum": float("nan")}
        ])

    summary = {
        "count_1": int((qc_counts == 1).sum()),
        "count_2": int((qc_counts == 2).sum()),
        "count_3": int((qc_counts == 3).sum()),
        "count_gt_3": int((qc_counts > 3).sum()),
        "median": float(qc_counts.median()),
        "minimum": float(qc_counts.min()),
        "maximum": float(qc_counts.max()),
    }
    return pd.DataFrame([summary])


def _scaffold_for_molecule(smiles: str) -> str:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return ""
    scaffold = MurckoScaffold.GetScaffoldForMol(mol)
    if scaffold is None or scaffold.GetNumAtoms() == 0:
        return ""
    return Chem.MolToSmiles(scaffold, canonical=True)


def compute_scaffold_summary(paired: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute Bemis-Murcko scaffold inventory for the paired valid-structure cohort."""
    cohort = paired.dropna(subset=["canonical_smiles"]).copy()
    total_molecules = int(len(cohort))

    scaffold_counter: dict[str, int] = {}
    scaffold_free_molecules = 0
    for smiles in cohort["canonical_smiles"].astype(str):
        scaffold = _scaffold_for_molecule(smiles)
        if scaffold == "":
            scaffold_free_molecules += 1
            continue
        scaffold_counter[scaffold] = scaffold_counter.get(scaffold, 0) + 1

    unique_scaffolds = int(len(scaffold_counter))
    singleton_scaffolds = int(sum(1 for count in scaffold_counter.values() if count == 1))
    largest_scaffold_size = int(max(scaffold_counter.values(), default=0))
    top_10 = sum(sorted(scaffold_counter.values(), reverse=True)[:10])
    proportion_in_largest_10_scaffolds = float(top_10 / total_molecules) if total_molecules else 0.0

    summary = pd.DataFrame([
        {
            "total_molecules": total_molecules,
            "unique_scaffolds": unique_scaffolds,
            "scaffold_free_molecules": scaffold_free_molecules,
            "singleton_scaffolds": singleton_scaffolds,
            "largest_scaffold_size": largest_scaffold_size,
            "proportion_in_largest_10_scaffolds": proportion_in_largest_10_scaffolds,
        }
    ])

    counts = pd.DataFrame(
        [
            {"scaffold_smiles": scaffold, "count": count}
            for scaffold, count in sorted(scaffold_counter.items(), key=lambda item: (-item[1], item[0]))
        ]
    )
    if not counts.empty:
        counts["proportion"] = counts["count"] / total_molecules if total_molecules else 0.0
    else:
        counts["proportion"] = pd.Series(dtype=float)

    return summary, counts
