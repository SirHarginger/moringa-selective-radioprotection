"""Consistency tests for the French Embassy report source.

These tests read text files only. They fit nothing, read no results and import no plotting
code, so they run anywhere. Their job is to stop the report drifting away from the
configuration and the outputs it describes:

- every figure the report embeds is a configured figure, numbered consistently;
- every caption in the report is byte-identical to the caption in the figure config, so a
  caption can never be edited in one place only;
- every citation key used resolves to an entry in references.bib, and every entry is used;
- the report never claims that an unexecuted output is a completed result;
- forbidden claims (selective radioprotection, demonstrated significance) do not appear.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "french_embassy"
REPORT = REPORT_DIR / "report.md"
BIB = REPORT_DIR / "references.bib"
TABLE_MANIFEST = REPORT_DIR / "table_manifest.csv"
CONFIG = ROOT / "configs" / "figures_report.yaml"

pytestmark = pytest.mark.skipif(not REPORT.is_file(), reason="report source not present")

IMAGE = re.compile(r"!\[(?P<caption>.*?)\]\((?P<path>[^)]*?)\)\{#fig:(?P<label>[^}\s]+)[^}]*\}",
                   re.DOTALL)  # fmt: skip
CITATION = re.compile(r"@([A-Za-z][A-Za-z0-9_:-]*)")
BIB_ENTRY = re.compile(r"^@\w+\{([^,]+),", re.MULTILINE)


def report_text() -> str:
    return REPORT.read_text(encoding="utf-8")


def figure_config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def normalise(text: str) -> str:
    """Collapse whitespace, as the YAML folded captions and the Markdown text differ."""
    return " ".join(text.split())


EMPHASIS = re.compile(r"[*_`]+")
# Words that turn a phrase into a denial. A scientific report must be able to say
# "these are not validated biomarkers" without tripping a check that looks for the bare
# phrase "validated biomarker"; the limitation is the point of the sentence.
NEGATORS = (
    "no ", "not ", "never ", "cannot ", "can not ", "nor ", "without ", "neither ",
    "rather than ", "instead of ", "absence of ", "lack of ", "far from ", "none of ",
)  # fmt: skip
NEGATION_WINDOW = 160  # characters of preceding context searched for a negator


def plain_text() -> str:
    """The report with Markdown emphasis markers removed and whitespace collapsed.

    Checks run against this, so that `**not** external validation` reads as
    `not external validation` and a phrase split by bold markers is still found.
    """
    return normalise(EMPHASIS.sub("", report_text())).lower()


def affirmative_occurrences(text: str, phrase: str) -> list[str]:
    """Occurrences of ``phrase`` that are NOT inside a negated or quoted construction.

    Returns the surrounding context of each affirmative occurrence, so a failure message
    can show what was actually asserted.
    """
    found = []
    for match in re.finditer(re.escape(phrase), text):
        start = max(0, match.start() - NEGATION_WINDOW)
        context = text[start : match.start()]
        # the nearest sentence boundary: a negator only applies within the same sentence
        sentence = re.split(r"(?<=[.;:!?])\s", context)[-1]
        if any(negator in sentence for negator in NEGATORS):
            continue
        found.append(text[start : match.end() + 60])
    return found


def embedded_figures() -> list[dict[str, str]]:
    return [m.groupdict() for m in IMAGE.finditer(report_text())]


# ------------------------------------------------------------------- figures and captions


def test_every_embedded_figure_is_a_configured_figure() -> None:
    configured = {e["id"]: e for e in figure_config()["figures"]}
    embedded = embedded_figures()
    assert embedded, "the report embeds no figures"
    for figure in embedded:
        stem = Path(figure["path"]).stem
        matches = [e for e in configured.values() if f"{e['id']}_{e['slug']}" == stem]
        assert matches, f"{stem} is not a configured figure"
        assert figure["path"].endswith(".png")
        assert figure["path"].startswith("../../figures/png/")


def test_every_configured_figure_appears_in_the_report() -> None:
    stems = {Path(f["path"]).stem for f in embedded_figures()}
    for entry in figure_config()["figures"]:
        assert f"{entry['id']}_{entry['slug']}" in stems, f"{entry['id']} is not in the report"


def test_captions_are_identical_to_the_configured_captions() -> None:
    """A caption must never be edited in the report without the config, or the reverse."""
    configured = {f"{e['id']}_{e['slug']}": e for e in figure_config()["figures"]}
    for figure in embedded_figures():
        entry = configured[Path(figure["path"]).stem]
        label = entry["report_label"]
        caption = normalise(figure["caption"])
        prefix = f"**{label}.** "
        assert caption.startswith(prefix), f"{entry['id']}: caption must start with {prefix!r}"
        assert normalise(caption[len(prefix) :]) == normalise(entry["caption"]), (
            f"{entry['id']}: the report caption and configs/figures_report.yaml disagree"
        )


def test_figure_numbers_are_sequential_and_match_the_labels() -> None:
    configured = {f"{e['id']}_{e['slug']}": e for e in figure_config()["figures"]}
    main, supplementary = [], []
    for figure in embedded_figures():
        label = configured[Path(figure["path"]).stem]["report_label"]
        (supplementary if label.startswith("Figure S") else main).append(label)
    assert main == [f"Figure {i}" for i in range(1, len(main) + 1)]
    assert supplementary == [f"Figure S{i}" for i in range(1, len(supplementary) + 1)]


def test_every_figure_is_referenced_in_the_prose() -> None:
    text = report_text()
    configured = {f"{e['id']}_{e['slug']}": e for e in figure_config()["figures"]}
    for figure in embedded_figures():
        label = configured[Path(figure["path"]).stem]["report_label"]
        body = IMAGE.sub("", text)  # the caption itself does not count as a reference
        assert label in body, f"{label} is embedded but never discussed in the text"


# ------------------------------------------------------------------------------ citations


def test_every_citation_key_resolves_to_a_bibliography_entry() -> None:
    keys = set(BIB_ENTRY.findall(BIB.read_text(encoding="utf-8")))
    assert keys, "references.bib has no entries"
    used = {k for k in CITATION.findall(report_text()) if not k.startswith("refs")}
    unresolved = sorted(used - keys)
    assert not unresolved, f"citation keys with no bibliography entry: {unresolved}"


def test_every_bibliography_entry_is_cited() -> None:
    keys = set(BIB_ENTRY.findall(BIB.read_text(encoding="utf-8")))
    used = set(CITATION.findall(report_text()))
    unused = sorted(keys - used)
    assert not unused, f"bibliography entries never cited: {unused}"


def test_no_bibliography_entry_has_a_placeholder_author_list() -> None:
    """`and others` hides an unverified record; four invented or incomplete entries were
    found this way on 2026-10-22, so the check stays."""
    text = BIB.read_text(encoding="utf-8")
    for entry in re.split(r"\n(?=@\w+\{)", text):
        match = BIB_ENTRY.search(entry)
        if not match:
            continue
        authors = re.search(r"author\s*=\s*\{(.*?)\}\s*,\s*\n", entry, re.DOTALL)
        if authors is None:
            continue
        assert "others" not in authors.group(1).lower(), (
            f"{match.group(1)}: placeholder author list; fetch the record and complete it"
        )


def test_every_bibliography_entry_records_its_verification_route() -> None:
    """No citation may enter the report without a recorded verification route."""
    text = BIB.read_text(encoding="utf-8")
    entries = re.split(r"\n(?=@\w+\{)", text)
    for entry in entries:
        match = BIB_ENTRY.search(entry)
        if not match:
            continue
        key = match.group(1)
        assert "note" in entry, f"{key}: no note field"
        lowered = entry.lower()
        assert any(route in lowered for route in ("crossref", "europe pmc", "verified")), (
            f"{key}: the note records no verification route"
        )


def test_the_retracted_paper_is_absent() -> None:
    """Giacoppo et al. 2017 (PMID 28705212) is flagged retracted and must never be cited."""
    for path in (BIB, REPORT):
        text = path.read_text(encoding="utf-8")
        assert "28705212" not in text or "retract" in text.lower(), path
        assert "10.1186/s12906-017-1876-z" not in text, f"{path}: retracted DOI cited"


# ---------------------------------------------------------- honesty about what was run


def test_unexecuted_outputs_are_declared_as_such() -> None:
    """Whatever is genuinely not executed must say so; the negative controls are."""
    text = report_text()
    assert "not executed" in text
    assert "controls_v1" in text, "the unexecuted negative-control run must be named"


def test_completed_analyses_are_not_described_as_pending() -> None:
    """Regression: the report must not still call executed analyses unexecuted.

    The four modelling runs, the compound ranking and the figures are complete, so a
    status of 'not executed' or 'not rendered' beside any of them is a stale statement.
    """
    text = plain_text()
    completed = ("exploratory_m3_v1", "loto_v1", "scales_v1")
    for run in completed:
        for line in text.split(". "):
            if run in line:
                assert "not executed" not in line, f"{run} is complete but reads unexecuted: {line}"
    assert "not rendered" not in text, "the figures are rendered"
    assert "ranked table pending investigator execution" not in text
    # and the real results must be stated
    assert "18 compounds" in text or "18 compounds ranked" in text
    assert "5 in tier a" in text or "five reached tier a" in text


def test_table_manifest_status_matches_the_files_on_disk() -> None:
    """Regression: a manifest row may not claim 'pending_execution' for a file that
    exists, nor 'generated' for one that does not."""
    rows = list(csv.DictReader(TABLE_MANIFEST.read_text(encoding="utf-8").splitlines()))
    assert rows
    statuses = {r["status"] for r in rows}
    assert statuses <= {"generated", "pending_execution"}, statuses
    for row in rows:
        exists = (ROOT / row["path"]).is_file()
        if row["status"] == "generated":
            assert exists, f"{row['table_id']}: marked generated but {row['path']} is absent"
        else:
            assert not exists, (
                f"{row['table_id']}: marked pending_execution but {row['path']} exists; "
                f"update the manifest status"
            )


def test_the_report_makes_no_forbidden_claim() -> None:
    """Claims the project cannot support must not appear AS ASSERTIONS.

    The check is negation-aware on purpose. "They are not validated biomarkers" is a
    required limitation, not a forbidden claim, and the fix for a failure here is to
    correct the claim, never to delete the limitation.
    """
    text = plain_text()
    forbidden = [
        "selective radioprotection",
        "proves that",
        "statistically significant improvement",
        "validated biomarker",
        "moringa radioprotects",
        "radioprotective compound",
        "predicts radiosensitivity",
    ]
    for phrase in forbidden:
        affirmative = affirmative_occurrences(text, phrase)
        assert not affirmative, f"{phrase!r} appears as an affirmative claim: {affirmative[0]!r}"


def test_negated_limitations_are_not_mistaken_for_claims() -> None:
    """Guard on the guard: the negation-aware check must still catch a real claim."""
    assert not affirmative_occurrences("they are not validated biomarkers", "validated biomarker")
    assert not affirmative_occurrences(
        "it is not a gene-level finding, a validated biomarker, or a mechanism",
        "validated biomarker",
    )
    assert affirmative_occurrences("p53 is a validated biomarker of response",
                                   "validated biomarker")  # fmt: skip
    # a negator in an earlier sentence must not excuse a later affirmative claim
    assert affirmative_occurrences(
        "no interval was computed. this is a validated biomarker.", "validated biomarker"
    )


def test_the_report_states_the_key_limitations() -> None:
    lowered = plain_text()
    required = [
        "superiority was not formally assessed",  # no inference
        "no negative control",  # controls missing
        "not external validation",  # repeated CV is not external
        "never used as training",  # Moringa data are motivation only
        "is not clonogenic sf2",  # endpoints kept apart
        "cc by-nc 4.0",  # licence disclosed
    ]
    for phrase in required:
        assert phrase in lowered, f"the report omits the required statement {phrase!r}"


def test_administrative_fields_are_marked_not_invented() -> None:
    text = report_text()
    assert "[TO BE COMPLETED]" in text
    for invented in ("grant number", "funding reference", "approved by the embassy"):
        assert invented not in text.lower(), f"invented administrative detail: {invented!r}"


def test_the_primary_numbers_match_the_saved_outputs() -> None:
    """The headline estimate and its relative size, as reported, must be internally exact."""
    text = report_text()
    assert "0.00383" in text and "2.85%" in text
    assert "0.0038316558867076" in text, "the reconciliation table must show the exact value"
    assert "0.0038170756763974" in text, "the record-weighted variant must be shown too"
    assert "nine of ten" in text.lower()
    # the reconciliation must name the estimand rather than pick the larger number
    assert "different weighting" in text.lower()
