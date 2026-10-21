# Phase 01 investigator-run QC checklist

**Who runs this:** the investigator. Claude Code cannot run downloads, `pytest` or the QC (project hook; CLAUDE.md).

**What it produces:** identity, grouping and availability tables, and counts. **No mSF2 value, summary statistic or plot is produced or looked at.** The only outcome-derived information is a per-record "invalid on the raw scale" flag, plus aggregate counts of invalid sub-types (blank, non-numeric, non-finite, < 0, > 1). That is an amendment of D01.05 (see D01.18). Seeing outcome distributions before the protocol freeze would invalidate the pre-specification.

**Status:** updated 2026-10-21 for the remediated code (`docs/phase_01_remediation_report.md`). It supersedes `docs/phase_01_recommendations.md` §5.

Tick each box and note the date. Anything that fails stops the sequence; record it in `docs/decision_log.md`.

---

## Stage 0: decisions to record before running anything

These must be fixed *before* any count is seen. Each one lives in `configs/preprocessing.yaml` or the decision log.

- [ ] Phase_00 → phase_01 gate signed, or an exception recorded.
- [ ] Solid, haematopoietic and excluded lineage lists accepted (config `population`).
- [ ] `non_cancer_markers` accepted. They are completed in Stage 2 from the Model.csv value lists, which are metadata only.
- [ ] `min_components_per_tissue` (defines T10) and `outer_folds` accepted.
- [ ] Rules accepted:
  - component edge rule (all candidates, D01.20; ratify via P01.14);
  - `lineage_span_scope` (P01.13; default `record_eligible`);
  - flag propagation;
  - a component spanning lineages is excluded;
  - links that were not expanded go to review.
- [ ] Provisional floors accepted as descriptive (O01.08).
- [ ] Tolerance for unresolved or ambiguous IDs fixed.
- [ ] Outcome-validity exclusion accepted (D01.18).

## Stage 1: code readiness

- [ ] Review the remediation (`docs/phase_01_remediation_report.md`) and approve or amend it.
- [ ] Review `.claude/settings.json` and the hook, and confirm that the Write/Edit hook is active: open `/hooks` in Claude Code, or restart Claude Code.
- [ ] Run the checks below, record the pytest summary line in the decision log, then commit the working tree (P00.01). Claude Code does not commit. Formatting comes before the commit so that the tree stays clean.

The existing environment `moringa-rad` is used for now (investigator instruction, 2026-10-21). The configured future environment is `explainable-radiosensitivity-ml` (D01.21); create it only after the environment review.

```bash
conda activate moringa-rad
git apply --check docs/proposed_patches/2026-10-21_hook_lint_format.patch \
  && git apply docs/proposed_patches/2026-10-21_hook_lint_format.patch   # protected .claude/ fixes
ruff format tests                                  # remaining cosmetic formatting (src/scripts done)
ruff format --check . && ruff check . --extend-select EXE,BLE,SIM,RUF100
python3 -I -m compileall -q src tests scripts .claude/hooks
python -m pytest -q
```

These tests use only mock payloads and labelled synthetic fixtures. They fit no models and download nothing. Some create temporary files and symlinks under pytest's `tmp_path`.

## Stage 2: acquisition (DepMap, then Cellosaurus, in one command)

```bash
python scripts/acquire_data.py --dry-run     # optional: show the plan
python scripts/acquire_data.py               # add --yard for the secondary Yard files
python scripts/acquire_data.py --verify      # offline integrity check
```

- [ ] All DepMap MD5 and size checks passed (the script stops on any mismatch). Files and `SHA256SUMS` are now read-only.
- [ ] Copy each `SHA256SUMS` line into the matching manifest `sha256` field, so the hashes are under version control and not only in the gitignored `data/raw`.
- [ ] Yard xlsx opened by hand. Record its sheet names, columns, identifier type, number of lines and version (533, 511 or 498).
- [ ] Look at the first ~300 bytes of the expression file and confirm the first column holds `ACH-` IDs.
- [ ] Record from `Model.csv`, as metadata only and without joining CLARIFi:
  - the header (column names);
  - the distinct `OncotreeLineage` values;
  - the distinct `OncotreePrimaryDisease` values;
  - the distinct `DepmapModelType` values;
  - whether `EngineeredModel`, `ModelType`, `OncotreeCode` and a doubling-time field exist.

  Then compare these with the config lists, add the exact non-cancerous label to `non_cancer_markers`, and record the changes.
- [ ] Record the distinct `ProfileType` values in `OmicsDefaultModelProfiles.csv`. The QC stops if none is `rna`.

