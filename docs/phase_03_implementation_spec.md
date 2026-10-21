# Phase 03 implementation specification (minimum viable pipeline)

**Status:** draft, 2026-10-21. It implements `docs/protocol.md` once the protocol is frozen.

**Rules:**
- Claude Code writes code and unit tests on labelled synthetic fixtures only. The investigator runs everything that fits, predicts or evaluates.
- Only scikit-learn, numpy, pandas, scipy and matplotlib are used. No orchestration framework.
- One YAML config per run in `configs/`.

## Data flow

```
QC outputs (frozen, hashed) ─┐
DepMap expression ───────────┼─> features.build ─> splits.load ─> models.run_tier ─> predictions/*.parquet
Hallmark GMT (hashed) ───────┘                                                          │
CLARIFi mSF2 (opened last) ───────────────────────────────────────────────────────────┘
          evaluation.compare ─> results/tables/*.csv ─> visualization.figures ─> figures/generated/
```

## Modules (in `src/radiosensitivity_ml/`)

| Module | Public functions | Input → output contract |
|---|---|---|
| `config.py` | `load_run_config(path) -> RunConfig` | YAML → frozen dataclass: paths, seeds, grids, R, K, tier and model lists. Records the config SHA-256 |
| `data/analysis_table.py` (sensitivity populations P-S1 to P-S5 are subsets of the frozen splits, never re-split) | `load_population(qc_dir, expected_sha, population="primary") -> Population` | Frozen `eligibility.csv` + `components.csv` (hashes checked) → eligible records: `row_number`, `depmap_id`, `component_id`, `lineage`, `pooled_lineage`. **No outcome** |
| | `load_outcome(clarifi, population, scale) -> pd.Series` | Called only after the split hash is recorded. Returns mSF2 indexed by `row_number`. Fails on invalid values. Applies the frozen boundary rule for −ln and logit |
| `features/expression.py` | `load_expression(path, model_ids) -> pd.DataFrame` | 24Q4 matrix → models × genes. Checks the header gene IDs. No transformation |
| `features/gene_sets.py` | `load_gmt(path, expected_sha)`; `GeneSetScorer` (sklearn transformer) | `fit` learns gene means and SDs on training rows; `transform` → samples × sets. Reports unmapped genes |
| | `ProliferationScorer` | Mean of the E2F and G2M set scores. Fitted in-fold |
| `evaluation/splits.py` | `make_splits(population, k_outer, k_inner, repeats, seed) -> SplitTable` | **No outcome argument.** Stratifies on `pooled_lineage` and groups by `component_id`. Long table keyed by (`repeat`, `outer_fold`, `row_number`), with `role` ∈ {train, test} and `inner_fold` (null for test rows). Asserts no component spans train and test at either level. Saved, then hashed before any outcome value beyond the validity flag is used |
| | `leave_one_lineage_out(population, min_components)` | Tier (b) folds |
| `models/baselines.py` | `GlobalMean`, `TissueRidge(categories, level="lineage" \| "lineage+disease" \| "pooled")` | Full one-hot over a category list fixed from eligible metadata; no reference level; dummies not scaled; intercept unpenalised. An unseen level gives an all-zero row, so the prediction is the intercept (logged). Supports `sample_weight` = 1/\|component\|. No strandedness covariate in primary models (protocol §6) |
| `models/offset.py` | `OffsetElasticNet(baseline, features)` | One estimator: `fit` refits the baseline, then the elastic net on the residuals. Used for M1, M1′ (B2 offset, 48 sets) and M4 (variance-filtered transcriptome) |
| `models/pipelines.py` | `build(model_id, config) -> Pipeline` | B0, B1, B2, M1, M1′, M2 (RandomForestRegressor), M3 (HistGradientBoostingRegressor), M4. Every transform lives inside the Pipeline |
| `models/run.py` | `run_tier_a(...)`, `run_tier_b(...)`, `run_tier_c(...)` | Nested CV with equal tuning budgets → long-format predictions: `row_number`, `repeat`, `outer_fold`, `model_id`, `y_true`, `y_pred`, `scale`, `tier`. Written once per run with a run record. **Investigator-run** |
| `models/controls.py` | `permute_within_tissue(y, lineage, seed)`; `random_gene_sets(gmt, universe, matched_on, n_draws, seed)` | Null inputs that reuse `run_tier_a` |
| `evaluation/metrics.py` | `paired_delta_mae(pred, a, b, weights="component" \| "record")`, `delta_rmse`, `delta_r2_oos`, `calibration`, `spearman_within_tissue` | Pure functions on the predictions table |
| `evaluation/intervals.py` | `component_bootstrap(...)` (descriptive), `nadeau_bengio(...)`, `nested_cv_interval(...)` | Candidates only. Adoption follows the coverage study (protocol §13) |
| `explainability/stability.py` | `permutation_importance_grouped(...)` (every model; outer-test rows only; MAE loss); `rank_stability(...)`: Kendall τ, RBO, top-k Jaccard | Importance tables per fold and repeat → stability metrics versus nulls |
| `visualization/figures.py` | `fig_flow`, `fig_delta_forest`, `fig_within_tissue`, `fig_stability_vs_null`, `fig_s_moringa_case` | Tables → PDF/SVG + PNG at 300–600 dpi (`docs/figure_standards.md`). Observed and predicted values are drawn distinctly |

