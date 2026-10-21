"""Tests for the workflow entry points (acquire_data.py, run_preprocessing.py).

SYNTHETIC SOFTWARE-TEST DATA ONLY: no network access (a fake opener serves invented
bytes), no real data files are read, and everything is written under pytest's
tmp_path. No models are run.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import stat
from pathlib import Path
from types import ModuleType
from typing import Self

import pytest

from radiosensitivity_ml.data import acquisition as acq

ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str) -> ModuleType:
    """Import a script from scripts/ without running its main()."""
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    """Minimal stand-in for an HTTP response (SYNTHETIC bytes)."""

    def __init__(self, body: bytes, status: int = 200) -> None:
        self.body, self.status, self.offset = body, status, 0

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self, n: int = -1) -> bytes:
        chunk = self.body[self.offset :] if n < 0 else self.body[self.offset : self.offset + n]
        self.offset += len(chunk)
        return chunk

    def geturl(self) -> str:
        return "https://example.invalid/final"


def opener_for(body: bytes, status: int = 200, calls: list | None = None):
    def opener(url: str) -> FakeResponse:
        if calls is not None:
            calls.append(url)
        return FakeResponse(body, status)

    return opener


BODY = b"ModelID,RRID\nACH-900001,CVCL_ZZ01\n"  # SYNTHETIC


def remote(tmp_path: Path, body: bytes = BODY, **overrides: object) -> acq.RemoteFile:
    fields = {
        "url": "https://example.invalid/file",
        "dest": tmp_path / "raw" / "SYNTHETIC_Model.csv",
        "md5": hashlib.md5(body).hexdigest(),
        "size": len(body),
    }
    fields.update(overrides)
    return acq.RemoteFile(**fields)  # type: ignore[arg-type]


def test_download_is_verified_logged_and_read_only(tmp_path: Path) -> None:
    log = tmp_path / "log.tsv"
    item = remote(tmp_path)
    assert acq.acquire(item, opener_for(BODY), log) == "downloaded"
    assert item.dest.read_bytes() == BODY
    assert not item.dest.stat().st_mode & stat.S_IWUSR
    lines = log.read_text().splitlines()
    assert lines[0].split("\t")[0] == "utc_time" and len(lines) == 2
    assert len(lines[1].split("\t")) == len(lines[0].split("\t")) == 9
    assert lines[1].split("\t")[-1] == hashlib.sha256(BODY).hexdigest()


def test_checksum_mismatch_never_becomes_a_raw_file(tmp_path: Path) -> None:
    item = remote(tmp_path, md5="0" * 32)
    with pytest.raises(acq.AcquisitionError):
        acq.acquire(item, opener_for(BODY), tmp_path / "log.tsv")
    assert not item.dest.exists()
    assert item.dest.with_name(item.dest.name + ".part").exists()


@pytest.mark.parametrize(
    ("body", "status"),
    [(b"<!DOCTYPE html><html>blocked</html>", 200), (BODY, 404)],
)
def test_html_pages_and_http_errors_are_rejected(tmp_path: Path, body: bytes, status: int) -> None:
    item = remote(tmp_path, body=body, md5=None, size=None)
    with pytest.raises(acq.AcquisitionError):
        acq.acquire(item, opener_for(body, status), tmp_path / "log.tsv")
    assert not item.dest.exists()


def test_existing_file_is_verified_not_downloaded_again(tmp_path: Path) -> None:
    item = remote(tmp_path)
    acq.acquire(item, opener_for(BODY), tmp_path / "log.tsv")
    calls: list[str] = []
    assert acq.acquire(item, opener_for(BODY, calls=calls), tmp_path / "log.tsv") == (
        "verified_existing"
    )
    assert calls == []


def test_interrupted_download_restarts_cleanly(tmp_path: Path) -> None:
    item = remote(tmp_path)
    item.dest.parent.mkdir(parents=True)
    item.dest.with_name(item.dest.name + ".part").write_bytes(b"truncated garbage")
    assert acq.acquire(item, opener_for(BODY), tmp_path / "log.tsv") == "downloaded"
    assert item.dest.read_bytes() == BODY


def test_sha256sums_written_once_then_verified(tmp_path: Path) -> None:
    folder = tmp_path / "raw"
    folder.mkdir()
    (folder / "a.csv").write_bytes(b"a")
    assert acq.sha256sums(folder, ["a.csv"]) == "written"
    assert acq.sha256sums(folder, ["a.csv"]) == "verified"
    (folder / "b.csv").write_bytes(b"b")
    with pytest.raises(acq.AcquisitionError):
        acq.sha256sums(folder, ["a.csv", "b.csv"])  # unlisted later file
    os.chmod(folder / "a.csv", stat.S_IWUSR | stat.S_IRUSR)
    (folder / "a.csv").write_bytes(b"changed")
    with pytest.raises(acq.AcquisitionError):
        acq.sha256sums(folder, ["a.csv"])


def test_corrupt_existing_file_is_not_overwritten(tmp_path: Path) -> None:
    item = remote(tmp_path)
    item.dest.parent.mkdir(parents=True)
    item.dest.write_bytes(b"SYNTHETIC wrong content")
    calls: list[str] = []
    with pytest.raises(acq.AcquisitionError, match="NOT overwritten"):
        acq.acquire(item, opener_for(BODY, calls=calls), tmp_path / "log.tsv")
    assert item.dest.read_bytes() == b"SYNTHETIC wrong content" and calls == []


def test_sha256sums_has_no_leftover_staging_file(tmp_path: Path) -> None:
    folder = tmp_path / "raw"
    folder.mkdir()
    (folder / "a.csv").write_bytes(b"a")
    acq.sha256sums(folder, ["a.csv"])
    assert not (folder / "SHA256SUMS.part").exists()
    assert not (folder / "SHA256SUMS").stat().st_mode & stat.S_IWUSR


def test_verify_group_reports_missing_files(tmp_path: Path) -> None:
    report = acq.verify_group([remote(tmp_path)])
    assert set(report.values()) == {"missing"}


def test_default_sources_are_the_24q4_core_files_only() -> None:
    script = load_script("acquire_data")
    args = script.parse_args([])
    assert script.selected_sources(args) == ["depmap_24q4", "msigdb_hallmark"]
    names = sorted(f.dest.name for f in acq.SOURCES["depmap_24q4"])
    assert names == sorted(
        [
            "README.txt",
            "Model.csv",
            "OmicsProfiles.csv",
            "OmicsDefaultModelProfiles.csv",
            "OmicsExpressionProteinCodingGenesTPMLogp1.csv",
        ]
    )
    assert all(f.md5 and f.size for f in acq.SOURCES["depmap_24q4"])
    extra = script.selected_sources(script.parse_args(["--batch-corrected", "--audit-23q4"]))
    assert extra == [
        "depmap_24q4",
        "msigdb_hallmark",
        "depmap_24q4_batch_corrected",
        "depmap_23q4_audit",
    ]


def test_acquire_data_refuses_to_run_outside_the_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = load_script("acquire_data")
    monkeypatch.chdir(tmp_path)
    assert script.main(["--dry-run"]) == 2


def test_check_inputs_reports_each_input(tmp_path: Path) -> None:
    script = load_script("run_preprocessing")
    folder = tmp_path / "depmap"
    folder.mkdir()
    for name in ("Model.csv", "Default.csv", "Profiles.csv"):
        (folder / name).write_text("SYNTHETIC\n")
    acq.sha256sums(folder, ["Model.csv", "Default.csv", "Profiles.csv"])
    (tmp_path / "CLARIFi.csv").write_text("SYNTHETIC\n")
    (tmp_path / "manifest.yaml").write_text("files: []\n")
    config = {
        "inputs": {
            "clarifi": str(tmp_path / "CLARIFi.csv"),
            "clarifi_manifest": str(tmp_path / "manifest.yaml"),
            "model": str(folder / "Model.csv"),
            "default_profiles": str(folder / "Default.csv"),
            "omics_profiles": str(folder / "Profiles.csv"),
            "expression": str(folder / "Expression.csv"),
            "cellosaurus_dir": str(tmp_path / "cellosaurus"),
        },
        "cellosaurus": {"complete_json_sha256": None},
    }
    status = script.check_inputs(config)
    assert status["model"] == "ok"
    assert status["clarifi"].startswith("NO CHECKSUM")  # synthetic manifest lists no files
    assert status["clarifi_manifest"] == "present"
    assert status["expression"].startswith("MISSING")
    assert status["cellosaurus_dir"].startswith("MISSING")
    assert status["cellosaurus.complete_json_sha256"].startswith("NOT RECORDED")
