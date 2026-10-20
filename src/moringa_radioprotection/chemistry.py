from __future__ import annotations

from typing import Any

from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")


def normalize_smiles_value(value: Any) -> str | None:
    """Trim and normalize missing SMILES strings while preserving original content."""
    if value is None:
        return None

    if isinstance(value, str):
        cleaned = value.strip()
    else:
        cleaned = str(value).strip()

    if cleaned == "" or cleaned.lower() in {"na", "n/a", "nan", "none", "null"}:
        return None
    return cleaned


def canonicalize_smiles(smiles: str | None) -> tuple[bool, str | None, str | None]:
    """Parse a SMILES string and return validity, canonical SMILES, and InChIKey."""
    if smiles is None:
        return False, None, None

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return False, None, None

    canonical = Chem.MolToSmiles(mol, canonical=True)
    inchikey = Chem.MolToInchiKey(mol)
    return True, canonical, inchikey


def parse_numeric_response(series: Any) -> Any:
    """Coerce CellMiner response strings to numeric values, treating missing labels as NaN."""
    if series is None:
        return None

    cleaned = series.astype(str).str.strip()
    cleaned = cleaned.replace({"na": "", "N/A": "", "NA": "", "nan": "", "None": "", "null": ""})
    return cleaned.replace("", float("nan")).astype(float)