## Stage 3: Cellosaurus results (fetched by the Stage 2 command)

- [ ] `acquire_data.py` printed the `COMPLETE.json` SHA-256. Record it in `configs/preprocessing.yaml` (`cellosaurus.complete_json_sha256`; the QC refuses to run while it is null). Also record it, the release, the access date and the round list in `data/manifests/cellosaurus__r56_0.yaml`.
- [ ] Check `batch_single_differences` in `COMPLETE.json`. Every ID was also queried on its own; differences are already included in the QC as extra candidates (which make a record ambiguous), but note them.
- [ ] Check `depmap_ids_without_record` in `COMPLETE.json`.
- [ ] Check `links_not_expanded` in `COMPLETE.json`. If it is non-empty, the link-round cap was reached; the QC will flag those components for review.
- [ ] **Spot-check batch semantics:** for 3 IDs picked from the CLARIFi ID list (not by outcome), compare the batch result with a single query in a browser. The URL is `https://api.cellosaurus.org/search/cell-line?q=dr:<ID>&fields=ac&format=tsv`.
- [ ] If the run failed, inspect `data/raw/cellosaurus/r56_0.partial`. Confirm the exact path ends in `.partial` before deleting it (this is a deletion inside `data/raw`), then re-run.
- [ ] **Commit the manifests and the config** (Stage 2 and Stage 3 edits) before Stage 4, so that the QC runs on a clean tree without `--allow-dirty`.

## Stage 4: identifier QC

```bash
python scripts/run_preprocessing.py --config configs/preprocessing.yaml --check-inputs
python scripts/run_preprocessing.py --config configs/preprocessing.yaml
# optional identifier-drift audit (needs: python scripts/acquire_data.py --audit-23q4)
python scripts/run_preprocessing.py --model-table-audit data/raw/depmap/23q4_v1/Model.csv \
  --out results/tables/phase_01/identifier_qc_23q4_v1_audit
```

Add `--allow-dirty` only if the tree cannot be committed. The diff hash is recorded either way.

- [ ] First run: record in `docs/phase_01_dataset_feasibility.md` §4, from `summary.json`:
  - `records`, the counts from initial CLARIFi to verified with expression;
  - `identity_issue_counts`;
  - `ids_concordant_name_discordant`;
  - `links_not_expanded`;
  - `eligibility.exclusion_reason_counts`;
  - `feasibility.primary`: n, T10, qualifying tissues, pooled and multiple-label components, strata, held-out-tissue training sizes and component-size histograms;
  - the `feasibility.sensitivity` blocks;
  - `moringa_lines`.
- [ ] Review by hand:
  - `ambiguous_matches.csv`;
  - `unmatched_records.csv`;
  - `duplicate_identifiers.csv`;
  - `problematic_entries.csv`, which may name the true identity of a contaminated line;
  - every `*_review` exclusion.

  Log each decision one per line in a resolution table. **Do not open or use mSF2 values when deciding.**
- [ ] Second run (audit): read the Model-table match counts and name mismatches against 23Q4 only.
- [ ] Apply the pre-fixed rules to n and T10 and record the outcome in the decision log. The floors are descriptive only; precision is decided by the phase_02 design analysis.

## Stage 5: cross-dataset overlap (not yet scripted, P01.08)

- [ ] Write and review the Yard name → ModelID → CVCL exact-match mapping, with a manual-review log.
- [ ] Rebuild the components over CLARIFi ∪ Yard, then count the overlap in both directions (counts only). Tier (c) stays blocked until this is done.

## Stage 6: manifests

For each acquired file, fill in:
- `access_date` (from `results/logs/phase_01/acquisition_log.tsv` or the sidecars);
- `retrieved_by` (a named person);
- `retrieval_method`;
- `sha256` and `size_bytes`;
- the MD5 match;
- `encoding`, `delimiter`, `line_terminator`, `n_lines` and `header`.

For Cellosaurus, also record the SHA-256 of `COMPLETE.json`, the release and the rounds.

A named human sets `provenance_status: verified` only after checking source, licence and endpoint.

## Stage 7: hand-back to Claude Code

Send Claude Code:
- both `summary.json` files and both `run_record.json` files;
- the Stage 2 header and value lists;
- the ID-resolution table;
- the overlap counts once Stage 5 exists.

QC tables contain CLARIFi names. **Do not commit them**: `results/tables/` is gitignored and the CLARIFi licence is unresolved. Do not send any file containing mSF2 values.
