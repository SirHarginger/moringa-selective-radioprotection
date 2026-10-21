# Decision log

One entry per decision. IDs follow `<type><phase>.<nn>`:
- `D` = decision applied;
- `P` = proposal awaiting investigator approval;
- `O` = open question for the investigator.

Example: `D00.03`. Entries from the first phase_00 pass were renumbered from the earlier `D0.x` / `P0.x` / `O0.x` scheme; the "Former ID" column keeps the mapping.

A phase gate is passed only when the investigator signs it off in the gate record at the end of this file.

## Resolved decisions

| ID | Decision | Basis | Former ID |
|---|---|---|---|
| D00.01 | Package `src/radiosensitivity_ml/` with `config.py`, `data/` (`provenance`, `identifiers`), `features/`, `models/`, `evaluation/` (`splits`), `explainability/`, `visualization/`. Docstring placeholders only | Investigator brief; software-architect, radiogenomics-curator | D0.1 |
| D00.02 | Old package name `moringa_radioprotection` not reused | software-architect, research-director | D0.2 |
| D00.03 | `configs/` is the only configuration folder. The empty, untracked `config/` was removed | Investigator brief | D0.3 |
| D00.04 | `figures/generated/` is the only figure output location; `results/` holds analytical outputs and tables. Earlier disagreement (software-architect preferred `results/figures/`) resolved by the investigator's brief | Investigator brief; figure-editor | D0.4 |
| D00.05 | Tracked provenance in `data/manifests/` (YAML per source and release) | radiogenomics-curator, reproducibility-auditor | D0.5 |
| D00.06 | CLARIFi manifest `data/manifests/clarifi__v1_0.yaml`: metadata verified; endpoint is literature-derived clonogenic SF2 (median per cell line) | radiogenomics-curator | D0.6 |
| D00.07 | Controlled `endpoint_class` vocabulary; endpoint classes never merged silently | radiogenomics-curator; CLAUDE.md | D0.7 |
| D00.08 | The Moringa linkage document uses only verified sources. PEF is never treated as SF2 | radiobiologist; investigator brief | D0.8 |
| D00.09 | `.gitignore` additions: secrets, caches, rendered figures, LaTeX build files, `graphify-out/`, source manuscripts | reproducibility-auditor; investigator brief | D0.9 |
| D00.10 | `CLAUDE.md` extended with project identity, phase naming (`phase_00`–`phase_05`) and the specialist-agent workflow. Safety text unchanged | Investigator brief | D0.11 (there was no D0.10) |
| D00.11 | Phase naming `phase_00` … `phase_05` | Investigator brief | — |
| D00.12 | Project identity "Explainable Radiosensitivity ML"; distribution and conda environment `explainable-radiosensitivity-ml`. Repository rename only proposed (P00.07) | Investigator brief | — |
| D00.13 | Naming: snake_case modules, folders and docs; figures `fig_01` / `fig_s01`; tables `table_01` / `table_s01` | Investigator brief; figure-editor | — |
| D00.14 | `pyproject.toml`: description, readme, empty runtime dependencies, `dev` extra (pytest, ruff), ruff and pytest settings | software-architect | part of P0.2 |
| D00.15 | Prototype packages in `environment.yml` marked LEGACY, not removed. Decisions deferred (see "Dependency decisions") | Investigator briefs (do not remove packages solely because the prototype used them) | part of P0.3 |
| D00.16 | Safety hook rewritten:<br>- invoked through `$CLAUDE_PROJECT_DIR`;<br>- per-segment allowlist;<br>- fails closed;<br>- no `-r` false positives;<br>- file operations may not touch `data/raw/` or `.claude/`;<br>- tests in `tests/test_safety_hooks.py` (live checks done; pytest not run by Claude Code) | Investigator brief; reproducibility-auditor; software-architect | P0.7 |
| D00.17 | Local annotated tag `archive/pre-radiosensitivity-ml` → `76f9e6f30042c55b22ef44e8ef1973ea0dadbc50` | Investigator brief | P0.1 (tag part) |
| D00.18 | `README_RESEARCH_SETUP.md` moved to `docs/claude_research_setup.md` | software-architect | — |
| D00.19 | Source manuscripts kept in `references/source_manuscripts/` (gitignored), with the tracked `manifest.yaml` | Investigator brief | — |
| D00.20 | Empty `docs/latex/` folder removed (no content; former files remain in the archive tag) | Investigator brief | — |
| D00.21 | **Retired** the prototype `Makefile` (its only target called deleted scripts) and the empty `requirements.txt`. Both are uncommitted deletions; originals remain in the archive tag | Investigator approval conditional on no active dependency; software-architect confirmed none (documentation only) | P00.04 |
| D00.22 | **Retired** `results/figures/` and `results/screening/` (tracked `.gitkeep` only); `.gitignore` rules and docs updated. Uncommitted deletions | As D00.21 | P00.05 |
| D00.23 | Moringa manuscript integrated:<br>- copied unchanged from the investigator's file `~/Downloads/Scanned manuscript RAMSRI.pdf` to `references/source_manuscripts/moringa_original.pdf` (identical MD5);<br>- checksums in `manifest.yaml`;<br>- extraction in `docs/moringa_scientific_linkage.md` with PDF/printed page references | Investigator brief; radiobiologist verification | O00.01 (partly) |
| D00.24 | CLARIFi licences recorded separately in the manifest:<br>- dataset (Zenodo) CC BY 4.0;<br>- article CC BY-NC 4.0.<br>`redistribution_allowed: unresolved`; stricter terms applied; raw file stays gitignored | reproducibility-auditor (sources accessed 2026-10-20) | part of O00.02 |
| D00.25 | CLARIFi row count corrected: 286 lines = header + **285** data rows (last line lacks a trailing newline; `wc -l` had undercounted). Matches the article's 285 cell lines. MD5 still matches | reproducibility-auditor flag; Claude Code `grep -c ''` | — |
| D00.26 | Scientific-connection section (§13 of the linkage document) adopted. README framing changed to wound-healing / proliferation context; "selective radioprotection" kept only as a hypothesis | research-director | — |