## Contracts that guard against leakage (unit-tested on synthetic fixtures)

1. `make_splits` has no outcome parameter, and its output hash is recorded before `load_outcome` is called.
2. No `component_id` appears in both train and test within any outer fold.
3. Fitted transformer state depends only on training indices (a spy test).
4. Inner-fold indices never include outer-test rows.
5. Tier (b) training excludes the held-out lineage entirely.
6. Tier (c) excludes overlapping components in both directions.
7. Importances are computed on outer-test rows only.
8. Offset models refit their baseline in every inner fit (a spy test).
9. The tier (a) component file is CLARIFi-only and frozen. Tier (c) builds its own CLARIFi ∪ Yard graph.

## Order of implementation (shortest path to the confirmatory run)

1. `analysis_table` + `splits`: frozen splits and their hash. No outcome needed.
2. `gene_sets`, `baselines`, `offset`, `pipelines`, with synthetic-fixture tests.
3. `models.run` with checkpoints and `--resume`.
4. `simulation.generator` + `evaluation.intervals` + `run_interval_simulation.py`. The investigator runs it, and the adopted interval method and R are signed into the decision log.
5. Unseal the outcome (access logged), then `run_model.py` → `evaluate_models.py` → `run_explainability.py` → `generate_figures.py`.

## Out of scope until needed

- Deep models, AutoML, xgboost, DVC or Snakemake.
- Full-transcriptome hyperparameter sweeps beyond the protocol grid.

## Command-line entry points

| Command | Status | Calls |
|---|---|---|
| `python scripts/acquire_data.py [--verify\|--dry-run]` | **WORKING** | `data.acquisition`, `data.cellosaurus_fetch` |
| `python scripts/run_preprocessing.py --config configs/preprocessing.yaml [--check-inputs]` | **WORKING** | `data.qc_identifiers`, `data.eligibility`, `data.qc_report` |
| `python scripts/run_interval_simulation.py --config configs/simulation.yaml [--resume]` | PLANNED (runs after the freeze, before the outcome is unsealed; protocol §13) | `simulation.generator` (Gaussian copula over the real eligible expression matrix; synthetic outcomes only), `models.run`, `evaluation.intervals` |
| `python scripts/run_model.py --config configs/experiment.yaml [--resume]` | PLANNED | `evaluation.splits`, `models.*`, `models.run`, `models.checkpoints` |
| `python scripts/evaluate_models.py --config configs/experiment.yaml` | PLANNED | `evaluation.metrics`, `evaluation.intervals` |
| `python scripts/run_explainability.py --config configs/experiment.yaml` | PLANNED | `explainability.stability` |
| `python scripts/generate_figures.py --config configs/figures.yaml` | PLANNED | `visualization.figures` |

**Rules for every script:**
- runs from the repository root;
- adds `src/` to the path itself, so no install is needed;
- exits 0 on success, 1 on an expected error (one-line message), and 2 on wrong usage;
- never overwrites a results folder.

No PLANNED script is created before its implementation and tests exist.

**`configs/experiment.yaml`** (written at the protocol freeze):
- `run_id`;
- the frozen QC folder and its `summary.json` SHA-256;
- expression file and gene-set GMT, each with a SHA-256;
- scale (`raw`, `neglog`, `logit`);
- tiers;
- model IDs;
- grids;
- `k_outer`, `k_inner`, `repeats`;
- seeds;
- weighting;
- clip rule.

## Resume design (`run_model.py --resume`)

