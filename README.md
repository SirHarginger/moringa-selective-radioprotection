# Explainable Radiosensitivity ML

Does a cancer cell line's baseline gene expression predict how well it survives radiation better than simply knowing which tissue it came from? This repository is a reproducible, leakage-controlled, **estimation-focused** benchmark of that question.

**Python package:** `radiosensitivity_ml`.
**Study protocol:** [`docs/protocol.md`](docs/protocol.md) (v0.3, Option B; not yet frozen).

> **Status (2026-10-21).** Command labels used below:
> - **WORKING:** implemented and validated by the investigator. These are acquisition (`acquire_data.py`) and identifier QC (`run_preprocessing.py`); the real QC has been run.
> - **IMPLEMENTED:** code, configs and unit tests are written but **not yet validated** by the investigator, and no model has been fitted. These are the simulation, modelling, evaluation, explainability and figure commands. They may be run for real only after the protocol is formally frozen.
> - **BLOCKED:** cross-assay concordance (needs the Yard mapping) and the "identity-sound" sensitivity population.
>
> No model result or figure exists.

---

## 1. What the research investigates

**Outcome.** Clonogenic surviving fraction after 2 Gy (SF2), from **CLARIFi**: literature-median SF2 (mSF2) for 285 cancer cell lines. The analysis cohort is 241 eligible solid-tumour lines in 237 independent biological components.

**Predictors.** Baseline RNA expression from **DepMap 24Q4**, summarised as 50 Hallmark gene-set scores (MSigDB v2025.1.Hs).

**Main comparison.** Out-of-sample prediction error of tissue-only (M1) versus tissue + expression (M2), measured as the paired, component-weighted ΔMAE with its uncertainty. A superiority statement needs an interval method that has passed the prespecified simulation. **No claim of clinically or biologically meaningful improvement is made.**

**Leakage control.** Related cell lines (same donor, parent/child, same individual; from DepMap and **Cellosaurus**) form groups that never cross a training/test split. All learning happens inside training folds.

**Relation to the Moringa manuscript.** The project was motivated by an in vitro study of *Moringa oleifera* extracts on V79, DU145 and MCF-7 cells at 0 and 2 Gy. That study measured extract-modified **proliferation** (proliferation enhancement factor, PEF). This project predicts **intrinsic clonogenic radiosensitivity**, a different endpoint.
- PEF is never treated as SF2.
- Nothing here predicts Moringa radioprotection, extract-modified proliferation or wound healing.
- MCF-7 and DU145 (both eligible) appear only as supplementary context.

See [`docs/moringa_scientific_linkage.md`](docs/moringa_scientific_linkage.md).

## 2. Environment

| Environment | Use |
|---|---|
| `moringa-rad` | Existing local environment. Use it now |
| `explainable-radiosensitivity-ml` | Intended dedicated environment ([`environment.yml`](environment.yml)). Create it after the dependency review; a lockfile will follow |

```bash
conda activate moringa-rad
# proposed future environment:
conda env create -f environment.yml && conda activate explainable-radiosensitivity-ml
```

Run every command **from the repository root**. The scripts find the package themselves.

## 3. Datasets and licences

| Source | Version | Licence | Location |
|---|---|---|---|
| CLARIFi (Oike et al., *Cancer Sci* 2025; Zenodo 10.5281/zenodo.20710748) | v1.0 | Unresolved (dataset CC BY 4.0 vs article CC BY-NC 4.0); **do not redistribute** | `data/raw/CLARIFi.csv` (placed manually) |
| DepMap Public 24Q4 (doi:10.25452/figshare.plus.27993248.v1) | 24Q4 | CC BY 4.0 | `data/raw/depmap/24q4/` |
| Cellosaurus API | 56.0 | CC BY 4.0 | `data/raw/cellosaurus/r56_0/` |
| MSigDB Hallmark (Liberzon et al. 2015) | 2025.1.Hs | CC BY 4.0 | `data/raw/msigdb/2025.1.Hs/` |

