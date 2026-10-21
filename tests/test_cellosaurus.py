"""Unit tests for Cellosaurus response parsing and verification.

SYNTHETIC SOFTWARE-TEST DATA ONLY: every accession, name and identifier below is
invented (CVCL_ZZxx, ACH-9xxxxx) to mimic the verified response FORMAT. None is a
scientific observation. No network access; no models.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from radiosensitivity_ml.data import cellosaurus as cs

HEADER = "\t".join(cs.EXPECTED_COLUMNS)


def synthetic_row(
    ac: str,
    name: str,
    depmap: str = "",
    hi: str = "",
    oi: str = "",
    acas: str = "",
    problematic: str = "",
) -> str:
    """One SYNTHETIC TSV row in the verified column order."""
    dr = f"Other; X1|DepMap; {depmap}" if depmap else "Other; X1"
    values = {
        "id": name,
        "ac": ac,
        "acas": acas or ac,
        "sy": f"{name} syn; {name}-2",
        "dr": dr,
        "hi": hi,
        "oi": oi,
        "ca": "Cancer cell line",
        "problematic": problematic,
        "ox": "NCBI_TaxID=9606; ! Homo sapiens (Human)",
        "dtv": "1",
    }
    return "\t".join(values[c] for c in cs.EXPECTED_COLUMNS)


def synthetic_tsv(rows: list[str], num_found: int | None = None) -> str:
    """A SYNTHETIC TSV response with '##' metadata lines."""
    found = len(rows) if num_found is None else num_found
    meta = ["##   query.q: synthetic", f"##   response.numFound: {found}", ""]
    return "\n".join([*meta, HEADER, *rows]) + "\n"


def test_release_info_parses_verified_structure() -> None:
    text = json.dumps({"Cellosaurus": {"header": {"release": {"version": "99.0", "updated": "x"}}}})
    assert cs.parse_release_info(text)["version"] == "99.0"
    with pytest.raises(cs.CellosaurusFormatError):
        cs.parse_release_info(json.dumps({"release": "99.0"}))


def test_relationships_and_states_are_distinct() -> None:
    text = synthetic_tsv(
        [
            synthetic_row("CVCL_ZZ01", "FAKEA", "ACH-900001", hi="CVCL_ZZ09 ! FAKEPARENT"),
            synthetic_row(
                "CVCL_ZZ02", "FAKEB", "ACH-900002", oi="CVCL_ZZ03 ! FAKEC|CVCL_ZZ04 ! FAKED"
            ),
        ]
    )
    parsed = cs.parse_search_tsv(text)
    a, b = parsed.records
    assert a.parents == (cs.Link("CVCL_ZZ09", "FAKEPARENT"),)
    assert a.parent_status == cs.RECORDED
    assert a.same_individual_status == cs.NONE_RECORDED
    assert [link.accession for link in b.same_individual] == ["CVCL_ZZ03", "CVCL_ZZ04"]
    assert b.depmap_ids == ("ACH-900002",)
    assert a.synonyms == ("FAKEA syn", "FAKEA-2")


def test_missing_relationship_column_is_unavailable_not_absent() -> None:
    columns = [c for c in cs.EXPECTED_COLUMNS if c != "oi"]
    text = (
        "##   response.numFound: 1\n"
        + "\t".join(columns)
        + "\n"
        + "\t".join("CVCL_ZZ01" if c == "ac" else "" for c in columns)
    )
    parsed = cs.parse_search_tsv(text, required_columns=("ac",))
    assert parsed.records[0].same_individual_status == cs.FIELD_UNAVAILABLE
    with pytest.raises(cs.CellosaurusFormatError):  # default: every column is required
        cs.parse_search_tsv(text)


def test_truncated_response_is_rejected() -> None:
    text = synthetic_tsv([synthetic_row("CVCL_ZZ01", "FAKEA", "ACH-900001")], num_found=2)
    with pytest.raises(cs.CellosaurusFormatError, match="truncated"):
        cs.parse_search_tsv(text)


def test_response_without_numfound_is_rejected() -> None:
    with pytest.raises(cs.CellosaurusFormatError):
        cs.parse_search_tsv(HEADER + "\n" + synthetic_row("CVCL_ZZ01", "FAKEA"))


def test_wrong_field_count_and_bad_accessions_are_rejected() -> None:
    with pytest.raises(cs.CellosaurusFormatError):
        cs.parse_search_tsv(synthetic_tsv([synthetic_row("CVCL_ZZ01", "A") + "\textra"]))
    with pytest.raises(cs.CellosaurusFormatError):
        cs.parse_search_tsv(synthetic_tsv([synthetic_row("NOTCVCL", "A")]))
    with pytest.raises(cs.CellosaurusFormatError):
        cs.parse_search_tsv(synthetic_tsv([synthetic_row("CVCL_ZZ01", "A", hi="junk ! X")]))


def test_secondary_accessions_exclude_primary() -> None:
    text = synthetic_tsv([synthetic_row("CVCL_ZZ01", "A", acas="CVCL_ZZ01; CVCL_ZZ99")])
    assert cs.parse_search_tsv(text).records[0].secondary_accessions == ("CVCL_ZZ99",)


def test_merge_records_rejects_conflicts_and_collapses_duplicates() -> None:
    first = cs.parse_search_tsv(synthetic_tsv([synthetic_row("CVCL_ZZ01", "A")])).records[0]
    other = cs.parse_search_tsv(synthetic_tsv([synthetic_row("CVCL_ZZ01", "B")])).records[0]
    assert len(cs.merge_records([first, first])) == 1
    with pytest.raises(cs.CellosaurusFormatError):
        cs.merge_records([first, other])


# ------------------------------------------------------------- saved-folder checks


def write_synthetic_folder(folder: Path, ids: list[str], tamper: str = "") -> None:
    """Write a SYNTHETIC fetch folder in the layout of scripts/fetch_cellosaurus_phase_01.py."""
    folder.mkdir()

    def save(name: str, body: str, status: int = 200) -> str:
        (folder / name).write_text(body)
        digest = hashlib.sha256(body.encode()).hexdigest()
        sidecar = {"sha256": digest, "http_status": status}
        (folder / f"{name}.json").write_text(json.dumps(sidecar))
        return digest

    save(
        "release_info.json",
        json.dumps({"Cellosaurus": {"header": {"release": {"version": "56.0"}}}}),
    )
    body = synthetic_tsv([synthetic_row("CVCL_ZZ01", "FAKEA", ids[0])])
    digest = save("r0_dr_batch001.tsv", body, status=500 if tamper == "status" else 200)
    complete = {
        "status": "complete",
        "depmap_ids_sha256": hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest(),
        "rounds": [{"files": [{"file": "r0_dr_batch001.tsv", "sha256": digest, "num_found": 1}]}],
    }
    if tamper != "no_complete":
        (folder / "COMPLETE.json").write_text(json.dumps(complete))
    if tamper == "extra_file":
        (folder / "stray.tsv").write_text(body)
    if tamper == "modified":
        (folder / "r0_dr_batch001.tsv").write_text(body + "x")


def test_saved_folder_loads_when_complete(tmp_path: Path) -> None:
    write_synthetic_folder(tmp_path / "cello", ["ACH-900001"])
    records, provenance = cs.load_saved_responses(tmp_path / "cello", "56.0", ["ACH-900001"])
    assert list(records) == ["CVCL_ZZ01"]
    assert provenance["n_response_files"] == 1


@pytest.mark.parametrize("tamper", ["no_complete", "extra_file", "modified", "status"])
def test_saved_folder_rejects_incomplete_or_tampered(tmp_path: Path, tamper: str) -> None:
    write_synthetic_folder(tmp_path / "cello", ["ACH-900001"], tamper=tamper)
    with pytest.raises(cs.CellosaurusFormatError):
        cs.load_saved_responses(tmp_path / "cello", "56.0", ["ACH-900001"])


def test_saved_folder_rejects_other_release_or_id_list(tmp_path: Path) -> None:
    write_synthetic_folder(tmp_path / "cello", ["ACH-900001"])
    with pytest.raises(cs.CellosaurusFormatError):
        cs.load_saved_responses(tmp_path / "cello", "57.0", ["ACH-900001"])
    with pytest.raises(cs.CellosaurusFormatError):
        cs.load_saved_responses(tmp_path / "cello", "56.0", ["ACH-900001", "ACH-900002"])
