import pandas as pd

from moringa_radioprotection.chemistry import canonicalize_smiles, normalize_smiles_value, parse_numeric_response
from moringa_radioprotection.nci import MissingRequiredColumnsError, validate_expected_columns


def test_parse_numeric_response_handles_missing_strings():
    series = pd.Series(["1.5", "na", "", "-2.0", "N/A"])
    result = parse_numeric_response(series)
    assert result.tolist()[:4] == [1.5, float("nan"), float("nan"), -2.0]


def test_valid_smiles_canonicalization():
    valid, canonical, inchikey = canonicalize_smiles("C1=CC=CC=C1")
    assert valid is True
    assert canonical == "C1=CC=CC=C1"
    assert isinstance(inchikey, str)
    assert len(inchikey) > 0


def test_invalid_smiles_returns_false():
    valid, canonical, inchikey = canonicalize_smiles("not_a_valid_smiles")
    assert valid is False
    assert canonical is None
    assert inchikey is None


def test_validate_expected_columns_raises_for_missing_columns():
    frame = pd.DataFrame({"A": [1], "B": [2]})
    try:
        validate_expected_columns(frame, {"A", "missing_column"})
    except MissingRequiredColumnsError:
        pass
    else:
        raise AssertionError("Expected MissingRequiredColumnsError was not raised")


def test_normalize_smiles_value_handles_missing_tokens():
    assert normalize_smiles_value("  na  ") is None
    assert normalize_smiles_value("CCO") == "CCO"
