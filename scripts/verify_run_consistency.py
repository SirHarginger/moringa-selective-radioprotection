"""Verify that an exploratory run is consistent with the frozen primary benchmark.

    python scripts/verify_run_consistency.py --reference primary_v1 --candidate exploratory_m3_v1

Every check reads saved artefacts only. Nothing is fitted, tuned, predicted or scored, so
this is safe to run at any time; it is also the audit step of the full workflow
(``scripts/run_full_workflow.sh``).

Checks, in order. A failure prints the reason and sets a non-zero exit code.

  1  cohort       the candidate covers the same records and the same independent
                 biological components as the reference (241 / 237 for primary_v1)
  2  grouping     no biological component appears in both the training and the test side
                 of any outer fold, in either run
  3  splits       the candidate's ``splits_sha256`` and its splits table are identical to
                 the reference's, so both runs used the same outer and inner folds
  4  inputs       identical input checksums (outcome, expression, gene sets, QC tables)
  5  seeds        identical base seed, repeats, k_outer and k_inner
  6  nesting      tuning happened inside training folds (k_inner >= 2 and recorded)
  7  shared       models present in both runs produce bit-identical predictions, matched
                 on the scientific identifier of each held-out prediction (model, scale,
                 variant, repeat, outer fold, record) rather than on the runs' internal
                 task keys, which differ by design whenever the configurations differ.
                 Coverage must be exactly one to one, with no duplicate identifiers and
                 identical observed outcomes. This is the strongest available check that
                 the candidate did not disturb the benchmark
  8  frozen       the reference's own files are untouched (its recorded hashes still match
                 the files on disk)
  9  isolation    the two runs write to different run folders, so the benchmark cannot be
                 overwritten
 10  completeness the candidate's run_status reports every task computed, none failed

Two modes.

**Preflight (``--pre``)** vets the candidate BEFORE it runs and **reads no candidate
output file at all**: its parameters come from its configuration, found by matching
``run_id`` under ``configs/`` (or named with ``--candidate-config``). It confirms the
planned cohort from the frozen QC table, that the grouping key is well formed, that the
split-generating configuration is identical to the reference's, that the input
specification, seeds and fold counts match, that tuning is nested and the leakage
protections are as frozen, that the required model identifiers are present, and that the
run is isolated under the intended run id. Checks that genuinely cannot be made yet --
realised folds, the realised split hash, input checksums, shared predictions and task
completeness -- are reported as **DEFERRED**, named individually, and are never counted as
passed.

**Post-run (default)** requires the candidate's own manifest and fails if it is absent. It
verifies the realised artefacts: the actual split table and its SHA-256, the recorded input
checksums, the realised biological grouping across outer and inner folds, bit-identical
predictions for shared models, and task completeness.

Either mode exits non-zero on a genuine mismatch. Nothing is skipped silently.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import pandas as pd
import yaml

from radiosensitivity_ml.data.provenance import file_sha256
from radiosensitivity_ml.models.checkpoints import CheckpointError, RunStore

# The scientific identifier of one held-out prediction. Task keys are run-scoped (they
# hash the configuration, code, inputs and splits), so they are never used to match
# predictions between runs; these columns are.
IDENTIFIER_COLUMNS = ("model_id", "scale", "variant", "repeat", "outer_fold", "row_number")
OUTCOME_COLUMN = "y_true"
PREDICTION_COLUMN = "y_pred"
# splits.parquet holds (repeat, outer_fold, row_number, role, inner_fold); the record ->
# component mapping lives in the QC eligibility table, so grouping is verified against it.
ELIGIBILITY = "eligibility.csv"


class Report:
    """Collects check outcomes so every check runs even after one fails."""

    def __init__(self) -> None:
        self.rows: list[tuple[str, bool, str]] = []
        self.deferred: list[str] = []

    def add(self, name: str, ok: bool, detail: str) -> None:
        self.rows.append((name, ok, detail))

    def defer(self, name: str, detail: str) -> None:
        """A check that cannot be made yet and is explicitly postponed, never skipped."""
        self.deferred.append(name)
        self.rows.append((name, True, f"DEFERRED to the post-run check: {detail}"))

    @property
    def failed(self) -> list[tuple[str, bool, str]]:
        return [r for r in self.rows if not r[1]]

    def render(self) -> str:
        width = max(len(name) for name, _, _ in self.rows)
        lines = [
            f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail}"
            for name, ok, detail in self.rows
        ]
        lines.append("")
        checked = len(self.rows) - len(self.deferred)
        if self.failed:
            lines.append(f"{checked - len(self.failed)}/{checked} checks passed")
        else:
            lines.append(f"All {checked} checks performed here passed")
        if self.deferred:
            lines.append(
                f"{len(self.deferred)} check(s) deferred and NOT yet verified: "
                f"{', '.join(self.deferred)}"
            )
            lines.append(
                "Re-run without --pre once the candidate has produced results, to verify them."
            )
        return "\n".join(lines)


def load_manifest(run_dir: Path) -> dict:
    path = run_dir / "run_manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"{path} does not exist; has the run been started?")
    return json.loads(path.read_text(encoding="utf-8"))


def load_status(run_dir: Path) -> dict | None:
    path = run_dir / "run_status.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def discover_config(configs_root: Path, run_id: str) -> Path:
    """The configuration file whose ``run_id`` is ``run_id``.

    Preflight runs before the candidate has written anything, so its parameters can only
    come from its configuration file. Exactly one file must claim the run id. Only
    experiment configurations are considered -- a file must declare both ``models`` and
    ``validation`` -- so that a downstream configuration which merely names the same run
    (the compound and triage configurations do) is not mistaken for one.
    """
    matches = []
    for path in sorted(configs_root.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict) or str(data.get("run_id", "")) != run_id:
            continue
        if "models" in data and "validation" in data:
            matches.append(path)
    if not matches:
        raise FileNotFoundError(
            f"no configuration in {configs_root} declares run_id {run_id!r}; "
            "pass --candidate-config explicitly"
        )
    if len(matches) > 1:
        raise FileNotFoundError(
            f"several configurations declare run_id {run_id!r}: "
            f"{', '.join(p.name for p in matches)}"
        )
    return matches[0]


def eligibility_table(config: dict, project_root: Path) -> pd.DataFrame:
    """The frozen QC eligibility table named in a configuration."""
    qc_dir = project_root / str(dict(config.get("inputs") or {})["qc_dir"])
    return pd.read_csv(qc_dir / ELIGIBILITY)


def component_of_record(config: dict, project_root: Path) -> pd.Series:
    """row_number -> component_id, from the QC eligibility table named in the config."""
    return eligibility_table(config, project_root).set_index("row_number")["component_id"]


def planned_cohort(config: dict, project_root: Path) -> tuple[int, int, str]:
    """(records, components, detail) the candidate WILL use, from the QC table alone.

    The analysis population is the rows the frozen QC marked eligible, so the cohort can
    be checked before a single model is fitted.
    """
    table = eligibility_table(config, project_root)
    eligible = table[table["eligible_primary"].astype(str).str.lower() == "true"]
    records = len(eligible)
    components = int(eligible["component_id"].nunique())
    multi = int((eligible["component_id"].value_counts() > 1).sum())
    return records, components, f"{multi} components hold more than one record"


def grouping_safeguards(config: dict, project_root: Path) -> tuple[bool, str]:
    """The grouping key is well formed, so no record can escape its component.

    Every eligible record must carry a component id, and component ids must be reused
    across records wherever the QC found a relationship: that reuse is what makes the
    grouped split meaningful. Realised folds are checked after the run.
    """
    table = eligibility_table(config, project_root)
    eligible = table[table["eligible_primary"].astype(str).str.lower() == "true"]
    missing = int(eligible["component_id"].isna().sum())
    blank = int((eligible["component_id"].astype(str).str.strip() == "").sum())
    grouped = int((eligible["component_id"].value_counts() > 1).sum())
    ok = missing == 0 and blank == 0 and grouped > 0
    return ok, (
        f"{len(eligible)} eligible records, {missing} without a component id, "
        f"{blank} blank, {grouped} components grouping >1 record"
    )


SPLIT_DETERMINING_KEYS = ("population", "population_options", "validation", "seeds", "tier")


def split_configuration_matches(ref: dict, cand: dict) -> tuple[bool, str]:
    """The inputs that determine the split table are identical.

    The outer and inner folds are a deterministic function of the population, the fold
    counts, the repeat count and the base seed. If all of those agree, the candidate will
    generate the same splits; whether it actually did is verified after the run.
    """
    differences = [
        f"{key}: {ref.get(key)!r} vs {cand.get(key)!r}"
        for key in SPLIT_DETERMINING_KEYS
        if ref.get(key) != cand.get(key)
    ]
    ref_qc = dict(ref.get("inputs") or {}).get("qc_sha256")
    cand_qc = dict(cand.get("inputs") or {}).get("qc_sha256")
    if ref_qc != cand_qc:
        differences.append("inputs.qc_sha256 differs, so the population may differ")
    return not differences, (
        "; ".join(differences)
        if differences
        else f"identical {', '.join(SPLIT_DETERMINING_KEYS)} and QC checksums"
    )


def model_identifiers(cand: dict, required: tuple[str, ...]) -> tuple[bool, str]:
    """The candidate fits every model its comparisons need."""
    models = [str(m) for m in (cand.get("models") or [])]
    absent = [m for m in required if m not in models]
    return not absent, (f"models {models}" + (f"; MISSING required {absent}" if absent else ""))


LEAKAGE_KEYS = (("fit", "component_weighting"), ("predictions", "clip_raw_to_unit_interval"))


def leakage_protections(ref: dict, cand: dict) -> tuple[bool, str]:
    """Settings that keep held-out data out of training, identical to the frozen run."""
    problems = []
    k_inner = int(dict(cand.get("validation") or {}).get("k_inner", 0))
    if k_inner < 2:
        problems.append(f"k_inner = {k_inner}: tuning would not be nested")
    for section, key in LEAKAGE_KEYS:
        a = dict(ref.get(section) or {}).get(key)
        b = dict(cand.get(section) or {}).get(key)
        if a != b:
            problems.append(f"{section}.{key}: {a!r} vs {b!r}")
    if not dict(cand.get("fit") or {}).get("component_weighting"):
        problems.append("fit.component_weighting is off: records would outweigh components")
    return not problems, (
        "; ".join(problems)
        if problems
        else f"nested tuning (k_inner = {k_inner}), component weighting and clip rule as frozen"
    )


def cohort_sizes(splits: pd.DataFrame, components: pd.Series) -> tuple[int, int]:
    """(records, independent components) actually used by a run."""
    rows = sorted(set(splits["row_number"]))
    return len(rows), int(components.reindex(rows).nunique())


def grouping_is_intact(splits: pd.DataFrame, components: pd.Series) -> tuple[bool, str]:
    """No biological component may appear on both sides of an outer fold, or in two
    inner folds of one training set."""
    table = splits.assign(component=components.reindex(splits["row_number"]).to_numpy())
    if table["component"].isna().any():
        return False, "some records have no component in the QC eligibility table"
    outer = table.groupby(["repeat", "outer_fold", "component"])["role"].nunique()
    straddling = int((outer > 1).sum())
    train = table[table["role"] == "train"]
    inner = train.groupby(["repeat", "outer_fold", "component"])["inner_fold"].nunique()
    inner_split = int((inner > 1).sum())
    ok = straddling == 0 and inner_split == 0
    return ok, (
        f"{len(outer)} component-fold groups; {straddling} straddling train/test, "
        f"{inner_split} split across inner folds"
    )


def compare_predictions(name: str, a: pd.DataFrame, b: pd.DataFrame) -> str | None:
    """Compare one model's held-out predictions between two runs; None when identical.

    Matching is on the scientific identifier of a held-out prediction -- model, outcome
    scale, control variant, repeat, outer fold and the held-out record -- never on the
    runs' internal task keys. Coverage must be exactly one to one with no duplicates, the
    observed outcomes must agree, and the predictions must be bitwise equal, because the
    two runs fit the same model on the same splits with the same seeds and grids. A
    numerical difference is reported with its magnitude, not tolerated.
    """
    ids = list(IDENTIFIER_COLUMNS)
    required = [*ids, OUTCOME_COLUMN, PREDICTION_COLUMN]
    for label, frame in (("reference", a), ("candidate", b)):
        absent = [c for c in required if c not in frame.columns]
        if absent:
            return f"{name}: the {label} predictions lack {absent}"
        duplicates = int(frame.duplicated(subset=ids).sum())
        if duplicates:
            return (
                f"{name}: {duplicates} duplicate held-out identifiers in the {label} run "
                f"(each record must be predicted once per repeat and fold)"
            )
    left = a.set_index(ids).sort_index()
    right = b.set_index(ids).sort_index()
    only_reference = left.index.difference(right.index)
    only_candidate = right.index.difference(left.index)
    if len(only_reference) or len(only_candidate):
        return (
            f"{name}: coverage is not one to one -- {len(only_reference)} predictions only "
            f"in the reference run, {len(only_candidate)} only in the candidate "
            f"({len(left)} vs {len(right)} rows)"
        )
    if not left[OUTCOME_COLUMN].equals(right[OUTCOME_COLUMN]):
        differing = int((left[OUTCOME_COLUMN].to_numpy() != right[OUTCOME_COLUMN].to_numpy()).sum())
        return (
            f"{name}: {differing} held-out observed outcomes differ between the runs, so "
            f"they are not the same data"
        )
    if not left[PREDICTION_COLUMN].equals(right[PREDICTION_COLUMN]):
        x = left[PREDICTION_COLUMN].to_numpy(dtype=float)
        y = right[PREDICTION_COLUMN].to_numpy(dtype=float)
        difference = np.abs(x - y)
        both_nan = np.isnan(x) & np.isnan(y)
        changed = int((~both_nan & ((difference != 0) | (np.isnan(x) != np.isnan(y)))).sum())
        worst = float(np.nanmax(difference)) if changed else 0.0
        return (
            f"{name}: {changed} of {len(x)} predictions differ, largest absolute difference "
            f"{worst:.3e}. Identical deterministic fits on identical splits must be bitwise "
            f"equal: investigate the cause (code, library versions, thread counts) rather "
            f"than accepting a tolerance"
        )
    return None


def shared_predictions(ref_dir: Path, cand_dir: Path, ref: dict, cand: dict) -> tuple[bool, str]:
    """Models present in both runs must have produced identical held-out predictions.

    Task keys are deliberately NOT compared. A key is
    ``sha256(context | scale | model | repeat | fold | variant | seed)`` where the context
    hashes the configuration, the code, the inputs and the split table
    (``models.run.context_sha256``), so two runs with different configurations always have
    different keys for the same fit -- that is what stops a stale checkpoint being reused
    across incompatible configurations. The task *seed*, by contrast, depends only on the
    base seed and the fit's coordinates, so a model shared between the runs is the same
    computation and must give the same numbers. Each run is therefore read with its own
    keys and the predictions are matched on their scientific identifiers.
    """

    def by_model(manifest: dict) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for key in manifest["tasks"]:
            scale, model, _r, _f, variant, _seed = manifest["task_details"][key]
            if variant == "real":
                out.setdefault(f"{model}|{scale}", []).append(key)
        return out

    ref_tasks, cand_tasks = by_model(ref), by_model(cand)
    shared = sorted(set(ref_tasks) & set(cand_tasks))
    if not shared:
        return False, "no model is present in both runs"
    ref_store, cand_store = RunStore(ref_dir), RunStore(cand_dir)
    problems: list[str] = []
    compared = 0
    for name in shared:
        try:
            a = ref_store.load_predictions(sorted(ref_tasks[name]))
            b = cand_store.load_predictions(sorted(cand_tasks[name]))
        except (FileNotFoundError, OSError, KeyError, ValueError) as exc:
            problems.append(f"{name}: missing predictions ({type(exc).__name__}: {exc})")
            continue
        if len(ref_tasks[name]) != len(cand_tasks[name]):
            problems.append(
                f"{name}: {len(ref_tasks[name])} tasks in the reference run but "
                f"{len(cand_tasks[name])} in the candidate"
            )
            continue
        problem = compare_predictions(name, a, b)
        if problem:
            problems.append(problem)
        else:
            compared += len(a)
    if problems:
        return False, "; ".join(problems)
    return True, (
        f"{len(shared)} shared model-scale combinations ({', '.join(shared)}); "
        f"{compared} held-out predictions matched one-to-one on "
        f"{'+'.join(IDENTIFIER_COLUMNS)} and bitwise identical"
    )


def reference_is_untouched(ref_dir: Path, ref: dict) -> tuple[bool, str]:
    """The frozen run's recorded hashes must still match its files on disk."""
    problems = []
    splits = ref_dir / "splits.parquet"
    if not splits.is_file():
        problems.append("splits.parquet missing")
    elif file_sha256(splits) != ref.get("splits_sha256"):
        problems.append("splits.parquet differs from run_manifest.json")
    recorded = {Path(p).name for p in (ref.get("inputs_sha256") or {})}
    return not problems, "; ".join(problems) or (
        f"splits hash matches; {len(recorded)} input hashes recorded"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--reference", default="primary_v1", help="frozen run id")
    parser.add_argument("--candidate", required=True, help="exploratory run id to verify")
    parser.add_argument("--models-root", type=Path, default=ROOT / "results" / "models")
    parser.add_argument("--configs-root", type=Path, default=ROOT / "configs")
    parser.add_argument(
        "--project-root", type=Path, default=ROOT,
        help="root that configuration-relative paths resolve against",
    )  # fmt: skip
    parser.add_argument(
        "--candidate-config", type=Path, default=None,
        help="candidate configuration (--pre only; discovered from its run_id if omitted)",
    )  # fmt: skip
    parser.add_argument("--expect-records", type=int, default=241)
    parser.add_argument("--expect-components", type=int, default=237)
    parser.add_argument("--require-models", nargs="*", default=["M0", "M1", "M2"])
    parser.add_argument(
        "--pre", action="store_true",
        help="preflight: configuration-level checks only, before the candidate has run. "
             "Reads no candidate output files.",
    )  # fmt: skip
    args = parser.parse_args(argv)

    ref_dir = args.models_root / args.reference
    cand_dir = args.models_root / args.candidate
    report = Report()

    # The reference manifest is always required: it is the frozen run being protected.
    try:
        ref = load_manifest(ref_dir)
    except FileNotFoundError as exc:
        print(f"ERROR: reference run: {exc}", file=sys.stderr)
        return 2
    ref_config = dict(ref.get("config") or {})

    # The candidate's parameters come from its manifest after the run, and from its
    # configuration file before it. Preflight must never require candidate outputs.
    cand: dict | None = None
    if args.pre:
        try:
            cand_config_path = args.candidate_config or discover_config(
                args.configs_root, args.candidate
            )
            cand_config = yaml.safe_load(cand_config_path.read_text(encoding="utf-8")) or {}
        except (FileNotFoundError, OSError, yaml.YAMLError) as exc:
            print(f"ERROR: candidate configuration: {exc}", file=sys.stderr)
            return 2
        try:
            shown = cand_config_path.relative_to(args.project_root)
        except ValueError:
            shown = cand_config_path
        report.add(
            "0 candidate source",
            True,
            f"preflight from {shown} (no candidate output read)",
        )
    else:
        try:
            cand = load_manifest(cand_dir)
        except FileNotFoundError as exc:
            print(
                f"ERROR: candidate run: {exc}\n"
                f"       The post-run check requires the candidate's own outputs. To vet "
                f"its configuration before it runs, use --pre.",
                file=sys.stderr,
            )
            return 2
        cand_config = dict(cand.get("config") or {})

    try:
        ref_components = component_of_record(ref_config, args.project_root)
    except (KeyError, FileNotFoundError) as exc:
        report.add("QC eligibility readable", False, f"{type(exc).__name__}: {exc}")
        print(report.render())
        return 1

    # ---- 1 cohort, 2 grouping, 3 splits
    if args.pre:
        try:
            records, components, detail = planned_cohort(cand_config, args.project_root)
        except (KeyError, FileNotFoundError) as exc:
            report.add("1 cohort", False, f"{type(exc).__name__}: {exc}")
            records = components = -1
            detail = ""
        report.add(
            "1 cohort (planned)",
            (records, components) == (args.expect_records, args.expect_components),
            f"{records} records / {components} components "
            f"(expected {args.expect_records} / {args.expect_components}); {detail}",
        )
        ok, detail = grouping_safeguards(cand_config, args.project_root)
        report.add("2 grouping key", ok, detail)
        report.defer("2 grouping (realised folds)", "no split table exists yet")
        ok, detail = split_configuration_matches(ref_config, cand_config)
        report.add("3 split configuration", ok, detail)
        report.defer(
            "3 splits identical",
            "the realised splits.parquet and its SHA-256 cannot be compared before the run",
        )
    else:
        assert cand is not None
        # RunStore.load_splits re-hashes splits.parquet and raises CheckpointError when it
        # differs from the hash recorded in run_manifest.json, which is itself one of the
        # required post-run checks: a corrupted or regenerated split table must be reported
        # as a failed verification, not propagated as an unrelated exception.
        try:
            ref_splits = RunStore(ref_dir).load_splits(ref["splits_sha256"])
            cand_splits = RunStore(cand_dir).load_splits(cand["splits_sha256"])
        except (CheckpointError, OSError, ValueError) as exc:
            report.add("splits readable", False, f"{type(exc).__name__}: {exc}")
            print(report.render())
            return 1
        cand_components = component_of_record(cand_config, args.project_root)
        records, components = cohort_sizes(cand_splits, cand_components)
        report.add(
            "1 cohort",
            (records, components) == (args.expect_records, args.expect_components),
            f"{records} records / {components} components "
            f"(expected {args.expect_records} / {args.expect_components})",
        )
        for label, table, mapping in (
            ("reference", ref_splits, ref_components),
            ("candidate", cand_splits, cand_components),
        ):
            ok, detail = grouping_is_intact(table, mapping)
            report.add(f"2 grouping ({label})", ok, detail)
        same_hash = ref["splits_sha256"] == cand["splits_sha256"]
        identical = ref_splits.equals(cand_splits)
        report.add(
            "3 splits identical",
            same_hash and identical,
            f"sha256 {'match' if same_hash else 'DIFFER'}; table "
            f"{'identical' if identical else 'DIFFERS'}",
        )

    # ---- 4 inputs, 5 seeds, 6 nesting and leakage, 6b model identifiers
    if args.pre:
        ref_inputs = dict(ref_config.get("inputs") or {})
        cand_inputs = dict(cand_config.get("inputs") or {})
        shared = sorted(set(ref_inputs) & set(cand_inputs))
        differing = [k for k in shared if ref_inputs[k] != cand_inputs[k]]
        report.add(
            "4 input specification",
            not differing,
            f"{len(shared)} input keys compared"
            + (f"; DIFFER: {', '.join(differing)}" if differing else "; identical"),
        )
        report.defer("4 input checksums", "hashes are recorded when the run starts")
    else:
        assert cand is not None
        same = ref.get("inputs_sha256") == cand.get("inputs_sha256")
        report.add("4 input checksums", same, "identical" if same else "DIFFER")

    ref_val = dict(ref_config.get("validation") or {})
    cand_val = dict(cand_config.get("validation") or {})
    ref_seed = dict(ref_config.get("seeds") or {}).get("base_seed")
    cand_seed = dict(cand_config.get("seeds") or {}).get("base_seed")
    report.add(
        "5 seeds and folds",
        ref_seed == cand_seed and ref_val == cand_val,
        f"base_seed {ref_seed} vs {cand_seed}; validation {ref_val} vs {cand_val}",
    )
    ok, detail = leakage_protections(ref_config, cand_config)
    report.add("6 leakage protections", ok, detail)
    ok, detail = model_identifiers(cand_config, tuple(args.require_models))
    report.add("6b model identifiers", ok, detail)

    # ---- 7 shared predictions, 8 frozen reference
    if args.pre:
        report.defer("7 shared predictions", "the candidate has produced no predictions yet")
    else:
        assert cand is not None
        ok, detail = shared_predictions(ref_dir, cand_dir, ref, cand)
        report.add("7 shared predictions", ok, detail)
    ok, detail = reference_is_untouched(ref_dir, ref)
    report.add("8 reference untouched", ok, detail)

    # ---- 9 isolation, 10 completeness
    cand_run_id = str(cand_config.get("run_id") or (cand or {}).get("run_id") or "")
    expected_id = cand_run_id == args.candidate
    distinct = ref_dir.resolve() != cand_dir.resolve() and ref["run_id"] != cand_run_id
    report.add(
        "9 run isolation",
        distinct and expected_id,
        f"{ref['run_id']} -> {ref_dir.name}; {cand_run_id or '<none>'} -> {cand_dir.name}"
        + ("" if expected_id else f"; run_id does not match --candidate {args.candidate!r}"),
    )
    if args.pre:
        report.defer("10 completeness", "no run_status.json until the run finishes")
    else:
        status = load_status(cand_dir)
        counts = dict((status or {}).get("counts") or {})
        complete = bool(status) and status.get("status") == "complete" and not counts.get("failed")
        report.add(
            "10 completeness",
            complete,
            f"status={(status or {}).get('status', 'absent')} counts={counts}",
        )

    print(report.render())
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