### phase_01 decisions (2026-10-21)

Phase_01 work started on the investigator's Phase 01 brief. The phase_00 gate below is still **unsigned** (see "Gate record"), so these decisions cover documentation and preparation only.

| ID | Decision | Basis |
|---|---|---|
| D01.01 | Claude Code does not download datasets. The project hook blocks `curl`/`wget` and was **not** weakened. Acquisition is scripted for the investigator (`scripts/acquire_phase_01.sh`, `scripts/fetch_cellosaurus_phase_01.py`) | CLAUDE.md ("do not bypass hooks"); D00.16 |
| D01.02 | DepMap **24Q4** (figshare DOI 10.25452/figshare.plus.27993248.v1, CC BY 4.0, published MD5s) is the pinned feature release. 23Q4 v1 `Model.csv` is used for the identity audit only | radiogenomics-curator; reproducibility-auditor re-confirmed IDs, sizes, MD5s and licence |
| D01.03 | Endpoint classes. Yard 2016 is `profiling_derived_survival` (CellTiter-Glo ATP, day 9; integral survival), never pooled with mSF2. GSE184119 is `gene_expression` (induced, normal cells): no-go as labels or features. NCI-60/Amundson deferred | radiobiologist, curator, statistical-reviewer; `docs/phase_01_endpoint_compatibility.md` R1–R10 |
| D01.04 | Endpoint rules R1–R10 adopted as the working proposal (primary target CLARIFi mSF2; Yard for transportability only; PEF and crystal-violet OD never targets) | radiobiologist; no specialist objected |
| D01.05 | No mSF2 summary statistics before the protocol freeze. Phase_01 outcome checks are limited to blank and non-numeric counts | statistical-reviewer SR-08 |
| D01.06 | Seven manifests created or updated: `depmap__24q4`, `depmap__23q4_v1`, `yard2016__ncomms11428_v1`, `cellosaurus__r56_0`, `geo_gse184119__suppl_20210925`, `iclac__v14`, plus CLARIFi descriptive checks. All new ones are `unverified`, not acquired | curator; auditor |
| D01.07 | **CLARIFi manifest corrected.** Top-level `licence: null` with `licence_terms_applied: CC-BY-NC-4.0`; `redistribution_allowed: null`; **`provenance_status: unverified`** (licence unresolved, no named human reviewer); new field `integrity_status: verified` | reproducibility-auditor (data_management.md §2) |
| D01.08 | Descriptive QC code added: `src/radiosensitivity_ml/data/qc_identifiers.py`, `scripts/qc_phase_01_identifiers.py`, `tests/test_qc_identifiers.py` (synthetic fixtures). It reads no outcome values, and from the expression file it keeps only model IDs | software-architect review (`research-code-review` skill); fixes applied |
| D01.09 | Scripts hardened after review: every download is checked before `.part` is renamed (MD5, file signature, size); `SHA256SUMS` is write-once and then verified; per-file acquisition log; the Cellosaurus fetch is all-or-nothing and checks the live release and the 1000-row cap; the QC verifies checksums before reading, refuses to overwrite a run, fails on missing columns, uses `QUOTE_NONE` for TSV, dedupes Cellosaurus records and strips the `RRID:` prefix only for comparison | software-architect P1-1…P2-4; reproducibility-auditor P1.1–P1.5 |
| D01.10 | Literature review: correction to the cross-assay novelty row. Cross-assay transfer is already published (Manem 2021; Kolnohuz 2024); only overlap-controlled transfer, reported as heterogeneity, is open | research-director D6 |
| D01.11 | Feasibility recommendation **CONDITIONAL GO** for **drafting** the phase_02 protocol, with the conditions in `docs/phase_01_recommendations.md` §2 and the n-thresholds in §3. Recommendation only; not a gate sign-off | research-director |

### phase_01 reconciliation (2026-10-21): proposed dispositions of O01.01–O01.12

**Source:** the investigator's Phase 01 reconciliation brief of 2026-10-21, which provisionally accepted CONDITIONAL GO. Full reasoning is in `docs/phase_01_reconciliation.md`.

**Status key:**
- **ID-prov:** investigator-directed in the brief, which uses the word "proposed". This is still provisional.
- **Prop:** proposed by specialists and Claude Code.
- **Open:** needs an investigator choice.

**No row below is a final approval.** The "Final approval" column stays empty until the investigator signs.