Provenance for each source is in [`data/manifests/`](data/manifests/). Raw files are never edited, and `data/raw/` is not committed.

## 4. Acquire and verify the data — WORKING

```bash
python scripts/acquire_data.py --dry-run    # plan
python scripts/acquire_data.py              # DepMap 24Q4 core + MSigDB Hallmark + Cellosaurus
python scripts/acquire_data.py --verify     # offline integrity check (exit 1 if anything is missing)
```

**Recorded hashes:**
- the Cellosaurus `COMPLETE.json` SHA-256 is in `configs/preprocessing.yaml` (`cellosaurus.complete_json_sha256`);
- the Hallmark GMT SHA-256 `f22066af72e215ccb7b89d88e492c07e1eef17534c2ca7b0f9902cfecbbdd8e9` is pinned in every `configs/experiment*.yaml` and in `data/manifests/msigdb_hallmark__2025_1_hs.yaml`. The local file was downloaded manually (no acquisition-log entry), so confirm once that it equals the official release file. The model run refuses any other file.

```bash
curl -fsSL https://data.broadinstitute.org/gsea-msigdb/msigdb/release/2025.1.Hs/h.all.v2025.1.Hs.symbols.gmt | sha256sum
sha256sum data/raw/msigdb/2025.1.Hs/h.all.v2025.1.Hs.symbols.gmt   # both must print f22066af…bdd8e9
```

## 5. Preprocessing: identifier QC — WORKING

```bash
python scripts/run_preprocessing.py --config configs/preprocessing.yaml --check-inputs
python scripts/run_preprocessing.py --config configs/preprocessing.yaml
```

**Output:** `results/tables/phase_01/identifier_qc/` (`summary.json`, identity, components, eligibility and tissue tables). The experiment configs pin the SHA-256 of `eligibility.csv`, `components.csv` and `summary.json`. If the QC is re-run, update those hashes.

**Final clean-tree QC (once, after the Git checkpoint; D04.03).** The run refuses a dirty tree, so commit first. Existing QC folders are never overwritten:

```bash
git status --porcelain                      # must print nothing
python scripts/run_preprocessing.py --config configs/preprocessing.yaml \
  --out results/tables/phase_01/identifier_qc_clean
# Membership and component assignment must match the approved cohort exactly:
cmp results/tables/phase_01/identifier_qc/eligibility.csv results/tables/phase_01/identifier_qc_clean/eligibility.csv
cmp results/tables/phase_01/identifier_qc/components.csv  results/tables/phase_01/identifier_qc_clean/components.csv
cmp results/tables/phase_01/identifier_qc/summary.json    results/tables/phase_01/identifier_qc_clean/summary.json
grep '"dirty"' results/tables/phase_01/identifier_qc_clean/run_record.json   # must show false
```

- If the three `cmp` commands print nothing, every eligible identifier and every component assignment is byte-identical, and the pinned `qc_sha256` values stay valid. Run provenance (commit, clean flag, times) is only in `run_record.json`.
- Then set `qc_dir: results/tables/phase_01/identifier_qc_clean` in the three `configs/experiment*.yaml` and commit. The QC records the code commit; the configs commit that follows does not change QC outputs, so there is no circular dependency.
- If a `cmp` reports a difference, stop. Inspect it with `diff` and record it in the decision log before anything else; pin new hashes only after that review.

## 6. Select the uncertainty method by simulation — IMPLEMENTED (investigator-run)

```bash
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1   # required for --workers > 1
python scripts/run_interval_simulation.py --config configs/simulation.yaml --pilot --workers 2   # runtime pilot
python scripts/run_interval_simulation.py --config configs/simulation.yaml --workers 2           # full study
python scripts/run_interval_simulation.py --config configs/simulation.yaml --resume --workers 2  # after interruption
```

