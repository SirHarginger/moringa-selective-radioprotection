"""Run manifests and task checkpoints for genuine ``--resume`` (spec §Resume).

Layout of ``<output_dir>/<run_id>/``::

    run_manifest.json      frozen at first start (config, code, inputs, splits, packages,
                           thread settings, task keys)
    splits.parquet         written and hashed BEFORE any outcome value is loaded
    tasks/<key>/           predictions.parquet, model.joblib, task_record.json, DONE
    tasks/<key>.partial/   a task being written (discarded on resume)
    _rejected/             corrupted task folders moved aside on resume (never deleted)
    failures.jsonl         one line per failed task attempt

A task folder is complete only if DONE holds the SHA-256 of task_record.json, which in
turn holds the SHA-256 of predictions.parquet and model.joblib. Folders are renamed into
place only when complete, so a crash never leaves a half-written task under its key.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import traceback
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from radiosensitivity_ml.data.provenance import file_sha256

THREAD_VARIABLES = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")
PREDICTION_COLUMNS = (
    "row_number", "depmap_id", "component_id", "lineage", "scale", "model_id",
    "variant", "repeat", "outer_fold", "y_true", "y_pred",
)  # fmt: skip


class CheckpointError(RuntimeError):
    """Raised for an incompatible run folder or a corrupted checkpoint."""


@dataclass(frozen=True)
class Task:
    """One unit of work: fit on the outer-training rows, predict the outer-test rows."""

    scale: str
    model_id: str
    repeat: int
    fold: int
    variant: str  # "real", "perm_0003", "randsets_0007"
    seed: int
    key: str


def stable_int(*parts: object) -> int:
    """Deterministic 32-bit integer from its parts (used for seeds)."""
    digest = hashlib.sha256("|".join(map(str, parts)).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def make_task(
    context_sha256: str, base_seed: int, scale: str, model_id: str, repeat: int, fold: int,
    variant: str = "real",
) -> Task:  # fmt: skip
    """Task with its seed (from the base seed and its coordinates, never from the key)
    and its key (from everything that determines its result)."""
    seed = stable_int(base_seed, scale, model_id, repeat, fold, variant)
    key = hashlib.sha256(
        "|".join(map(str, (context_sha256, scale, model_id, repeat, fold, variant, seed))).encode()
    ).hexdigest()[:20]
    return Task(scale, model_id, repeat, fold, variant, seed, key)


def atomic_write_text(path: Path, text: str) -> None:
    """Write text via a temporary file and an atomic rename."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def environment_record() -> dict[str, object]:
    """Package versions and thread settings that can change numerical results."""
    import platform

    import joblib
    import numpy
    import pandas
    import pyarrow
    import scipy
    import sklearn

    return {
        "python": platform.python_version(),
        "packages": {
            "numpy": numpy.__version__,
            "pandas": pandas.__version__,
            "scipy": scipy.__version__,
            "scikit-learn": sklearn.__version__,
            "joblib": joblib.__version__,
            "pyarrow": pyarrow.__version__,
        },
        "threads": {name: os.environ.get(name) for name in THREAD_VARIABLES},
        "n_jobs": 1,
    }


COMPARED_FIELDS = (
    "config_sha256", "code_sha256", "inputs_sha256", "splits_sha256", "environment", "tasks",
)  # fmt: skip


