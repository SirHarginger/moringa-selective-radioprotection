"""Experiment configuration: load, validate and hash ``configs/experiment.yaml``.

The configuration is the single source of every modelling choice (protocol v0.2+):
inputs and their expected hashes, population, outcome scales, models and grids,
validation design, seeds, controls and inference. Unknown keys are rejected so a
typo can never silently change a prespecified choice. The SHA-256 of the canonical
JSON form is recorded in every run manifest.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

SCALES = ("raw", "neglog", "logit")
POPULATIONS = ("primary", "retaining_problematic", "stranded_excluded", "identity_sound")
TIERS = ("within", "loto")
MODEL_IDS = ("M0", "M1", "M1P", "M2", "M2P", "M2X", "M3")
INTERVAL_METHODS = ("nadeau_bengio", "naive_component_t", "not_assessable")

TOP_KEYS = {
    "schema_version", "run_id", "inputs", "population", "population_options", "scales",
    "tier", "models", "grids", "validation", "seeds", "fit", "predictions", "controls",
    "inference", "output_dir",
}  # fmt: skip
OPTIONAL_KEYS = {"controls", "output_dir", "tier", "population_options"}
INPUT_KEYS = {
    "qc_dir", "qc_sha256", "clarifi", "clarifi_manifest", "expression", "gene_sets",
    "gene_sets_sha256",
}  # fmt: skip
INFERENCE_KEYS = {"method", "alpha_one_sided", "bh_q", "decision_file", "decision_sha256"}


class ExperimentConfigError(ValueError):
    """Raised for a missing, unknown or invalid configuration entry."""


@dataclass(frozen=True)
class ExperimentConfig:
    """Validated experiment configuration (see configs/experiment.yaml for meanings)."""

    raw: Mapping[str, object]
    run_id: str
    inputs: Mapping[str, object]
    population: str
    scales: tuple[str, ...]
    tier: str
    models: tuple[str, ...]
    grids: Mapping[str, Mapping[str, list]]
    k_outer: int
    k_inner: int
    repeats: int
    base_seed: int
    component_weighting: bool
    clip_raw_predictions: bool
    controls: Mapping[str, int] = field(default_factory=dict)
    interval_method: str = "not_assessable"
    alpha_one_sided: float = 0.05
    bh_q: float = 0.05
    decision_file: Path | None = None
    decision_sha256: str | None = None
    output_dir: Path = Path("results/models")
    population_options: Mapping[str, object] = field(default_factory=dict)

    @property
    def sha256(self) -> str:
        """SHA-256 of the canonical JSON form of the raw configuration."""
        return config_sha256(self.raw)


def config_sha256(data: Mapping[str, object]) -> str:
    """Hash of a configuration mapping in canonical (sorted, compact) JSON."""
    text = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ExperimentConfigError(message)


def _int(value: object, name: str, minimum: int) -> int:
    _require(isinstance(value, int) and not isinstance(value, bool), f"{name} must be an integer")
    _require(value >= minimum, f"{name} must be >= {minimum}")  # type: ignore[operator]
    return value  # type: ignore[return-value]


def experiment_from_mapping(data: Mapping[str, object]) -> ExperimentConfig:
    """Validate a parsed YAML mapping and build an ExperimentConfig."""
    unknown = set(data) - TOP_KEYS
    _require(not unknown, f"unknown top-level keys: {sorted(unknown)}")
    missing = TOP_KEYS - OPTIONAL_KEYS - set(data)
    _require(not missing, f"missing keys: {sorted(missing)}")
    _require(data["schema_version"] == 1, "schema_version must be 1")
    inputs = dict(data["inputs"])  # type: ignore[call-overload]
    _require(set(inputs) == INPUT_KEYS, f"inputs must have exactly {sorted(INPUT_KEYS)}")
    population = str(data["population"])
    _require(population in POPULATIONS, f"population must be one of {POPULATIONS}")
    scales = tuple(data["scales"])  # type: ignore[arg-type]
    _require(bool(scales) and set(scales) <= set(SCALES), f"scales must be a subset of {SCALES}")
    tier = str(data.get("tier", "within"))
    _require(tier in TIERS, f"tier must be one of {TIERS}")
    models = tuple(data["models"])  # type: ignore[arg-type]
    _require(bool(models) and set(models) <= set(MODEL_IDS), f"models must be within {MODEL_IDS}")
    grids = dict(data["grids"])  # type: ignore[call-overload]
    for model in models:
        _require(model in grids, f"grid missing for model {model}")
    validation = dict(data["validation"])  # type: ignore[call-overload]
    _require(set(validation) == {"k_outer", "k_inner", "repeats"}, "validation keys invalid")
    seeds = dict(data["seeds"])  # type: ignore[call-overload]
    fit = dict(data["fit"])  # type: ignore[call-overload]
    predictions = dict(data["predictions"])  # type: ignore[call-overload]
    inference = dict(data["inference"])  # type: ignore[call-overload]
    method = str(inference.get("method", "not_assessable"))
    _require(method in INTERVAL_METHODS, f"inference.method must be one of {INTERVAL_METHODS}")
    alpha = float(inference.get("alpha_one_sided", 0.05))
    _require(0 < alpha < 0.5, "alpha_one_sided must be in (0, 0.5)")
    controls = dict(data.get("controls") or {})  # type: ignore[call-overload]
    _require(
        set(controls) <= {"permuted_outcome", "random_gene_sets"},
        "controls keys must be permuted_outcome / random_gene_sets",
    )
    if any(int(v) > 0 for v in controls.values()):  # type: ignore[call-overload]
        _require("raw" in scales, "negative controls run on the raw scale; add 'raw' to scales")
        for model in ("M1", "M2"):
            _require(model in grids, f"negative controls need a grid for {model}")
    unknown_inference = set(inference) - INFERENCE_KEYS
    _require(not unknown_inference, f"unknown inference keys: {sorted(unknown_inference)}")
    bh_q = float(inference.get("bh_q", 0.05))
    _require(0 < bh_q < 1, "inference.bh_q must be in (0, 1)")
    decision_file = inference.get("decision_file")
    decision_sha = inference.get("decision_sha256")
    _require(
        (decision_file is None) == (decision_sha is None),
        "inference.decision_file and inference.decision_sha256 must be set together",
    )
    _require(
        method == "not_assessable" or decision_file is not None,
        "an adopted interval method needs inference.decision_file and decision_sha256",
    )
    return ExperimentConfig(
        raw=dict(data),
        run_id=str(data["run_id"]),
        inputs=inputs,
        population=population,
        scales=scales,
        tier=tier,
        models=models,
        grids={k: dict(v) for k, v in grids.items()},
        k_outer=_int(validation["k_outer"], "k_outer", 2),
        k_inner=_int(validation["k_inner"], "k_inner", 2),
        repeats=_int(validation["repeats"], "repeats", 1),
        base_seed=_int(seeds["base_seed"], "base_seed", 0),
        component_weighting=bool(fit["component_weighting"]),
        clip_raw_predictions=bool(predictions["clip_raw_to_unit_interval"]),
        controls={k: _int(v, k, 0) for k, v in controls.items()},
        interval_method=method,
        alpha_one_sided=alpha,
        bh_q=bh_q,
        decision_file=None if decision_file is None else Path(str(decision_file)),
        decision_sha256=None if decision_sha is None else str(decision_sha),
        output_dir=Path(str(data.get("output_dir", "results/models"))),
        population_options=dict(data.get("population_options") or {}),  # type: ignore[call-overload]
    )


def load_experiment(path: Path) -> ExperimentConfig:
    """Read and validate an experiment YAML file."""
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ExperimentConfigError(f"{path} is not a YAML mapping")
    return experiment_from_mapping(data)