`--workers N` (default 1) runs independent replicates and truth draws in N processes. Results do not depend on N, and N may change on resume. Choose N from free memory (`nproc`; `free -h`); it is never chosen automatically. Keep the thread variables identical for the pilot and the full run: they are recorded in the manifest, and a resume refuses a change. Ctrl+C keeps every finished checkpoint. The pilot folder is `pilot_run_id` in `configs/simulation.yaml` (`coverage_v1_pilot_opt`); `coverage_v1_pilot` is the archived pre-optimisation pilot (D04.05). `scripts/compare_simulation_runs.py` compares two simulation folders.

**When and how:** run after the protocol freeze and **before the real outcome is used**. It uses synthetic outcomes only. The synthetic data keep the real tissue and component structure, and the predictors keep the real correlation structure.

**Order (protocol §13 budget rule):**
1. Record the compute budget H **and its unit** (CPU-hours, or wall-clock hours at W workers) in `docs/decision_log.md`, then run the pilot with the W of the full run. It writes only `results/simulation/coverage_v1_pilot_opt/runtime.json` (seconds per replicate and per truth set, workers, wall-clock seconds, effective parallelism); no performance results exist to inspect.
2. Apply the budget rule: `nsim` 500, else 250 (edit `configs/simulation.yaml` and record why); P = B = 1999 / 1000 / 0 later in `controls`.
3. Run the full study. **Output:** `results/simulation/coverage_v1/` (`operating_characteristics.csv`, `decision.json`, `runtime.json`).
4. If `decision.json` says `recheck_required: true`, re-run with `repeats: R` and `run_id: coverage_v1_r<R>`. Use that run's `decision.json` only if it adopts the same method with `recheck_required: false`.
5. Copy into `configs/experiment.yaml`:
   - `inference.method` ← `adopted_method`;
   - `validation.repeats` ← `repeats` (also in `configs/experiment_scales.yaml`);
   - `inference.decision_file` ← the decision path;
   - `inference.decision_sha256` ← `sha256sum <decision path>`.

   Evaluation refuses a verdict if any of these disagree. If `adopted_method` is `not_assessable`, leave `inference.method: not_assessable` and keep `repeats: 20`; results are then reported descriptively.

