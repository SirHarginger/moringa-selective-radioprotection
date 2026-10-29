"""Regression tests for scripts/verify_run_consistency.py.

SYNTHETIC DATA ONLY: the manifests, configurations and QC tables below are invented in
memory and written to pytest's temporary directory. No model is fitted and no real run is
read (no ``model_fit`` marker).

The bug these tests pin down: preflight used to load the candidate's ``run_manifest.json``
before any check ran, so ``--pre`` failed with FileNotFoundError for exactly the case it
exists to serve -- a run that has not happened yet.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = "primary_v1"
CANDIDATE = "exploratory_m3_v1"


def load_script(name: str = "verify_run_consistency") -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script() -> ModuleType:
    return load_script()


# ------------------------------------------------------------------ synthetic fixtures


def base_config(run_id: str, models: list[str] | None = None, **overrides: Any) -> dict:
    """SYNTHETIC configuration with the split-determining keys the checker compares."""
    config = {
        "run_id": run_id,
        "inputs": {
            "qc_dir": "qc",
            "qc_sha256": {"eligibility.csv": "a" * 64},
            "clarifi": "data/raw/CLARIFi.csv",
        },
        "population": "primary",
        "population_options": {"min_components_per_tissue": 10},
        "tier": "within",
        "models": models if models is not None else ["M0", "M1", "M2", "M3"],
        "validation": {"k_outer": 5, "k_inner": 5, "repeats": 10},
        "seeds": {"base_seed": 20261021},
        "fit": {"component_weighting": True},
        "predictions": {"clip_raw_to_unit_interval": True},
    }
    config.update(overrides)
    return config


def write_qc(project_root: Path, n_records: int = 8, n_grouped: int = 1) -> None:
    """SYNTHETIC QC eligibility table: n_records eligible rows plus two ineligible ones.

    ``n_grouped`` components hold two records each, so the component count is
    ``n_records - n_grouped``.
    """
    rows = []
    row_number = 0
    for index in range(n_records - n_grouped):
        rows.append((row_number, f"G:ACH:{index:04d}", "True"))
        row_number += 1
    for index in range(n_grouped):  # a second record for the first components
        rows.append((row_number, f"G:ACH:{index:04d}", "True"))
        row_number += 1
    for index in range(2):  # ineligible rows must be ignored by the planned cohort
        rows.append((row_number, f"G:ACH:X{index}", "False"))
        row_number += 1
    table = pd.DataFrame(rows, columns=["row_number", "component_id", "eligible_primary"])
    qc = project_root / "qc"
    qc.mkdir(parents=True, exist_ok=True)
    table.to_csv(qc / "eligibility.csv", index=False)


def synthetic_splits(swap_folds: bool = False) -> pd.DataFrame:
    """SYNTHETIC grouped split table over the 8 eligible rows written by ``write_qc``.

    Rows 0 and 7 share component ``G:ACH:0000``, so they always sit on the same side of
    every outer fold and in the same inner fold: the table satisfies the grouping checks,
    so a negative test fails only on the property it is targeting. ``swap_folds`` returns
    a genuinely different but equally valid table, for the differing-splits test.
    """
    groups = {0: [0, 7, 1], 1: [2, 3, 4, 5, 6]}
    rows = []
    for fold, test_rows in groups.items():
        train_rows = [r for r in range(8) if r not in test_rows]
        outer = (1 - fold) if swap_folds else fold
        for row in test_rows:
            rows.append((0, outer, row, "test", -1))
        for row in train_rows:
            # component G:ACH:0000 (rows 0 and 7) must share one inner fold
            inner = 0 if row in (0, 7) else row % 2
            rows.append((0, outer, row, "train", inner))
    return pd.DataFrame(
        rows, columns=["repeat", "outer_fold", "row_number", "role", "inner_fold"]
    ).sort_values(["repeat", "outer_fold", "row_number"], ignore_index=True)


def write_manifest(
    models_root: Path, run_id: str, config: dict, splits_sha: str = "s" * 64
) -> Path:
    """SYNTHETIC run manifest plus a splits file whose hash matches what it records."""
    from radiosensitivity_ml.data.provenance import file_sha256

    run_dir = models_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    synthetic_splits().to_parquet(run_dir / "splits.parquet", index=False)
    actual = file_sha256(run_dir / "splits.parquet")
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "config": config,
                "config_sha256": "c" * 64,
                "inputs_sha256": {"data/raw/CLARIFi.csv": "d" * 64},
                "splits_sha256": splits_sha if splits_sha != "s" * 64 else actual,
                "tasks": [],
                "task_details": {},
            }
        ),
        encoding="utf-8",
    )
    return run_dir


def task_key(run_dir: Path, model: str) -> str:
    """A 20-character key that differs per run, as the real store's keys do.

    The real key hashes the run context (configuration, code, inputs, splits), so two runs
    with different configurations never share a key for the same fit. The synthetic keys
    mirror that, so the tests exercise key reconciliation rather than assuming it away.
    """
    return hashlib.sha256(f"{run_dir.name}|{model}".encode()).hexdigest()[:20]


def write_task_predictions(
    run_dir: Path,
    model: str,
    y_pred: float,
    rows: tuple[int, ...] = (0, 1),
    y_true: tuple[float, ...] = (0.5, 0.6),
    key: str | None = None,
) -> str:
    """SYNTHETIC per-task predictions in the layout RunStore.load_predictions reads.

    One real-variant task for ``model``, written where the run store expects it, so that
    the shared-model consistency check exercises the project's own checkpoint API.
    """
    key = key or task_key(run_dir, model)
    manifest_path = run_dir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["tasks"] = [*manifest.get("tasks", []), key]
    manifest.setdefault("task_details", {})[key] = ["raw", model, 0, 0, "real", 1]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    folder = run_dir / "tasks" / key
    folder.mkdir(parents=True, exist_ok=True)
    n = len(rows)
    pd.DataFrame(
        {
            "model_id": [model] * n,
            "scale": ["raw"] * n,
            "variant": ["real"] * n,
            "repeat": [0] * n,
            "outer_fold": [0] * n,
            "row_number": list(rows),
            "y_true": list(y_true[:n]),
            "y_pred": [y_pred] * n,
        }
    ).to_parquet(folder / "predictions.parquet", index=False)
    return key


@pytest.fixture
def project(tmp_path: Path) -> dict[str, Path]:
    """A synthetic project: QC table, configs folder, models folder with the reference."""
    write_qc(tmp_path)
    configs = tmp_path / "configs"
    configs.mkdir()
    models = tmp_path / "results" / "models"
    models.mkdir(parents=True)
    write_manifest(models, REFERENCE, base_config(REFERENCE, models=["M0", "M1", "M2"]))
    return {"root": tmp_path, "configs": configs, "models": models}


def run_checker(script: ModuleType, project: dict[str, Path], *extra: str) -> int:
    return script.main(
        [
            "--reference", REFERENCE,
            "--candidate", CANDIDATE,
            "--models-root", str(project["models"]),
            "--configs-root", str(project["configs"]),
            "--project-root", str(project["root"]),
            "--expect-records", "8",
            "--expect-components", "7",
            *extra,
        ]
    )  # fmt: skip


# ----------------------------------------------- 1  preflight before the candidate exists


def test_preflight_passes_before_the_candidate_directory_exists(
    script: ModuleType, project: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """The regression: --pre must work with no candidate output whatsoever."""
    (project["configs"] / "experiment_exploratory_m3.yaml").write_text(
        yaml.safe_dump(base_config(CANDIDATE)), encoding="utf-8"
    )
    assert not (project["models"] / CANDIDATE).exists()
    assert run_checker(script, project, "--pre") == 0
    out = capsys.readouterr().out
    assert "preflight from" in out and "no candidate output read" in out
    assert "1 cohort (planned)" in out and "8 records / 7 components" in out
    assert "2 grouping key" in out and "3 split configuration" in out
    # deferred checks are named, not silently skipped, and not counted as passed
    assert "DEFERRED" in out
    for deferred in ("3 splits identical", "7 shared predictions", "10 completeness"):
        assert deferred in out
    assert "deferred and NOT yet verified" in out
    assert not (project["models"] / CANDIDATE).exists(), "preflight must create nothing"


def test_preflight_discovers_the_config_by_run_id(
    script: ModuleType, project: dict[str, Path]
) -> None:
    """The documented command passes no --candidate-config, so discovery must work."""
    (project["configs"] / "some_other_name.yaml").write_text(
        yaml.safe_dump(base_config(CANDIDATE)), encoding="utf-8"
    )
    assert run_checker(script, project, "--pre") == 0


def test_preflight_reports_a_missing_or_ambiguous_config(
    script: ModuleType, project: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_checker(script, project, "--pre") == 2
    assert "declares run_id" in capsys.readouterr().err
    for name in ("a.yaml", "b.yaml"):
        (project["configs"] / name).write_text(
            yaml.safe_dump(base_config(CANDIDATE)), encoding="utf-8"
        )
    assert run_checker(script, project, "--pre") == 2
    assert "several configurations" in capsys.readouterr().err


# --------------------------------------- 2  preflight detects incompatible configurations


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"seeds": {"base_seed": 1}}, "3 split configuration"),
        ({"validation": {"k_outer": 10, "k_inner": 5, "repeats": 10}}, "3 split configuration"),
        ({"population": "all_records"}, "3 split configuration"),
        ({"tier": "loto"}, "3 split configuration"),
        ({"validation": {"k_outer": 5, "k_inner": 1, "repeats": 10}}, "6 leakage protections"),
        ({"fit": {"component_weighting": False}}, "6 leakage protections"),
        ({"predictions": {"clip_raw_to_unit_interval": False}}, "6 leakage protections"),
    ],
)
def test_preflight_rejects_an_incompatible_configuration(
    script: ModuleType,
    project: dict[str, Path],
    capsys: pytest.CaptureFixture[str],
    overrides: dict,
    expected: str,
) -> None:
    config = base_config(CANDIDATE)
    config.update(overrides)
    (project["configs"] / "candidate.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    assert run_checker(script, project, "--pre") == 1
    out = capsys.readouterr().out
    assert any(line.startswith("FAIL") and expected in line for line in out.splitlines()), out


def test_preflight_rejects_missing_model_identifiers(
    script: ModuleType, project: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """M3 must be comparable with M0, M1 and M2 on the same splits."""
    (project["configs"] / "candidate.yaml").write_text(
        yaml.safe_dump(base_config(CANDIDATE, models=["M3"])), encoding="utf-8"
    )
    assert run_checker(script, project, "--pre") == 1
    out = capsys.readouterr().out
    assert "MISSING required" in out and "6b model identifiers" in out


def test_preflight_rejects_a_wrong_cohort_and_a_degenerate_grouping(
    script: ModuleType, project: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    write_qc(project["root"], n_records=5, n_grouped=0)  # 5 records, no grouped component
    (project["configs"] / "candidate.yaml").write_text(
        yaml.safe_dump(base_config(CANDIDATE)), encoding="utf-8"
    )
    assert run_checker(script, project, "--pre") == 1
    out = capsys.readouterr().out
    assert "1 cohort (planned)" in out and "5 records / 5 components" in out
    assert any("FAIL" in line and "2 grouping key" in line for line in out.splitlines())


def test_preflight_rejects_an_unexpected_run_id(
    script: ModuleType, project: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    (project["configs"] / "candidate.yaml").write_text(
        yaml.safe_dump(base_config(CANDIDATE)), encoding="utf-8"
    )
    code = script.main(
        [
            "--reference", REFERENCE,
            "--candidate", CANDIDATE,
            "--candidate-config", str(project["configs"] / "candidate.yaml"),
            "--models-root", str(project["models"]),
            "--configs-root", str(project["configs"]),
            "--project-root", str(project["root"]),
            "--expect-records", "8", "--expect-components", "7",
            "--pre",
        ]
    )  # fmt: skip
    assert code == 0
    # a configuration whose run_id is not the candidate must be refused
    mismatched = base_config("something_else")
    (project["configs"] / "mismatched.yaml").write_text(
        yaml.safe_dump(mismatched), encoding="utf-8"
    )
    code = script.main(
        [
            "--reference", REFERENCE,
            "--candidate", CANDIDATE,
            "--candidate-config", str(project["configs"] / "mismatched.yaml"),
            "--models-root", str(project["models"]),
            "--configs-root", str(project["configs"]),
            "--project-root", str(project["root"]),
            "--expect-records", "8", "--expect-components", "7",
            "--pre",
        ]
    )  # fmt: skip
    assert code == 1
    assert "does not match --candidate" in capsys.readouterr().out


# ------------------------------------- 3  post-run rejects missing candidate outputs


def test_post_run_requires_the_candidate_manifest(
    script: ModuleType, project: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """Without --pre the candidate's own outputs are mandatory, never inferred."""
    (project["configs"] / "candidate.yaml").write_text(
        yaml.safe_dump(base_config(CANDIDATE)), encoding="utf-8"
    )
    assert run_checker(script, project) == 2
    err = capsys.readouterr().err
    assert "candidate run" in err and "use --pre" in err