**Unit of work: a task.** One task is a (tier, scale, model_id, repeat, outer_fold) combination. Each task is independent: it fits on its outer-training rows, including inner tuning, and predicts its outer-test rows.

**Layout:**

```
results/models/<run_id>/
  run_manifest.json        # frozen at first start: config SHA-256, git commit, code hashes,
                           # input SHA-256s (QC files, split table, expression, GMT, CLARIFi),
                           # package versions, seeds, task list with each task's key
  splits.parquet           # written and hashed BEFORE the outcome is loaded
  scale_rows.json          # row numbers available on each scale (no outcome values);
                           # written once, verified on resume and by evaluation
  run_status.json          # running | complete | incomplete, with task counts
  tasks/<task_key>/
      predictions.parquet  # row_number, y_true, y_pred, ...
      task_record.json     # task key, seed, start/end time, row and prediction counts,
                           # SHA-256 of predictions.parquet, hyperparameters chosen
      DONE                 # written last, containing the SHA-256 of task_record.json
```

**Task key:** the SHA-256 of (config hash, input hashes, split-table hash, tier, scale, model_id, repeat, outer_fold, seed). Any change to inputs or settings produces new keys, so stale results can never be reused silently.

**Writing:** each task writes to `tasks/<task_key>.partial/`. When it finishes, it adds `DONE` and renames the folder. A crash therefore leaves only a `.partial` folder, which is discarded on resume.

**`--resume` behaviour:**
1. Load `run_manifest.json`. **Refuse to resume** if any of these differs: config hash, code hashes, input hashes, package versions, or the task list. The run then stops with an "incompatible checkpoint" message naming each difference. The user starts a new `run_id`; nothing is overwritten.
2. For each task, accept it only if:
   - `DONE` exists;
   - its hash matches `task_record.json`;
   - the predictions hash matches;
   - the row set equals the outer-test rows of that fold.

   A task failing any check is reported as corrupted, moved to `tasks/_rejected/<task_key>_<utc>`, and recomputed.
3. Recompute missing and rejected tasks only. Each task re-seeds from its own recorded seed, so a recomputed task equals an uninterrupted one.
4. Progress is printed as `[n_done/n_total] task_key status elapsed`, with a final summary of reused, recomputed, rejected and failed counts. Any failure gives a non-zero exit.

**Without `--resume`:** if the `run_id` folder exists, the run stops (never overwrites). `--resume` is the only way to continue a run.

**Nothing resumes mid-fit.** Within-task checkpointing (a partially tuned grid) is out of scope: an interrupted task restarts.

**Determinism rules (ml-methodologist review):**
- **Inner folds** are stored in `splits.parquet`, as inner fold IDs per (repeat, outer_fold), grouped by component. Their hash goes into `task_record.json`.
- **Task seed** = H(base_seed, tier, scale, model_id, repeat, outer_fold). It is never derived from the task key. It feeds every random state the task uses (inner CV shuffling, estimator `random_state`), and each is named in `task_record.json`.
- **Split table on resume:** `splits.parquet` is verified against its manifest hash, never regenerated. The split function has no outcome parameter, which is checked by signature and a test.
- **Thread settings:** `n_jobs`, thread counts and BLAS environment variables (`OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`) are recorded in the manifest, and a resume is refused if they differ. Boosting uses deterministic settings.
- **Reproducibility guarantee:** byte-identical predictions are expected under identical settings. The test checks equality within an absolute tolerance of 1e-12.
- **Evaluation:** `evaluate_models.py` refuses to run unless every task in the manifest has a valid `DONE`.

**Tests (synthetic, dummy estimator):**
- task-key stability;
- refusal on changed config or inputs;
- `.partial` discarded;
- a corrupted `DONE` or predictions file rejected and recomputed;
- results from a resumed run equal those from an uninterrupted run, byte for byte;
- no overwrite without `--resume`.

## Review fixes (D03.03; code only, nothing executed)

**Model runs (`models/run.py`, `models/checkpoints.py`, `config.py`):**
- Negative controls: each draw has one seed, `stable_int(base_seed, "control", variant)`, shared by every fold and model of that draw. Permutation moves whole components within each lineage.
- Component weights are recomputed among the records available on the task's scale.
- Inner tuning applies the same raw-scale prediction clip as the outer evaluation.
- `retaining_problematic` splits copy each added relative's component assignment; both sensitivity split tables pass `check_splits`.
- `inputs_sha256` includes CLARIFi and its manifest (file bytes only). The manifest records git commit/dirty state (not compared on resume), Python, joblib and pyarrow versions. `code_sha256` fails if no source files are found.
- Config: controls require `raw` in scales and grids for M1 and M2; `inference` keys are strict and add `bh_q`, `decision_file` and `decision_sha256`. An adopted interval method requires the decision file.
- The M2P grid tunes the M1P residual penalty over M1P's own grid.