| ID | Proposed disposition | Basis | Status | Final approval |
|---|---|---|---|---|
| O01.01 | **Keep** the benchmark question: expression beyond tissue of origin, out-of-sample, clonogenic mSF2. Title amended to "…A prespecified, leakage-controlled benchmark with cross-assay transportability". "Preregistered" is not used unless formal registration happens (O00.07). "Explainable" stays out of the title. Closes O00.10 once signed | Brief; research-director | ID-prov | — |
| O01.02 | **Solid tumours primary.** Myeloid/Lymphoid form the haematopoietic sensitivity stratum. Pre-QC rule in reconciliation §3.2: non-cancer, engineered and `Other` lines excluded; blank or unknown lineage goes to human review | Brief; radiogenomics-curator (OncoTree level-1 verified; 24Q4 strings unverified) | ID-prov | — |
| O01.03 | **DepMap 24Q4 OncotreeLineage primary.** Sensitivity analyses: (i) CCLE suffix; (ii) Esophagus/Stomach split by primary disease. Small tissues pooled as "other solid" and never held out alone | Brief; curator | ID-prov | — |
| O01.04 | **Raw mSF2 primary.** −ln(mSF2) and logit(mSF2) sensitivity analyses are **mandatory** and frozen in the same protocol version, together with the boundary rule, the out-of-range prediction rule and one training loss. MAE on a transformed scale is a different estimand | Brief; radiobiologist; statistical-reviewer; research-director | ID-prov (scale) / Prop (mandatory sensitivity) | — |
| O01.05 | **Proliferation comparator B2:** tissue plus the in-fold mean of MSigDB Hallmark E2F_TARGETS and G2M_CHECKPOINT. Declared nested in and collinear with the expression block. S1 wording: "beyond tissue and a proliferation-correlated signal". DepMap doubling time is a sensitivity analysis only if the field exists (UNVERIFIED) | ml-methodologist; radiobiologist; research-director | Prop | — |
| O01.06 | **Paired ΔMAE versus tissue-only is the primary metric.** ΔRMSE, ΔR² and calibration are secondary and non-gating. Primary CI: Bates-type nested-CV interval, conditional on a synthetic coverage check; fallback Nadeau–Bengio corrected *t*; component bootstrap descriptive. δ comes from the anchors in reconciliation §4.3 (A4 checked against the A1 noise floor). **No number set.** Three-way LB/UB reporting | Brief; statistical-reviewer; research-director (disagreement 1: ml-methodologist preferred the bootstrap) | ID-prov (metric) / Prop (CI, δ rule) | — |
| O01.07 | **MSigDB Hallmark (50 sets).** Scoring: mean of in-fold z-scored log2(TPM+1); singscore is the alternative; GSVA is not primary. Before the freeze, verify the release string, GMT SHA-256, licence and gene mapping. Negative controls in reconciliation §4.5 | ml-methodologist | Prop | — |
| O01.08 | The §3 numbers are **relabelled** as provisional data-sufficiency floors (descriptive; not evidence of power). G-n becomes a design-analysis precision criterion (ADEMP simulation, run by the investigator, using metadata structure and literature effects only) | Brief; statistical-reviewer; research-director | ID-prov / Prop | — |
| O01.09 | **Resolved by investigator ruling.** Stability diagnostics are always reported, with thresholds relative to permuted and random-gene-set nulls. Attribution claims need both G-pred and G-stab. If G-pred fails: aggregate stability only, with named lists in the supplement only. Closes specialist disagreement D1 | Brief; ml-methodologist accepted; research-director | ID-prov | — |
| O01.10 | Yard: original Supplementary Data 1. **Both** transfer directions. Overlap excluded by component. Spearman ρ metric, with no target-domain fitting. Term: "cross-assay transportability", defined as across assays measuring different endpoints. List of forbidden words | Brief; radiobiologist; ml-methodologist | ID-prov / Prop | — |
| O01.11 | NCI-60 **deferred** until source overlap (SR-02) is resolved | research-director | Prop | — |
| O01.12 | **Yes:** request per-line counts and values from the CLARIFi authors (P01.02); retrieve Data S2 if available. The δ timing depends on this (O01.13) | statistical-reviewer; radiobiologist | Prop | — |

### phase_01 investigator rulings (brief "Phase 01 – Technical remediation and data-QC readiness", 2026-10-21)

The investigator gave **conditional approval** to the phase_01 scientific reconciliation, and ruled on the open items below. These rulings come from the investigator's brief; they are not Claude Code proposals. The phase gates remain unsigned.

**Preserved framework (unchanged):**
- paired ΔMAE as the primary comparison;
- tissue-only baseline;
- raw mSF2 as the primary scale;
- separate validation tiers.

| ID | Investigator ruling | Status |
|---|---|---|
| O01.13 | δ must be justified independently and fixed before the confirmatory protocol is frozen. Protocol drafting may continue without a numerical δ | **Ruled** |
| O01.14 | Repair safety and data-integrity vulnerabilities **before** QC execution | **Ruled.** Implemented in D01.17 and P01.07/P01.09/P01.10; awaiting investigator review |
| O01.15 | Confidence-interval methods need investigator-controlled coverage assessment before adoption. Use exploratory cross-assay **rank concordance** where appropriate. Keep Moringa as **supplementary** biological context | **Ruled** |
| O01.16 | Standardise configured environment naming; document the legacy environment separately | **Ruled; applied** (D01.21) |

**phase_01 reconciliation decisions applied (documentation only)**

| ID | Decision | Basis |
|---|---|---|
| D01.12 | `docs/phase_01_reconciliation.md`, `docs/phase_01_static_code_review.md`, `docs/phase_01_investigator_qc_checklist.md` and `docs/phase_02_protocol_outline.md` created | Investigator brief 2026-10-21 |
| D01.13 | "Preregistered" replaced by "prespecified" in `phase_01_recommendations.md`, `phase_01_novelty_assessment.md` and `README.md`. The unjustified example margin "ΔR²_oos ≥ 0.03" withdrawn. Superseding notes added to recommendations §3/§4 and novelty §6/§10.4 | research-director; brief |
| D01.14 | Correction to `phase_01_dataset_feasibility.md` §5.3: the Cellosaurus `hi`/`oi` links are parsed but not yet output | radiogenomics-curator; reproducibility-auditor |
| D01.15 | Yard endpoint wording fixed to "ATP-based (CellTiter-Glo) day-9 integral survival". A relayed summary had said "proliferation/viability" | Claude Code, against D01.03 |

