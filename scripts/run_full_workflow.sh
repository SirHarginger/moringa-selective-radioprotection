#!/usr/bin/env bash
# Complete scientific workflow, INVESTIGATOR-RUN, in dependency order.
#
#   bash scripts/run_full_workflow.sh            # everything except the overnight controls
#   bash scripts/run_full_workflow.sh --all      # including the ~10-20 h negative controls
#   bash scripts/run_full_workflow.sh --stage 5  # one stage only
#   bash scripts/run_full_workflow.sh --list     # show the stages and their dependencies
#   bash scripts/run_full_workflow.sh --dry-run  # print the commands without running them
#
# Every stage is re-runnable. Stages that write write-once outputs are skipped when their
# output already exists, so an interrupted workflow can simply be restarted.
#
# WHAT IS FROZEN. results/models/primary_v1 and results/tables/primary_v1 (version-1
# files) are never written by this script. The primary benchmark stays M2 vs M1 from that
# run whatever any exploratory stage produces.
#
# WORKERS. The investigator's machine has 6 physical cores / 12 threads / about 31 GiB,
# so WORKERS defaults to 6 with one BLAS thread per worker. Override with
# `WORKERS=4 bash scripts/run_full_workflow.sh`.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

WORKERS="${WORKERS:-6}"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

RUN_ALL=0
DRY_RUN=0
ONLY_STAGE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --all)     RUN_ALL=1 ;;
    --dry-run) DRY_RUN=1 ;;
    --stage)   ONLY_STAGE="${2:?--stage needs a number}"; shift ;;
    --list)
      cat <<'STAGES'
Stage  What it does                                   Depends on   Approx cost (6 workers)
  0    Static checks and tests                        -            ~2 min
  1    Verify the M3 configuration against primary    -            seconds
  2    Exploratory M3 random forest                   1            ~8 min
  3    Leave-one-tissue-out (R2)                      -            ~2 min
  4    Outcome-scale sensitivity (R3)                 -            ~15 min
  5    Evaluate every completed exploratory run       2,3,4        ~1 min
  6    Explainability for eligible runs               5            ~10 min
  7    Pathway and cell-line triage                   6            ~1 min
  8    Compound evidence and candidate ranking        -            seconds
 10    Publication and scientific tables              5,7          ~1 min
  9    Report figures (PNG + PDF)                     5,7,8,10     ~2 min
       (stage 10 runs before stage 9: figures 6 and 7 read the
        publication triage tables that stage 10 writes)
 11    Pre-build audit (does not require the report)  9,10         seconds
 12    Build PDF + DOCX, then the strict final audit  9,10,11      ~1 min
  C    Negative controls, 1000 draws (--all only)     1            ~10-20 h
STAGES
      exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

run() {
  echo
  echo "--- \$ $*"
  if [ "${DRY_RUN}" -eq 1 ]; then return 0; fi
  "$@"
}

stage() {
  local number="$1" title="$2"
  if [ -n "${ONLY_STAGE}" ] && [ "${ONLY_STAGE}" != "${number}" ]; then return 1; fi
  echo
  echo "=============================================================="
  echo " Stage ${number}: ${title}"
  echo "=============================================================="
  return 0
}

skip_if_exists() {
  # skip_if_exists <path> <message>; returns 1 (skip) when the output is already there
  if [ -e "$1" ]; then echo "  already present, skipping: $1"; return 1; fi
  return 0
}

# ---------------------------------------------------------------- 0  static checks
if stage 0 "Static checks and tests (no model fitting)"; then
  run ruff check src scripts tests
  run ruff format --check src scripts tests
  run pytest -m 'not model_fit' -q
fi

# ---------------------------------------------------------------- 1  verify M3 config
if stage 1 "Preflight: vet the exploratory M3 configuration against the frozen primary"; then
  # Preflight reads NO candidate output: it works from
  # configs/experiment_exploratory_m3.yaml (found by its run_id), the primary manifest and
  # the frozen QC tables. It therefore runs before M3 has ever been started, and fails if
  # the configuration is incompatible. Checks that need the realised run are reported as
  # DEFERRED and are verified again in stage 2 after the fit.
  run python scripts/verify_run_consistency.py \
    --reference primary_v1 --candidate exploratory_m3_v1 \
    --candidate-config configs/experiment_exploratory_m3.yaml --pre
fi

# ---------------------------------------------------------------- 2  M3 random forest
if stage 2 "Exploratory M3 random forest (200 tasks)"; then
  if skip_if_exists results/models/exploratory_m3_v1/run_status.json \
       "M3 already run"; then
    run python scripts/run_model.py \
      --config configs/experiment_exploratory_m3.yaml --workers "${WORKERS}"
  fi
  run python scripts/verify_run_consistency.py \
    --reference primary_v1 --candidate exploratory_m3_v1
fi

# ---------------------------------------------------------------- 3  leave-one-tissue-out
if stage 3 "Leave-one-tissue-out generalisation (R2)"; then
  if skip_if_exists results/models/loto_v1/run_status.json "LOTO already run"; then
    run python scripts/run_model.py \
      --config configs/experiment_loto.yaml --workers "${WORKERS}"
  fi
fi

# ---------------------------------------------------------------- 4  scale sensitivity
if stage 4 "Outcome-scale sensitivity (R3)"; then
  if skip_if_exists results/models/scales_v1/run_status.json "scales already run"; then
    run python scripts/run_model.py \
      --config configs/experiment_scales.yaml --workers "${WORKERS}"
  fi
fi