**Evaluation (`evaluation/report.py`):** the config hash must match the run manifest; each task must hold exactly its test rows available on its scale; the decision file's hash, method and R must match the config. Only the primary comparison (M2 vs M1, raw, primary population, within-tissue tier) gets a verdict ("gain shown" or "no gain shown"); everything else is labelled descriptive.

**Explainability (`explainability/report.py`):** requires `evaluation_record.json` from the same config and run; loads inputs once; BH q from the config; importance seeds from `stable_int(base_seed, "importance", task_key)`; adds M2 coefficient sign consistency; M2P and M3 importances descriptive only.

**Simulation (`simulation/`):** lineage-conditional expression (real lineage centroids + residual copula); a fixed `SignalMap` fitted once on a reference synthetic sample; scenarios parameterised by `effect_k` and normalised shares (nine scenarios); truth test records are real (lineage, primary disease) pairs drawn with probability 1/|component|, and the truth MCSE is recorded; the R rule reports `R_rule_not_met` instead of defaulting, plus `recheck_required`; truth and replicate checkpoints are verified on reuse; `operating_characteristics.csv` and `decision.json` are written once (a later run must produce identical bytes).

**Figures (`visualization/`):** all inputs and output paths are checked and every figure is built before anything is written; `svg.hashsalt` is fixed; sidecars are written atomically and carry `run_id` and the `evaluation_record.json` SHA-256.

## Triage module (D03.04; protocol §21)

`python scripts/generate_triage.py --config configs/triage.yaml`, investigator-run after `run_explainability.py`.

- `triage/rules.py`: pure functions. `pathway_evidence` / `rank_pathways` / `attach_external_evidence`; `cell_line_evidence` / `rank_discrepancies` / `replication_priorities`; shared tier vocabulary and `order_by_tier` (tier, then fixed tie-break keys, then a 1-based `rank`).
- `triage/report.py`: strict config (`TriageConfig`, no hidden defaults); `verified_provenance` checks that the evaluation record matches the experiment config and run ID, that the run manifest is unchanged since evaluation, and that `stability.json` belongs to the same config; `cell_line_metadata` reads hash-verified QC metadata; `generate_triage` writes `results/triage/<run_id>/` once.
- Inputs used: `comparisons.csv` (primary verdict), `oof_predictions.csv`, `explainability/importance_per_task.csv`, `coefficient_signs.csv`, `gene_set_tests.csv`, `gene_set_score_correlation.csv`, QC `eligibility.csv`, an optional curated evidence CSV.
- Small additions to earlier steps (needed by triage, nothing executed): `oof_predictions.csv` now carries the SD, min and max of each record's prediction across CV repeats; explainability writes `gene_set_score_correlation.csv` (Spearman correlation of set scores on the eligible lines; features only).
- Deferred, with missing inputs listed in `triage_manifest.json`: new unassayed DepMap lines; per-tissue reproducibility of gene-set importance.
- Tests: `tests/test_triage.py` (synthetic fixtures; no model fitting, so no `model_fit` marker).
- After the statistical review (D03.05): rules follow protocol §21 as revised; `criteria_text` is the single wording source for outputs (`triage_manifest.json`) and fig_s04.

## Methods diagrams (D03.05)

`python scripts/generate_figures.py --config configs/diagrams.yaml` renders fig_04, fig_s04, fig_s05 and fig_s06 through `visualization/render.py:render_diagrams`, reusing `figures.style`, `figures.save` and the sidecar format (`data_provenance: conceptual_diagram`). Drawing code: `visualization/diagrams.py` (millimetre coordinates, box kinds distinguishable in greyscale). `tests/test_diagrams.py` checks label fit, text overlap, font size, rule-text consistency and write-once rendering. Specs: `figures/specs/fig_04_*.yaml`, `fig_s0[4-6]_*.yaml`.

## Test plan

Run `pytest` with synthetic fixtures for the contracts above, plus golden-file tests for the metric functions on hand-computed toy inputs. No real data are used in tests.