**phase_01 technical remediation (2026-10-21; code written, nothing executed; awaiting investigator review)**

| ID | Decision | Basis |
|---|---|---|
| D01.16 | Identifier QC rebuilt as six modules: `provenance`, `cellosaurus`, `qc_identifiers`, `components`, `eligibility`, `qc_report`. Pre-fixed rules live in `configs/phase_01_identifier_qc.yaml`; the scripts are rewritten. Details: `docs/phase_01_remediation_report.md` | Investigator brief; software-architect, radiogenomics-curator, reproducibility-auditor, statistical-reviewer, ml-methodologist |
| D01.17 | **Hook and settings edited by Claude Code under the brief's explicit authorisation** (O01.14):<br>- Write/Edit/MultiEdit/NotebookEdit path guard;<br>- Bash indirect-write rules;<br>- `.git/` and `.venv/` protected;<br>- `Edit(...)` deny rules and ask rules in `.claude/settings.json`.<br>From now on, `.claude/` changes follow the procedure in `docs/architecture.md` §7.1. This closes P01.09, pending investigator review | Investigator brief; reproducibility-auditor; software-architect |
| D01.18 | **Proposed amendment of D01.05 (needs ratification, P01.11).** The QC classifies the outcome cell only as valid or invalid on the raw scale (blank, non-numeric, non-finite, < 0, > 1). It writes one per-record flag and aggregate counts, and invalid records are excluded pending review. Counts of exactly 0 and exactly 1 were **removed** before any run: the statistical-reviewer judged them an outcome look | statistical-reviewer; ml-methodologist |
| D01.19 | **Deviation record.** On 2026-10-21, a Claude Code header check (`head -3 data/raw/CLARIFi.csv`) displayed the mSF2 values of two cell lines (the first two data rows). No statistic was computed and the values were used for nothing. Later reads touch identifiers only. Reported to the investigator | Claude Code (self-report) |
| D01.20 | **Implemented as proposed; needs ratification (P01.14).** Component edge rule: **every** Cellosaurus candidate and the DepMap RRID link a record, not only accepted matches. This is conservative and can only merge components; edges from ambiguous candidates are counted. It changes a §3.3 rule that was fixed before QC, so it can change the population. `docs/phase_01_reconciliation.md` §3.3 is amended to match. Lineage span is checked over record-eligible members by default (`lineage_span_scope`, P01.13) | ml-methodologist; radiogenomics-curator; statistical-reviewer (asked for the rule to be recorded) |
| D01.22 | **Sprint 2026-10-21 (investigator: 307 tests passed).** Formatting and lint applied to `src`/`scripts`; the 6 extended-rule findings are fixed or justified. The 5 in `.claude/hooks` go via `docs/proposed_patches/2026-10-21_hook_lint_format.patch` (not applied; §7.1). `ruff format tests` left to the investigator. Interim environment `moringa-rad`; configured future environment `explainable-radiosensitivity-ml` | Investigator brief |
| D01.23 | Cellosaurus live pilot (WebFetch, nothing saved): batched `dr:(…OR…)` returns all 3 test IDs; batched `ac:(…)` works; MCF-7 has an `oi` sister line, Hs 631.T (CVCL_N481). Recorded in the Cellosaurus manifest. DepMap 24Q4 file IDs, sizes and MD5s re-confirmed on figshare. Column schema not fully confirmable without the files; the QC fails loudly on mismatch | Claude Code |
| D01.24 | `docs/protocol.md` DRAFT v0.1 and `docs/phase_03_implementation_spec.md` written. **Revisions after one review round** (statistical-reviewer, ml-methodologist; both: "acceptable as a draft"):<br>- component-weighted ΔMAE proposed as primary;<br>- confirmatory test is LB > δ, with four reporting categories;<br>- M1′ added for S1;<br>- strandedness covariate in every arm (proposed);<br>- offset models refit their baseline inside every fit;<br>- tier (a) graph CLARIFi-only;<br>- permutation p-values with BH for G-stab | statistical-reviewer; ml-methodologist |
| D01.25 | **Single Python workflow.**<br>- `scripts/acquire_data.py` (new; logic in `data/acquisition.py`, with the Cellosaurus fetch moved into the package as `data/cellosaurus_fetch.py`) replaces `acquire_phase_01.sh` and `fetch_cellosaurus_phase_01.py`. The shell script is kept, marked SUPERSEDED, for GEO/ICLAC only.<br>- `qc_phase_01_identifiers.py` is renamed `scripts/run_preprocessing.py`, with a new `--check-inputs` option; `configs/phase_01_identifier_qc.yaml` is renamed `configs/preprocessing.yaml`.<br>- README rewritten with WORKING vs PLANNED commands. The resume design is in `docs/phase_03_implementation_spec.md`.<br>- Reviewed by software-architect, reproducibility-auditor and ml-methodologist; all fixes applied | Investigator brief 2026-10-21 |
| D02.01 | **Real QC cohort confirmed (2026-10-21).** Re-checked against `summary.json` (SHA-256 `b09e74ec…f402`): 285 → 273 verified with expression → **241 eligible records / 237 components** (4 pairs), T10 = 9, retaining-problematic 252/247 (T10 = 10), candidate graph 237. Strandedness among eligible default profiles: 7 stranded (ACH-000095, -000337, -000455, -000468, -000979 DU145, -001001, -001061). Curator review: ACH-000921 stays excluded (CVCL_0463 contaminated; NCI-H1339 CVCL_A472 has no DepMap ID); the 4 pairs are correct; no source correction changes the primary cohort. The QC ran with `--allow-dirty` on commit 76f9e6f; re-run on a clean commit before the freeze | Claude Code (verified from outputs); radiogenomics-curator |
| D02.02 | `docs/protocol.md` **v0.2**:<br>- full 20-level ridge tissue comparator (pooling used only for stratification), with granular, pooled and suffix sensitivities;<br>- strandedness removed from the primary models and handled by a sensitivity exclusion (P-S4);<br>- exact aggregation and Err-type estimand;<br>- ADEMP interval-selection simulation with a mechanical adoption rule;<br>- δ Option A vs Option B presented for an investigator ruling;<br>- sensitivity populations P-S1 to P-S5.<br>Freeze still blocked by the [OPEN] items | ml-methodologist; statistical-reviewer; radiogenomics-curator; research-director |
| D03.01 | **Investigator ruling (2026-10-21): Option B.** Estimation-focused benchmark of paired component-weighted ΔMAE. It reverses the O01.13 withdrawal of the LB > 0 test.<br>- One-sided superiority at α = 0.05 is allowed only through a simulation-adopted interval.<br>- No claim of clinically or biologically meaningful improvement.<br>- BH q = 0.05 for pathway families.<br>- P = B = 1000 is the starting control budget, checked against p-value resolution and cost.<br>- Boundary rule (E).<br>- Protocol v0.3 | Investigator brief (Phase 03) |
| D03.02 | Phase 03 pipeline implemented (code, configs, tests; nothing executed by Claude Code). Model IDs are renamed to the investigator's family (M0, M1, M1P, M2, M2P, M2X, M3). The whole-transcriptome model (old M4) is dropped to keep the family small. **The Bates nested-CV interval (I2) is not implemented**; under the frozen protocol fallback, the adoption rule is applied to Nadeau–Bengio and naive component t. The `identity_sound` population (P-S5) raises NotImplemented, because its rule is not yet in the QC outputs. Tier (c) is still blocked (P01.08) | Claude Code; reviews in D03.03 |
| D03.03 | **Phase 03 review round and fixes (2026-10-21; code only, nothing executed, tests not run).** Five read-only reviews: software-architect, ml-methodologist, statistical-reviewer, reproducibility-auditor, research-director. All accepted findings are applied; details in `docs/phase_03_implementation_spec.md` "Review fixes". Main changes:<br>- control draws seeded per draw; component-level within-lineage permutation;<br>- verdict only for the primary comparison; "expression worse" wording removed;<br>- evaluation and explainability check config, run and decision-file hashes;<br>- simulation: lineage-conditional expression, fixed signal map, `effect_k` scenarios (nine), truth MCSE, no silent R default;<br>- protocol §13–§16 updated to match; P = B = 1999 recommended (1000 the floor); stale "q = 0.10" line removed.<br>The simulation scenario values remain [OPEN] design parameters | software-architect; ml-methodologist; statistical-reviewer; reproducibility-auditor; research-director |
| D03.04 | **Lint fixes and triage module (2026-10-21; code only, nothing executed).** Investigator ran `pytest -m "not model_fit"` (357 passed, 4 deselected). Lint: `FetchSettings` default built per call; unused loop variable and dict iteration fixed; invalid `# fmt: skip` comments removed; `pyproject.toml` gains `[tool.ruff.lint]` (extend-select I, BLE, RUF100; ρ allowed in labels; E402 ignored in `scripts/`, which add `src/` to the path before importing). Not changed: PERF401 loop-to-comprehension suggestions in split/QC code (readability of audited code), hook findings (pending patch). Triage (protocol §21; `configs/triage.yaml`): gene-set, measured-cell-line and discrepancy rankings with prespecified tiers A/B/C/`not_prioritised`/`not_rankable`; new DepMap lines and tissue reproducibility deferred. Thresholds await confirmation at the freeze. No specialist review of the triage rules yet | Investigator brief (Phase 03 verification); Claude Code |
| D03.05 | **Targeted statistical review of the triage rules, applied (2026-10-21; code only, nothing executed).** statistical-reviewer (read-only subagent): 5 must-fix, 7 should-fix; overall design accepted. Applied:<br>- M1: claim level per tier; only tier A may be called "associated in-model, hypothesis-generating";<br>- M2: the "outside both repeat ranges" condition is removed from tier A; ranges renamed `repeat_prediction_range_*`, descriptive only, stated not to be prediction intervals;<br>- M3: A/B need ≥ 1000 completed draws of each null (`min_null_draws`), counted from actual draws; `g_stab_feasible` recorded;<br>- M4: empirical p uses valid draws only; incomplete control draws are refused;<br>- M5 and S6: "BH-adjusted", not "FDR-controlled"; null interpretations written into §18 and §21;<br>- S1: tier B needs the permuted-outcome null; `nulls_passed` column;<br>- S2: `tested_importance_repeat0` vs `mean_importance_all_fits`;<br>- S3: shares worded as proportions of overlapping fits; all 5 × R fits required;<br>- S4: percentile definition, regression-to-the-mean and shrinkage notes; observed-value percentile and signed residuals added;<br>- S5: ties share the maximum percentile;<br>- S7: tier reason names the dominant sign.<br>Not done: Benjamini–Yekutieli sensitivity column (optional). The reviewer did not re-check the fixes. The reviewer confirmed from the brief that control draws reuse repeat-0 outer splits; Claude Code verified this in `models/run.py:task_list`. **Methods diagrams added:** fig_04, fig_s04–fig_s06 (`configs/diagrams.yaml`; conceptual, no data); fig_s04 text comes from `triage.rules.criteria_text`. Not rendered by Claude Code; a layout test checks label fit | statistical-reviewer; investigator brief |
| D03.06 | **Final Phase 03 test corrections (2026-10-21; code only).** Investigator run: 374 passed, 1 failed, 4 `model_fit` deselected; diagrams v1 rendered. Failure `test_discrepancy_ranking_separates_technical_review` was an implementation defect: `cohort_percentile` ranked ties at the maximum (D03.05 change), so a value shared by the whole cohort (here identical repeat spread) put every line at the 100th percentile and flagged all as "technical review first". Fixed to (1 + lines with a strictly smaller value) / n (ties never raise a percentile); regression test added; the test's expectation was correct and is unchanged. Protocol §21, `configs/triage.yaml` and fig_s04b wording updated; diagrams bumped to v2. Ruff: implicit string concatenations in list/tuple literals parenthesised or joined; `itertools.pairwise`; `typing.Self` in a test helper; `min()` in a test; ×, −, – allowed as intended typography | Investigator brief; Claude Code |
| D01.21 | Configured environment name is `explainable-radiosensitivity-ml` in every current command. The legacy `moringa-rad` is documented in `README.md`; historical documents are unchanged | O01.16 |