class RunStore:
    """File-system store for one run."""

    def __init__(self, root: Path):
        self.root = root
        self.manifest_path = root / "run_manifest.json"
        self.splits_path = root / "splits.parquet"
        self.tasks_dir = root / "tasks"
        self.rejected_dir = root / "_rejected"
        self.failures_path = root / "failures.jsonl"

    # ---------------------------------------------------------------- manifest

    def create(self, manifest: Mapping[str, object]) -> None:
        """Start a new run folder. Never reuses an existing folder."""
        if self.root.exists():
            raise CheckpointError(
                f"{self.root} already exists. Use --resume to continue it, or choose a new run_id."
            )
        self.tasks_dir.mkdir(parents=True)
        atomic_write_text(self.manifest_path, json.dumps(manifest, indent=2, sort_keys=True))

    def load_manifest(self) -> dict[str, object]:
        if not self.manifest_path.is_file():
            raise CheckpointError(f"{self.root} has no run_manifest.json; cannot resume")
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def incompatibilities(self, manifest: Mapping[str, object]) -> list[str]:
        """Fields that differ between the stored manifest and the current one."""
        stored = self.load_manifest()
        return [f for f in COMPARED_FIELDS if stored.get(f) != manifest.get(f)]

    # ------------------------------------------------------------------ splits

    def save_splits(self, splits: pd.DataFrame) -> str:
        """Write the split table once and return its SHA-256."""
        if self.splits_path.exists():
            raise CheckpointError(f"{self.splits_path} already exists")
        tmp = self.splits_path.with_name("splits.parquet.tmp")
        splits.to_parquet(tmp, index=False)
        os.replace(tmp, self.splits_path)
        return file_sha256(self.splits_path)

    def load_splits(self, expected_sha256: str) -> pd.DataFrame:
        """Read the frozen split table after verifying its hash (never regenerated)."""
        if file_sha256(self.splits_path) != expected_sha256:
            raise CheckpointError("splits.parquet differs from the hash in run_manifest.json")
        return pd.read_parquet(self.splits_path)

    # ------------------------------------------------------------------- tasks

    def task_dir(self, task: Task) -> Path:
        return self.tasks_dir / task.key

    def is_complete(self, task: Task, expected_rows: set[int]) -> bool:
        """True only if the task folder passes every integrity check."""
        folder = self.task_dir(task)
        try:
            done = (folder / "DONE").read_text(encoding="utf-8").strip()
            if done != file_sha256(folder / "task_record.json"):
                return False
            record = json.loads((folder / "task_record.json").read_text(encoding="utf-8"))
            if record["task"] != asdict(task):
                return False
            for name in ("predictions.parquet", "model.joblib"):
                if file_sha256(folder / name) != record["sha256"][name]:
                    return False
            predictions = pd.read_parquet(folder / "predictions.parquet")
            if tuple(predictions.columns) != PREDICTION_COLUMNS:
                return False
            return set(predictions["row_number"]) == expected_rows
        except (OSError, KeyError, ValueError, json.JSONDecodeError):
            return False

    def write_task(
        self,
        task: Task,
        predictions: pd.DataFrame,
        model: object,
        details: Mapping[str, object],
    ) -> None:
        """Write a finished task atomically (staging folder, DONE last, rename)."""
        import joblib

        if tuple(predictions.columns) != PREDICTION_COLUMNS:
            raise CheckpointError(f"prediction columns {list(predictions.columns)} are invalid")
        final = self.task_dir(task)
        if final.exists():
            raise CheckpointError(f"{final} exists; refusing to overwrite a task")
        staging = final.with_name(final.name + ".partial")
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir()
        predictions.to_parquet(staging / "predictions.parquet", index=False)
        joblib.dump(model, staging / "model.joblib")
        record = {
            "task": asdict(task),
            "finished_utc": datetime.now(UTC).isoformat(),
            "sha256": {
                name: file_sha256(staging / name)
                for name in ("predictions.parquet", "model.joblib")
            },
            **details,
        }
        (staging / "task_record.json").write_text(
            json.dumps(record, indent=2, sort_keys=True, default=str), encoding="utf-8"
        )
        (staging / "DONE").write_text(file_sha256(staging / "task_record.json"), encoding="utf-8")
        os.replace(staging, final)

    def discard_partials(self) -> int:
        """Remove staging folders left by an interrupted run; return how many."""
        count = 0
        for folder in self.tasks_dir.glob("*.partial"):
            shutil.rmtree(folder)
            count += 1
        return count

    def reject(self, task: Task) -> Path:
        """Move a corrupted task folder aside (kept for inspection, never deleted)."""
        self.rejected_dir.mkdir(exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        target = self.rejected_dir / f"{task.key}_{stamp}"
        os.replace(self.task_dir(task), target)
        return target

    def record_failure(self, task: Task, exc: BaseException, trace: str | None = None) -> None:
        """Append a failure; ``trace`` is the traceback text of an error raised elsewhere
        (a worker process), otherwise the exception being handled here is used."""
        line = {
            "utc": datetime.now(UTC).isoformat(),
            "task": asdict(task),
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc() if trace is None else trace,
        }
        with self.failures_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line) + "\n")

    def load_predictions(self, keys: list[str]) -> pd.DataFrame:
        """All predictions of the given task keys (each must be complete)."""
        frames = [pd.read_parquet(self.tasks_dir / key / "predictions.parquet") for key in keys]
        return pd.concat(frames, ignore_index=True)