# ---------------------------------------------------------------- C  negative controls
if [ "${RUN_ALL}" -eq 1 ] || [ "${ONLY_STAGE}" = "C" ]; then
  if stage C "Negative controls, 1000 draws of each null (long run, resumable)"; then
    echo "  250 real + 15,000 control tasks. Planning range ~10-20 h at ${WORKERS} workers."
    echo "  Safe to interrupt: checkpoints are per task and write-once; re-run to resume."
    if [ -f results/models/controls_v1/run_manifest.json ]; then
      run python scripts/run_model.py \
        --config configs/experiment_controls.yaml --workers "${WORKERS}" --resume
    else
      run python scripts/run_model.py \
        --config configs/experiment_controls.yaml --workers "${WORKERS}"
    fi
    run python scripts/verify_run_consistency.py \
      --reference primary_v1 --candidate controls_v1
    run python scripts/evaluate_models.py --config configs/experiment_controls.yaml
    run python scripts/run_explainability.py \
      --config configs/experiment_controls.yaml --workers "${WORKERS}"
    run python scripts/generate_triage.py --config configs/triage_controls.yaml
    echo
    echo "  Controls complete. The gene-set p-values in"
    echo "  results/tables/controls_v1/explainability/gene_set_tests.csv are now populated."
    echo "  Tiers stay capped at C unless a protocol amendment adopts the permutation"
    echo "  route first: docs/robustness_plan.md section 2."
  fi
fi

# ---------------------------------------------------------------- 5  evaluate
if stage 5 "Evaluate every completed exploratory run"; then
  for config in configs/experiment_exploratory_m3.yaml configs/experiment_loto.yaml \
                configs/experiment_scales.yaml; do
    run_id="$(grep -m1 '^run_id:' "${config}" | awk '{print $2}')"
    if [ -f "results/models/${run_id}/run_status.json" ]; then
      if skip_if_exists "results/tables/${run_id}/evaluation_record.json" \
           "already evaluated"; then
        # Not fatal: the LOTO and scales runs use different model sets (M0/M2X and
        # M1/M2 on transformed scales), so an evaluation step may legitimately refuse a
        # comparison that does not apply to them. The message says which.
        run python scripts/evaluate_models.py --config "${config}" \
          || echo "  evaluation of ${run_id} did not complete -- see the message above"
      fi
    else
      echo "  ${run_id} has not been run; skipping its evaluation"
    fi
  done
fi

# ---------------------------------------------------------------- 6  explainability
if stage 6 "Explainability for eligible runs (held-out rows, saved models only)"; then
  # Only runs containing M2 are eligible: importance is defined for the expression model.
  # primary_v1's explainability already exists and is NOT recomputed.
  if [ -d results/tables/primary_v1/explainability ]; then
    echo "  primary_v1 explainability already complete (50/50 fits); not recomputed."
  fi
  if [ -f results/models/exploratory_m3_v1/run_status.json ]; then
    if skip_if_exists results/tables/exploratory_m3_v1/explainability \
         "already explained"; then
      run python scripts/run_explainability.py \
        --config configs/experiment_exploratory_m3.yaml --workers "${WORKERS}"
    fi
  fi
fi

# ---------------------------------------------------------------- 7  triage
if stage 7 "Pathway and cell-line triage"; then
  if [ -d results/tables/primary_v1/explainability ]; then
    if skip_if_exists results/triage/primary_v1 "primary triage already present"; then
      run python scripts/generate_triage.py --config configs/triage.yaml
    fi
  fi
fi

# ---------------------------------------------------------------- 8  compounds
if stage 8 "Compound evidence inventory and candidate ranking"; then
  if skip_if_exists results/tables/primary_v1/compounds_v1 "compound tables present"; then
    run python scripts/make_compound_tables.py --config configs/compounds.yaml
  fi
fi

# ---------------------------------------------------------------- 10 tables (before figures)
if stage 10 "Publication and scientific tables"; then
  # verify-and-skip reuses an existing write-once folder when it is complete and was built
  # from exactly these inputs, and FAILS if it is incomplete or stale. Nothing is deleted
  # or overwritten, so validated tables survive a re-run of the workflow.
  for part in core triage; do
    run python scripts/make_publication_tables.py \
      --config configs/publication.yaml --part "${part}" --if-exists verify-and-skip
  done
fi

# ---------------------------------------------------------------- 9  figures
if stage 9 "Report figures, PNG 600 dpi + vector PDF"; then
  run python scripts/make_report_figures.py --config configs/figures_report.yaml --overwrite
fi

# ---------------------------------------------------------------- 11 audit
if stage 11 "Pre-build audit: are the report's prerequisites complete?"; then
  # prebuild mode checks runs, tables and figures but does NOT require the built PDF or
  # DOCX -- deciding whether to build them is the point of this audit.
  run python scripts/audit_outputs.py --mode prebuild
fi

# ---------------------------------------------------------------- 12 build the report
if stage 12 "Build the PDF and DOCX report, then audit strictly"; then
  run bash reports/french_embassy/build.sh
  # The final audit requires everything, including both built documents.
  run python scripts/audit_outputs.py --mode final --strict
fi

echo
echo "=============================================================="
echo " Workflow finished."
echo "   results/models/<run_id>/            fitted-model artefacts and checkpoints"
echo "   results/tables/<run_id>/            metrics, explainability, compound tables"
echo "   results/triage/<run_id>/            pathway and cell-line triage"
echo "   figures/png|pdf|metadata/           report figures and provenance sidecars"
echo "   reports/french_embassy/outputs/     final_project_report.pdf / .docx"
echo
echo " Reconcile the report text against the audit before submitting:"
echo "   python scripts/audit_outputs.py --strict"
echo "=============================================================="