## Dependency decisions (deferred; nothing removed)

| Package | Current justification | Decided in | Keep only if |
|---|---|---|---|
| requests | Prototype download scripts | phase_01 → phase_03 | Download logic is written for a verified source, with permission; otherwise use the standard library |
| tqdm | Prototype progress bars | phase_03 | A documented need exists (not essential) |
| rdkit | Prototype chemical fingerprints | phase_02 | The protocol includes compound or structure features (see O00.08) |
| xgboost | Prototype benchmark | phase_02 | The protocol prespecifies it after the scikit-learn baselines |
| openpyxl | Prototype spreadsheet input | phase_01 | A verified source is distributed only as `.xlsx` |

All packages are locked after the phase_03 environment review (P00.02, P00.03). Note: `environment.yml` pins Python 3.11, while the local `.venv` runs a newer Python. `pyproject.toml` allows ≥ 3.11; the environment review should choose one target.

## Awaiting investigator approval

| ID | Proposal | Raised by |
|---|---|---|
| P00.01 | Commit the working-tree deletions (prototype files plus D00.21 and D00.22). The tag preserves the prototype. Claude Code does not commit | reproducibility-auditor |
| P00.02 | Declare runtime dependencies with lower bounds; the human then generates and commits a lockfile (phase_03) | software-architect, reproducibility-auditor |
| P00.03 | Act on the dependency decisions above | software-architect |
| P00.06 | Untrack all of `graphify-out/` (the index still lists it; most files are already deleted on disk, and `.graphify_root` contains a machine-specific path): `git rm -r --cached graphify-out`. Files left on disk are kept and stay ignored | reproducibility-auditor |
| P00.07 | Rename the GitHub repository and remote URL to `explainable-radiosensitivity-ml`. Not done | Investigator brief |
| P00.08 | Keep the settings deny rule `Bash(*python* *)`; the investigator runs compile checks and pytest | reproducibility-auditor |
| P00.09 | Add `"onFailure": "block"` to the hook settings, if the installed Claude Code version supports it (not verified) | reproducibility-auditor |
| P00.10 | phase_02 gate: molecular models must beat tissue-only, study-only and proliferation-only baselines under grouped splits. **Amendment proposed (P01.03)** | research-director |
| P01.01 | Investigator runs the phase_01 commands (now `docs/phase_01_investigator_qc_checklist.md`; the recommendations §5 block is historical) and sends `summary.json` | Claude Code |
| P01.02 | Contact the CLARIFi corresponding author (Oike T): licence and Zenodo deposit; values and studies per line, and how the median was formed; DepMap release; whether Amundson/NCI-60 or Yard values are among the 926 sources | statistical-reviewer SR-01/SR-02; auditor; research-director |
| P01.03 | Amend P00.10: drop the "study-only" baseline (CLARIFi has no per-line study information) or make it conditional on P01.02 data | research-director D7 |
| P01.04 | Adopt the n/T₁₀ thresholds of `docs/phase_01_recommendations.md` §3 **before** running the QC | research-director |
| P01.05 | Supplementary novelty search (Scholar, Scopus, Web of Science, forward citations, preprints); verify all quantitative values against PDFs | literature-reviewer; research-director |
| P01.06 | Update `data/manifests/_template.yaml` with the optional fields now used by the manifests | reproducibility-auditor |
| P01.07 | **QC code patches, required before any QC output is used for decisions:**<br>- output the Cellosaurus `hi`/`oi` links and name;<br>- require `hi`/`oi` unless `--no-hierarchy` is passed;<br>- add a pure `build_components()`;<br>- add the solid-rule filter and optional `EngineeredModel`/`ModelType`/`OncotreeCode` columns;<br>- emit *n* and T₁₀ per taxonomy;<br>- add alias-duplicate checks;<br>- add a Cellosaurus `COMPLETE.json` marker;<br>- verify `release_info`;<br>- flag mixed releases;<br>- add a non-numeric outcome count.<br>Synthetic-fixture tests for each. Software-architect review once written. Static review D1, D1b, D2, D2b, D2c, B4, C1, C3, D3. **Status 2026-10-21:** implemented (D01.16); tests written but not run; awaiting investigator review | reproducibility-auditor; radiogenomics-curator; ml-methodologist; research-director |
| P01.08 | Write a Yard name → ModelID → CVCL exact-match mapping script with a manual-review log (not yet scripted) | radiogenomics-curator |
| P01.09 | **Safety hook and settings hardening:**<br>- `Write`/`Edit` deny rules for `data/raw/**` and `.claude/**`;<br>- forbid `ruff --fix-only`/`--output-file`;<br>- block `sort -o`, `uniq IN OUT` and `tree -o`;<br>- path-check git `mv`/`add` and deny `add -f`;<br>- normalise paths and handle `cd`.<br>Plus tests. Static review E1–E5. **Status 2026-10-21:** implemented by Claude Code under O01.14 (D01.17); awaiting investigator review and test run | reproducibility-auditor |
| P01.11 | Ratify D01.18 (outcome-validity exclusion and aggregate invalid-type counts before the freeze) or amend it | statistical-reviewer |
| P01.12 | Sensitivity-analysis transform rules (−ln, logit): domain and boundary specification in `docs/phase_01_remediation_report.md` §5. Fix option E or O before the freeze, without looking at counts | statistical-reviewer; radiobiologist (earlier pass) |
| P01.14 | Ratify D01.20 (all-candidate component edges) before QC outputs are opened. Decide together with P01.13 | research-director |
| P01.15 | Investigator to confirm:<br>- whether author-supplied per-line spread (anchor A5) counts as "independent" justification of δ (O01.13);<br>- whether the working title keeps "with cross-assay transportability", given O01.15 makes cross-assay analysis exploratory rank concordance (the research-director notes this weakens the title and the D01.10 novelty claim). Title not changed | research-director |
| P01.16 | Before the confirmatory freeze, decide the threshold rule (P01.04) and `min_components_per_tissue` = 10 (T10) | research-director |
| P01.13 | Investigator rulings needed on:<br>- whether an ineligible member (e.g. a haematopoietic line from the same donor) may exclude a solid line through `component_spans_lineages`. Implemented default `lineage_span_scope: record_eligible` = no, as recommended by the research-director; `all_members` = yes;<br>- whether "ids concordant, name discordant" records may be cleared by hand against the DepMap rename history | ml-methodologist; radiogenomics-curator |
| P01.10 | Low-severity acquisition fixes:<br>- GEO `filelist.txt` HTML check;<br>- acquisition log outside `data/raw`;<br>- `chmod a-w` after download;<br>- CLARIFi SHA check in the Cellosaurus fetch;<br>- consistent `#` handling;<br>- sidecar status check (static review A1, A3–A5, B1–B3, B5, C2, C4) | reproducibility-auditor |