## 7. Run the ML benchmark — IMPLEMENTED (investigator-run)

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1      # every session (compared on resume)
python scripts/run_model.py --config configs/experiment.yaml --workers 6    # primary: M0, M1, M1P, M2, M2P (raw mSF2)
python scripts/run_model.py --config configs/experiment_scales.yaml       # -ln and logit sensitivity
python scripts/run_model.py --config configs/experiment_loto.yaml         # held-out tissue (descriptive)
```

`--workers N` (default 1) fits independent tasks (model × repeat × outer fold) in N processes with single-threaded BLAS; the parent alone writes task checkpoints. Results do not depend on N, and N may change on resume. Each session is appended to `results/models/<run_id>/sessions.jsonl` (workers, threads, wall clock, packages, code hashes, git). Current primary config: descriptive-only route (D04.06): `inference.method: not_assessable`, R = 10, no negative controls.

**Design:**
- grouped, stratified 5 × 5 nested cross-validation, repeated R times;
- the split table is saved and hashed **before** the outcome is loaded;
- every transformation, the gene-set scoring and the tuning are fitted on training rows only.

**Output:** `results/models/<run_id>/`:
- `run_manifest.json`, `splits.parquet`;
- `tasks/<key>/` holding predictions, model, record and `DONE`;
- `failures.jsonl`.

**Population sensitivities:** set `population: retaining_problematic` or `stranded_excluded` with a new `run_id`.

## 8. Resume interrupted runs — IMPLEMENTED

```bash
python scripts/run_model.py --config configs/experiment.yaml --resume --workers 6
```

**What `--resume` checks:**
- It refuses to continue if the configuration, code, input hashes, split table, package versions, thread settings or task list differ from the stored manifest. Start a new `run_id` instead.
- Each finished task is verified by hash and row set, then reused.
- Corrupted tasks are moved to `_rejected/` and recomputed. Unfinished tasks restart.
- Without `--resume`, an existing run folder is never touched.

## 9. Evaluate predictions — IMPLEMENTED

```bash
python scripts/evaluate_models.py --config configs/experiment.yaml
```

The script refuses to run unless every task is complete.

**Output:** `results/tables/<run_id>/`.

| File | Content |
|---|---|
| `comparisons.csv` | ΔMAE, candidate intervals and verdict (component-weighted, plus the record-weighted sensitivity). With `not_assessable`: no interval columns; the primary verdict reads "descriptive only: superiority not formally assessed" |
| `per_repeat_delta_mae.csv` | ΔMAE per CV repeat |
| `model_metrics.csv` | MAE, RMSE, R², calibration |
| `tissue_errors.csv` | Errors by tissue |
| `oof_predictions.csv` | Out-of-fold predictions |
| `within_tissue_spearman.csv` | Within-tissue rank agreement |
| `negative_controls.csv` | Null ΔMAE from the controls |
| `held_out_tissue.csv` | Held-out-tissue results (LOTO run only) |

## 10. Explainability — IMPLEMENTED

```bash
python scripts/run_explainability.py --config configs/experiment.yaml
```

It computes grouped permutation importance of the 50 gene-set scores on outer-test rows, from the saved models. It also measures stability across tasks, and tests each set against the permuted-outcome and random-gene-set nulls (BH q = 0.05).

**Attribution** is flagged only if the primary comparison showed a gain **and** the set passes against both nulls.

**Output:** `results/tables/<run_id>/explainability/`.

## 10b. Triage rankings — IMPLEMENTED (investigator-run; secondary, hypothesis-generating)

```bash
python scripts/generate_triage.py --config configs/triage.yaml
```

It ranks candidates from the saved evaluation and explainability tables only; it fits and predicts nothing. Tiers are A (strongest support), B (suggestive), C (exploratory), `not_prioritised` and `not_rankable`, by rules fixed in `configs/triage.yaml` and protocol §21 before any ranking is viewed. Every source metric is kept in the tables.

| File (in `results/triage/<run_id>/`) | Content |
|---|---|
| `pathway_candidates.csv` | Gene sets: importance stability, coefficient-sign consistency, BH results against both nulls, correlated-score caveats; curated literature evidence (optional) beside the tier, never changing it |
| `cell_line_validation_priorities.csv` | Measured CLARIFi lines that may warrant re-measurement. **Not independent validation samples.** New, unassayed DepMap lines are deferred (inputs listed in the manifest) |
| `discrepancy_review.csv` | Large or unstable held-out errors and model disagreement, labelled "technical review first" or "unexplained discrepancy" |
| `triage_manifest.json` | Run ID, config, dataset, evaluation-record and source hashes; rules; primary verdict; deferred parts; limitations |

If the primary comparison did not show a gain, every gene set is capped at tier C and all outputs are labelled exploratory. Rankings never feed back into the primary comparison, feature selection or inference, and they are not evidence of causality, clinical utility or radioprotection.

## 11. Figures — IMPLEMENTED

```bash
python scripts/generate_figures.py --config configs/figures.yaml                  # primary figures (evaluation tables only)
python scripts/generate_figures.py --config configs/figures_explainability.yaml   # fig_s02, after run_explainability.py
```

**Publication set (version 2, D04.07):** shared style `src/radiosensitivity_ml/visualization/style.py`; nothing earlier is overwritten.

```bash
python scripts/make_publication_tables.py --config configs/publication.yaml --part core     # Tables 1-3, S1, Spearman v2
python scripts/generate_figures.py --config configs/figures_v2.yaml                        # fig_01/02/03/05, fig_s01, fig_s03 (v2)
python scripts/generate_triage.py --config configs/triage.yaml
python scripts/make_publication_tables.py --config configs/publication.yaml --part triage   # Tables S2, S3
python scripts/generate_figures.py --config configs/figures_triage_v2.yaml                 # fig_s07, fig_s08
python scripts/generate_figures.py --config configs/diagrams.yaml                          # fig_04 workflow v3
```

```bash
python scripts/generate_figures.py --config configs/diagrams.yaml   # methods diagrams; can run now
```

Every figure gets a `.meta.json` provenance sidecar. **Output:** `figures/generated/fig_NN_<slug>_vN.{pdf,svg,png}`.

**Two kinds of figure:**
- **Conceptual methods diagrams** (`configs/diagrams.yaml`, `data_provenance: conceptual_diagram`) show the study design and contain no data, predictions or statistics. They can be rendered now. fig_s04 is drawn from the implemented triage rule text and the frozen thresholds in `configs/triage.yaml`, so it always matches the code.
- **Results figures** (`configs/figures.yaml`, `data_provenance: empirical`) are made only from saved, investigator-generated evaluation tables.

| Figure | Kind | Content |
|---|---|---|
| fig_01 | results | Observed vs predicted |
| fig_02 | results | ΔMAE forest |
| fig_03 | results | Tissue errors |
| fig_04 | conceptual | Study workflow |
| fig_s01 | results | Repeat variability |
| fig_s02 | results | Gene-set stability |
| fig_s03 | results | MCF-7/DU145 context |
| fig_s04 | conceptual | Triage decision rules (A/B/C) |
| fig_s05 | conceptual | Evidence behind each triage ranking |
| fig_s06 | conceptual | Proposed experimental validation pathway (future work) |

Planned, results-dependent: a triage summary figure from `results/triage/<run_id>/` (tier counts and source metrics), to be added once real triage outputs exist. The cross-assay figure follows once tier (c) exists.

## 12. Where everything is saved

| Path | Content | Committed? |
|---|---|---|
| `data/raw/` | Source files as downloaded (read-only) | No |
| `data/manifests/`, `configs/` | Provenance; run settings | Yes |
| `results/tables/phase_01/identifier_qc/` | QC tables, `summary.json` | No |
| `results/simulation/<run_id>/` | Simulation results and decision | No |
| `results/models/<run_id>/` | Predictions, fitted models, manifests | No |
| `results/tables/<run_id>/` | Evaluation and explainability tables | No |
| `results/triage/<run_id>/` | Triage rankings and manifest | No |
| `figures/generated/` | Figures and sidecars | No |

## 13. Tests and troubleshooting

```bash
ruff format src scripts tests && ruff check src scripts tests
python -m pytest -q -m "not model_fit"     # fast unit tests (no model fitting)
python -m pytest -q -m model_fit           # tests that fit tiny models on SYNTHETIC data
```

| Problem | What to do |
|---|---|
| Interrupted download | Re-run `acquire_data.py`. Finished files are verified and kept |
| `… The existing file was NOT overwritten` | Move the failing file aside and re-run |
| `record inputs.gene_sets_sha256` | Copy the GMT SHA-256 from the acquisition log into the experiment configs |
| `… differs from its recorded SHA-256` (QC files) | The QC outputs changed. Update the pinned hashes only if the change is intended and recorded |
| `already exists. Use --resume …` | Add `--resume`, or choose a new `run_id` |
| `incompatible checkpoint: [...]` | Something changed since the run started. Start a new `run_id`; nothing was modified |
| `N task(s) failed` | See `results/models/<run_id>/failures.jsonl`, fix the cause, re-run with `--resume` |
| `tasks are missing or invalid` (evaluation) | Finish the run with `--resume` first |
| Figures `exists; figures are write-once` | Bump `version` in `configs/figures.yaml` |
| Triage `belongs to another config or run_id` | Re-run evaluation and explainability for this config first |

## More documentation

- [`docs/protocol.md`](docs/protocol.md): study protocol.
- [`docs/phase_03_implementation_spec.md`](docs/phase_03_implementation_spec.md): modules, contracts and resume design.
- [`docs/decision_log.md`](docs/decision_log.md): decisions and open items.
- [`docs/phase_01_investigator_qc_checklist.md`](docs/phase_01_investigator_qc_checklist.md): QC run checklist.
- `CLAUDE.md`: rules for AI assistance. Claude Code writes code; only the investigator runs models and analyses.