def test_post_run_requires_the_reference_manifest(
    script: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    models = tmp_path / "results" / "models"
    models.mkdir(parents=True)
    code = script.main(
        ["--reference", REFERENCE, "--candidate", CANDIDATE, "--models-root", str(models)]
    )
    assert code == 2 and "reference run" in capsys.readouterr().err


# ------------------------------ post-run happy path and shared-prediction consistency


def complete_candidate(project: dict[str, Path], y_pred: float = 0.42) -> Path:
    """A candidate that matches the reference in every verifiable respect."""
    write_task_predictions(project["models"] / REFERENCE, "M2", 0.42)
    run_dir = write_manifest(project["models"], CANDIDATE, base_config(CANDIDATE))
    write_task_predictions(run_dir, "M2", y_pred)
    (run_dir / "run_status.json").write_text(
        json.dumps({"status": "complete", "n_tasks": 1, "counts": {"computed": 1, "failed": 0}}),
        encoding="utf-8",
    )
    return run_dir


def test_post_run_passes_for_a_consistent_candidate(
    script: ModuleType, project: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """Exercises the real RunStore API: splits, predictions, status, all consistent."""
    complete_candidate(project)
    code = run_checker(script, project)
    out = capsys.readouterr().out
    assert code == 0, out
    assert "8 records / 7 components" in out
    for passing in ("3 splits identical", "7 shared predictions", "10 completeness"):
        assert any(line.startswith("PASS") and passing in line for line in out.splitlines()), (
            f"{passing} did not pass:\n{out}"
        )
    assert "DEFERRED" not in out, "the post-run check defers nothing"


def test_post_run_reconciles_different_task_keys(
    script: ModuleType, project: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """THE REGRESSION. Two runs never share a task key for the same fit, because the key
    hashes the run context (configuration, code, inputs, splits). Predictions must still
    be reconciled, on their scientific identifiers."""
    complete_candidate(project)
    reference_key = task_key(project["models"] / REFERENCE, "M2")
    candidate_key = task_key(project["models"] / CANDIDATE, "M2")
    assert reference_key != candidate_key, "the fixture must model run-scoped keys"
    assert (project["models"] / REFERENCE / "tasks" / reference_key).is_dir()
    assert (project["models"] / CANDIDATE / "tasks" / candidate_key).is_dir()

    assert run_checker(script, project) == 0
    out = capsys.readouterr().out
    assert any(
        line.startswith("PASS") and "7 shared predictions" in line for line in out.splitlines()
    ), out
    # the message must say what was matched, and must not mention task keys
    assert "matched one-to-one on" in out and "bitwise identical" in out
    assert "model_id+scale+variant+repeat+outer_fold+row_number" in out
    assert "different task keys" not in out


def test_post_run_detects_differing_shared_predictions(
    script: ModuleType, project: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """A model shared with the frozen run must reproduce it bit for bit, and a genuine
    disagreement must be reported with its magnitude rather than tolerated."""
    complete_candidate(project, y_pred=0.99)  # reference holds 0.42
    assert run_checker(script, project) == 1
    out = capsys.readouterr().out
    assert any(
        line.startswith("FAIL") and "7 shared predictions" in line for line in out.splitlines()
    ), out
    assert "2 of 2 predictions differ" in out
    assert "largest absolute difference" in out and "5.700e-01" in out
    assert "bitwise" in out and "rather than accepting a tolerance" in out


def test_post_run_detects_a_tiny_numerical_difference(
    script: ModuleType, project: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """No silent tolerance: a difference in the last bits still fails, with its size."""
    complete_candidate(project, y_pred=0.42 + 1e-12)
    assert run_checker(script, project) == 1
    out = capsys.readouterr().out
    assert "predictions differ" in out and "largest absolute difference" in out


def test_post_run_detects_duplicate_held_out_identifiers(
    script: ModuleType, project: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """One record may be predicted only once per model, repeat and fold.

    Both runs get two tasks, so the task counts agree and the duplicate check is the one
    that must catch the problem: the candidate's second task re-predicts rows 0 and 1.
    """
    run_dir = complete_candidate(project)
    write_task_predictions(
        project["models"] / REFERENCE, "M2", 0.42, rows=(2, 3), y_true=(0.7, 0.8),
        key="refsecondfold000000",
    )  # fmt: skip
    write_task_predictions(run_dir, "M2", 0.42, key="duplicate0000000000")
    assert run_checker(script, project) == 1
    out = capsys.readouterr().out
    assert "duplicate held-out identifiers in the candidate run" in out


def test_post_run_detects_partial_coverage(
    script: ModuleType, project: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """Fewer held-out predictions than the frozen run is a missing-task failure."""
    write_task_predictions(project["models"] / REFERENCE, "M2", 0.42)
    run_dir = write_manifest(project["models"], CANDIDATE, base_config(CANDIDATE))
    write_task_predictions(run_dir, "M2", 0.42, rows=(0,), y_true=(0.5,))
    (run_dir / "run_status.json").write_text(
        json.dumps({"status": "complete", "n_tasks": 1, "counts": {"computed": 1, "failed": 0}}),
        encoding="utf-8",
    )
    assert run_checker(script, project) == 1
    out = capsys.readouterr().out
    assert "coverage is not one to one" in out
    assert "only in the reference run" in out


def test_post_run_detects_differing_observed_outcomes(
    script: ModuleType, project: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """Identical identifiers must carry identical measured outcomes, or it is not the
    same data and no prediction comparison is meaningful."""
    write_task_predictions(project["models"] / REFERENCE, "M2", 0.42)
    run_dir = write_manifest(project["models"], CANDIDATE, base_config(CANDIDATE))
    write_task_predictions(run_dir, "M2", 0.42, y_true=(0.5, 0.9))
    (run_dir / "run_status.json").write_text(
        json.dumps({"status": "complete", "n_tasks": 1, "counts": {"computed": 1, "failed": 0}}),
        encoding="utf-8",
    )
    assert run_checker(script, project) == 1
    out = capsys.readouterr().out
    assert "held-out observed outcomes differ" in out


def test_post_run_detects_an_unequal_task_count(
    script: ModuleType, project: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """A model fitted in fewer folds in one run is a missing-task failure, not a match."""
    write_task_predictions(project["models"] / REFERENCE, "M2", 0.42)
    write_task_predictions(
        project["models"] / REFERENCE, "M2", 0.42, rows=(2, 3), y_true=(0.7, 0.8),
        key="extrafold0000000000",
    )  # fmt: skip
    run_dir = write_manifest(project["models"], CANDIDATE, base_config(CANDIDATE))
    write_task_predictions(run_dir, "M2", 0.42)
    (run_dir / "run_status.json").write_text(
        json.dumps({"status": "complete", "n_tasks": 1, "counts": {"computed": 1, "failed": 0}}),
        encoding="utf-8",
    )
    assert run_checker(script, project) == 1
    out = capsys.readouterr().out
    assert "tasks in the reference run but" in out


def test_post_run_detects_missing_task_predictions(
    script: ModuleType, project: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """A task recorded in the manifest but absent on disk is a failure, not a crash."""
    run_dir = complete_candidate(project)
    for parquet in (run_dir / "tasks").rglob("predictions.parquet"):
        parquet.unlink()
    assert run_checker(script, project) == 1
    out = capsys.readouterr().out
    assert any(
        line.startswith("FAIL") and "7 shared predictions" in line for line in out.splitlines()
    ), out
    assert "missing predictions" in out


# --------------------------------------- 4  post-run detects incompatible split hashes


def test_post_run_detects_incompatible_split_hashes(
    script: ModuleType, project: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """A candidate whose realised splits differ from the frozen run must be rejected."""
    candidate = base_config(CANDIDATE)
    run_dir = write_manifest(project["models"], CANDIDATE, candidate)
    # give the candidate a genuinely different split table, then record its real hash
    from radiosensitivity_ml.data.provenance import file_sha256

    # a valid but different split table, so only the hash comparison fails
    synthetic_splits(swap_folds=True).to_parquet(run_dir / "splits.parquet", index=False)
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    manifest["splits_sha256"] = file_sha256(run_dir / "splits.parquet")
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    assert run_checker(script, project) == 1
    out = capsys.readouterr().out
    assert any(
        line.startswith("FAIL") and "3 splits identical" in line for line in out.splitlines()
    ), out
    assert "DIFFER" in out


def test_post_run_detects_a_corrupted_split_table(
    script: ModuleType, project: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """A split table that no longer matches its recorded hash is a provenance failure."""
    run_dir = write_manifest(project["models"], CANDIDATE, base_config(CANDIDATE))
    pd.DataFrame({"repeat": [9], "outer_fold": [9], "row_number": [9], "role": ["test"],
                  "inner_fold": [-1]}).to_parquet(run_dir / "splits.parquet", index=False)  # fmt: skip
    assert run_checker(script, project) == 1
    out = capsys.readouterr().out
    # an explicit failed verification, not a propagated exception
    assert any(
        line.startswith("FAIL") and "splits readable" in line for line in out.splitlines()
    ), out
    assert "CheckpointError" in out and "differs from the hash" in out


def test_post_run_detects_differing_input_checksums(
    script: ModuleType, project: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    run_dir = write_manifest(project["models"], CANDIDATE, base_config(CANDIDATE))
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    manifest["inputs_sha256"] = {"data/raw/CLARIFi.csv": "e" * 64}
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert run_checker(script, project) == 1
    out = capsys.readouterr().out
    assert any(
        line.startswith("FAIL") and "4 input checksums" in line for line in out.splitlines()
    ), out


def test_post_run_flags_an_incomplete_candidate(
    script: ModuleType, project: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    run_dir = write_manifest(project["models"], CANDIDATE, base_config(CANDIDATE))
    (run_dir / "run_status.json").write_text(
        json.dumps({"status": "running", "n_tasks": 200, "counts": {"computed": 10, "failed": 2}}),
        encoding="utf-8",
    )
    assert run_checker(script, project) == 1
    out = capsys.readouterr().out
    assert any(
        line.startswith("FAIL") and "10 completeness" in line for line in out.splitlines()
    ), out


# ------------------------------------------------- the real configuration must preflight


@pytest.mark.skipif(
    not (ROOT / "results" / "models" / REFERENCE / "run_manifest.json").is_file(),
    reason="the frozen primary run is not present in this checkout",
)
def test_the_real_m3_configuration_preflights_against_the_real_primary(
    script: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    """End to end on the real artefacts: the documented command must succeed."""
    code = script.main(
        [
            "--reference", REFERENCE,
            "--candidate", CANDIDATE,
            "--candidate-config", str(ROOT / "configs" / "experiment_exploratory_m3.yaml"),
            "--pre",
        ]
    )  # fmt: skip
    out = capsys.readouterr().out
    assert code == 0, out
    assert "241 records / 237 components" in out