## Open questions

| ID | Question |
|---|---|
| O00.01 | Moringa manuscript (partly resolved, D00.23):<br>- supply printed pages 3 and 7–12 (extraction and culture methods, end of Discussion, references);<br>- give authors, citation and publication status;<br>- explain how *A*D was computed (sign, units, SE), since the tabulated *A*D values do not match the plotted changes in OD |
| O00.02 | CLARIFi:<br>- confirm the licence with the authors (Zenodo CC BY 4.0 vs article CC BY-NC 4.0);<br>- confirm who uploaded the Zenodo record;<br>- how the median was formed (values per line);<br>- which DepMap release |
| O00.03 | Primary endpoint: CLARIFi mSF2 only, or other clonogenic sources too? |
| O00.04 | Feature types and their source release |
| O00.05 | External validation dataset(s) |
| O00.06 | Target journal |
| O00.07 | OSF preregistration: yes or no |
| O00.08 | Prototype compound-potency direction. research-director recommends archiving it |
| O00.09 | Permissions for downloads and installs; compute for phase_04 |
| O00.10 | Repository framing: the manuscript is about radiation-modified proliferation and wound healing, not selective radioprotection. Confirm the project framing (supports P00.07). See O01.01 |
| O01.01 | Accept the reframing to a prespecified benchmark (formerly worded "preregistered"; see the dispositions table) of expression beyond tissue, and the working title (`docs/phase_01_recommendations.md` §4) |
| O01.02 | Primary population: solid tumours only (haematopoietic lines in a sensitivity analysis)? |
| O01.03 | Tissue taxonomy: OncotreeLineage (24Q4), CCLE suffix (24) or the article's 28 types? |
| O01.04 | Outcome scale: raw mSF2 or logit? |
| O01.05 | Definition of the proliferation baseline |
| O01.06 | Primary metric and margin |
| O01.07 | Gene-set collection and version |
| O01.08 | Thresholds for the identifier QC (see P01.04) |
| O01.09 | **Unresolved specialist disagreement D1.** If the predictive gate fails, are attribution-stability metrics still reported? The research-director says yes, with no biological interpretation; the ml-methodologist says they are meaningful only if the gate passes |
| O01.10 | Yard version (original Supplementary Data 1, or a RadioGx 498/511-line version) and transfer directions |
| O01.11 | NCI-60: defer until source overlap is resolved? |
| O01.12 | Retrieve CLARIFi Data S2 and/or ask the authors for per-line counts? |
| O01.13 | **RULED 2026-10-21** (see "phase_01 investigator rulings"). Original question: δ fallback if δ cannot be fixed by the freeze. The fallback is withdrawn |
| O01.14 | **RULED 2026-10-21:** repair before QC execution (the research-director's position) |
| O01.15 | **RULED 2026-10-21:** CI methods adopted only after coverage assessment; cross-assay is exploratory rank concordance; Moringa is supplementary. The terminology question ("cross-assay" vs "cross-endpoint") is carried into P01.15 |
| O01.16 | **RULED 2026-10-21; applied** (D01.21) |

## Agent consultations

| Date | Pass | Agents (subagent delegation) | Skills |
|---|---|---|---|
| 2026-10-20 | phase_00 architecture | software-architect, research-director, radiobiologist, radiogenomics-curator, reproducibility-auditor, figure-editor | publication-figures, research-code-review |
| 2026-10-20 | phase_00 standardisation | software-architect, research-director, radiogenomics-curator, reproducibility-auditor, figure-editor | research-code-review |
| 2026-10-20 | phase_00 closure | radiobiologist (manuscript extraction and verification), research-director (ML linkage), reproducibility-auditor (licence, readiness), software-architect (legacy cleanup) | scientific-integrity and reproducible-python rules applied; skills not re-invoked |
| 2026-10-21 | phase_01 | literature-reviewer ×2 (Part A: ML and tissue; Part B: datasets, normal cells, plant extracts); radiogenomics-curator (source verification, acquisition specification); radiobiologist (endpoint compatibility, Moringa linkage); ml-methodologist (feasibility, novelty, leakage); statistical-reviewer (independence, bias); research-director (synthesis, decision; received the other specialists' inputs as **summaries relayed by Claude Code**); software-architect (code review); reproducibility-auditor (provenance audit, web spot-checks). figure-editor not used | literature-evidence-map, dataset-feasibility, leakage-audit, research-code-review (applied by the agents; noted in their reports) |
| 2026-10-21 | phase_01 reconciliation | statistical-reviewer (metric, CI, δ, sample size, gates); ml-methodologist (validation tiers, comparators, controls, leakage, explanation); radiobiologist (scale, δ anchors, Yard wording, Moringa E3, proliferation confound); radiogenomics-curator (solid rule, components, QC dependencies, taxonomy); reproducibility-auditor (static audit of scripts, tests, hook); research-director (synthesis; received the others as **summaries relayed by Claude Code**). All ran as read-only subagents. Not consulted: literature-reviewer, software-architect, figure-editor | protocol-first, leakage-audit, research-code-review (Claude Code read and applied them; the agents applied their own lenses) |
| 2026-10-21 | phase_01 technical remediation | Code review round:<br>- software-architect: maintainability, test tracing; found 1 failing test, since fixed;<br>- radiogenomics-curator: identity handling;<br>- reproducibility-auditor: integrity and hook, then a narrow re-check of the revised hook;<br>- statistical-reviewer: sufficiency of QC outputs, outcome blinding, transform domains;<br>- ml-methodologist: split keys and leakage.<br>Final review round: see `docs/phase_01_remediation_report.md` §8. claude-code-guide: hook payload and permission-rule syntax (docs lookup). All read-only subagents | research-code-review, dataset-feasibility, leakage-audit (applied by Claude Code and the agents) |
| 2026-10-21 | phase_03 triage statistical review | statistical-reviewer (targeted, read-only: repeat ranges vs prediction intervals, null interpretation, thresholds, percentiles). Findings applied by Claude Code (D03.05); not re-checked by the reviewer | — |
| 2026-10-21 | phase_03 implementation review | software-architect (structure, interfaces), ml-methodologist (leakage, controls, tuning), statistical-reviewer (estimand, intervals, simulation, multiplicity), reproducibility-auditor (provenance, resume, write-once), research-director (claims and wording). All read-only subagents; findings applied by Claude Code (D03.03). No reviewer re-checked the fixes | research-code-review, leakage-audit, protocol-first (applied by Claude Code) |

**Phase_01 reconciliation outcome:**
- D1 is closed by the investigator's ruling (O01.09), pending signature.
- New open items: O01.13 (δ fallback) and O01.14 (hook precondition).
- Reconciled disagreements awaiting confirmation: O01.15.

**Phase_01 unresolved disagreement (first pass):** D1 (explanation stability when the predictive gate fails), recorded as O01.09. All other disagreements (D2–D7) were reconciled by the research-director, pending investigator approval (`docs/phase_01_novelty_assessment.md` §10.6).

## Gate record

| Gate | Date | Approved by | Notes |
|---|---|---|---|
| phase_00 → phase_01 | — | — | Awaiting investigator review of `docs/phase_00_verification.md` (recommendation: CONDITIONAL PASS). The Phase 01 brief was received on 2026-10-21 but is not a sign-off. A `.pytest_cache` dated 2026-10-21 03:17 with no `lastfailed` file is consistent with a passing hook-test run, but does not prove it (auditor). Investigator: sign here or record an exception |
| phase_01 → phase_02 | — | — | Awaiting investigator review of `docs/phase_01_recommendations.md` and `docs/phase_01_reconciliation.md` (updated recommendation 2026-10-21: CONDITIONAL GO, protocol **drafting** only). The investigator's 2026-10-21 brief provisionally accepted CONDITIONAL GO; **this is not a gate sign-off.** Investigator: sign here |
