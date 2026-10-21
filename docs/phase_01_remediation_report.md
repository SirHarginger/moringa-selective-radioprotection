# Phase 01 technical remediation: static verification report

**Status:** submitted for investigator approval, 2026-10-21.

**Static only.** Claude Code executed no tests, downloads, QC, simulations or models. The only checks it ran were `ruff check` (default rules, passing) and live smoke tests of the Bash hook on harmless commands. Every statement that something "passes" below is either one of those checks, or a hand-trace by a reviewer, and is labelled as such.

**Scope:** the brief "Phase 01 – Technical remediation and data-QC readiness" (O01.13–O01.16 rulings; decision log D01.16–D01.21, P01.11–P01.13).

---

## 1. Readiness assessment

**CONDITIONAL PASS** for investigator-controlled QC execution. All six final reviewers gave this verdict independently (§8.2), and none found a high-severity issue in the final round.

The QC may be run once the investigator has:
1. run the tests in §6 and found them passing;
2. confirmed that the Write/Edit hook is active (`/hooks` or a restart);
3. ratified or amended D01.18 (P01.11), D01.20 (P01.14) and `lineage_span_scope` (P01.13) **before opening any QC output**;
4. completed Stages 0–3 of `docs/phase_01_investigator_qc_checklist.md`. This includes checking the 24Q4 strings and recording the `COMPLETE.json` hash in the config.

**Why not PASS:**
- no test has been executed;
- several input formats (24Q4 strings, Cellosaurus query semantics) can only be confirmed on the real files.

**Not covered by this verdict:** tier (c) and the G-n/K choice. Both stay blocked until the Yard mapping (P01.08) and the strandedness summary exist.

## 2. Data-protection controls

### 2.1 What changed

**`.claude/hooks/block_model_execution.py`**

Protected locations:
- `data/raw/` and `.claude/`;
- also `.git/` and `.venv/`, because git configuration and environment executables could turn allowed commands into arbitrary execution.

File tools (Write, Edit, MultiEdit, NotebookEdit):
- the `file_path`/`notebook_path` is resolved relative to the payload `cwd`, both lexically (`normpath`: `..`, `./`, `//`) and through symlinks (`realpath`);
- either resolution inside a protected location is denied;
- missing, empty or non-string paths, non-object input, and an unknown project directory are all denied (fail closed).

Bash (in addition to the earlier allowlist and redirection rules):
- File operations and `git add`/`git mv` may not name:
  - a protected path (substring backstop plus normalised check);
  - a folder that contains one (`mv data x`, `cp -r … data/`, `rmdir data`);
  - an argument with shell expansions (`$`, `*?[]{}`, `~`).
- `cd` into a protected path is denied, and any file operation in a command that also contains `cd` is denied.
- Indirect writes are denied:
  - `sort -o/--output/-T`, `uniq IN OUT`, `tree -o/-R`, `file -C`, `date -s`;
  - `git add -f`, `git add --pathspec-from-file`;
  - `git -C <protected>`; paths after `-C` are resolved against it;
  - ruff `--output-file/-o/--fix/--fix-only/--unsafe-fixes/--add-noqa/--watch/--cache-dir`, and inline `--config` settings;
  - ruff and `python3 -I -m compileall` targets in protected folders.

**`.claude/settings.json`**
- A second PreToolUse entry, `Write|Edit|MultiEdit|NotebookEdit`, runs the same hook.
- Deny rules:
  - `Edit(/data/raw/**)`, `Edit(/.claude/**)`, `Edit(/.git/**)`, `Edit(/.venv/**)`;
  - user-level `~/.claude/settings*.json`, `~/.gitconfig`, `~/.config/git/**`.

  Per the Claude Code docs, `Edit(...)` rules cover every built-in file-editing tool, and a leading `/` anchors at the primary working directory.
- Ask rules for `.gitignore`, `data/manifests/**`, `pyproject.toml` and `ruff.toml`.

**Procedure for later changes** (`docs/architecture.md` §7.1): Claude Code can no longer edit `.claude/`. It proposes patch files; the investigator applies them by hand and runs the hook tests. This brief was the one authorised exception (D01.17).

### 2.2 Limits (not a sandbox)

These are not covered:
- MCP tools;
- programs that open files themselves;
- subagent internals and hard links;
- writes when Claude Code is launched from a directory other than the project root (the `/path` anchors move);
- any situation where the hook cannot start (a hook that fails to launch does not exit 2, so the deny rules are the only backstop).

Optional hardening for the investigator to decide: `disableBypassPermissionsMode` and Claude Code's OS-level sandbox. Neither was changed, because both alter how the investigator works.

### 2.3 Live smoke checks of the Bash hook

Performed through Claude Code's own Bash tool:
- `git status` and `ls`: allowed;
- `sort -o <scratchpad file>`: blocked;
- `mkdir -p data/./raw/probe_dir`: blocked (normalised path);
- `ruff check … .claude/hooks`: blocked.

**Not performed:** a live Write/Edit block test. A failed block would leave a file in a protected folder. The new hook entry may need `/hooks` review or a restart before it is active.

## 3. Cellosaurus acquisition and parsing

**Facts verified** against api.cellosaurus.org on 2026-10-21 (Claude Code WebFetch):
- release-info JSON path `Cellosaurus.header.release.version` = `56.0` (updated 2026-06-25);
- TSV metadata lines start with `##` and include `response.numFound`;
- requesting `prob` gives a column headed `problematic`;
- `dr` entries are `|`-separated, `DepMap; ACH-…`;
- `hi`/`oi` entries are `|`-separated, `CVCL_X ! name`;
- `acas` lists primary plus secondary accessions;
- `sy` values are `; `-separated;
- an empty cell means nothing is recorded;
- `dr:ACH-000979` → CVCL_0105 (DU145); `dr:ACH-000019` → CVCL_0031 (MCF-7).

**`src/radiosensitivity_ml/data/cellosaurus.py`**
- It parses accession, name, synonyms, secondary accessions, DepMap cross-references, parents, same-individual links, category, species, problem text and entry version.
- Relationship states are kept distinct: `recorded`, `none_recorded` (column present, empty: Cellosaurus lists none, which does not prove none exists) and `field_unavailable` (column absent).
- **Truncation is rejected:** a missing `numFound`, a record count different from `numFound`, a wrong field count or a malformed accession all fail.
- `load_saved_responses` verifies `COMPLETE.json`, sidecar hashes and HTTP 200, the release, the requested-ID hash, every listed file's hash, and that no unlisted response files exist.

**`scripts/fetch_cellosaurus_phase_01.py`**
- Checks CLARIFi against its manifest hash and Model.csv against `SHA256SUMS`.
- Rounds:
  - `dr` in batches;
  - `drsingle`, which queries **every** ID on its own, because a batch could return only part of an ID's entries. Differences are listed as `batch_single_differences`, and the QC uses the union, so any extra entry makes the record ambiguous;
  - `rrid` for DepMap RRIDs not yet fetched;
  - `link1…N` for `hi`/`oi` accessions not yet fetched, primary or secondary, until no new accession appears (cap 10).
- Checks HTTP 200 and Content-Length, saves a sidecar per response, then writes `COMPLETE.json` last.
- Makes files read-only and is all-or-nothing (`<out>.partial` → `<out>`).
- Prints the `COMPLETE.json` SHA-256 for the manifest.

## 4. Identifier harmonisation and QC

### 4.1 Definitions (kept distinct in every output)

| Term | Meaning |
|---|---|
| Record | One CLARIFi row, keyed by its CLARIFi row number. It is **not** an experimental observation: the number of SF2 measurements behind each median is unknown (O01.12) |
| Relationship group (component) | Connected records, linked by: <br>- DepMap PatientID;<br>- any Cellosaurus candidate or the RRID (primary or secondary);<br>- `hi`/`oi`, including bridge entries outside CLARIFi.<br>The future validation unit. IDs `G:<smallest node>` are deterministic for fixed inputs but change when inputs change |
| Tissue | Taxonomy label of a component. Primary: OncotreeLineage. Sensitivity: the Esophagus/Stomach split by primary disease, and the CCLE suffix |
| Eligible record | No exclusion reason under `configs/phase_01_identifier_qc.yaml` |
| n | Components with ≥ 1 eligible record |
| T10 | Tissues with ≥ `min_components_per_tissue` (10) eligible components. Tissues below it are pooled as "other solid" (pooling fixed globally); MULTIPLE-label components are reported separately and never pooled |

### 4.2 Identity rule

**Deterministic and exact.** Names only ever add issues.

- **`verified`** requires all of:
  - in Model.csv with the same CCLE name;
  - exactly one Cellosaurus entry cross-referencing the DepMap ID;
  - DepMap RRID equal to that entry's primary or secondary accession;
  - no shared identity with another record.
- **`ambiguous`** covers:
  - a CCLE name mismatch;
  - a missing RRID;
  - several candidates;
  - a disagreeing RRID;
  - a shared accession, RRID or name, or a duplicate ID;
  - an entry found only through the RRID.
- **`unmatched`**: not in Model.csv, or no entry found by DepMap ID or RRID.

Non-blocking notes: secondary-accession RRID; entry listing several DepMap IDs. Records whose IDs agree and only the name differs are listed separately for human clearance (P01.13).

### 4.3 Eligibility reasons

Assigned in a fixed order; every excluded record carries at least one.

**Identity and data:**
- `identity_ambiguous`, `identity_unmatched`;
- `outcome_invalid_review`;
- `no_default_rna_profile`, `not_in_expression_matrix`.

**Lineage:**
- `lineage_missing_review`, `lineage_haematopoietic`, `lineage_excluded`, `lineage_unrecognised_review`.

**Model and entry checks:**
- `engineered_model_review`, `non_cancer_model_review`, `cellosaurus_category_review`, `non_human_review`;
- `problematic_cell_line`.

**Component level:**
- `component_spans_lineages`;
- `component_problematic`, with the source accessions listed;
- `component_links_not_expanded_review`.

### 4.4 Outputs

Written to a write-once folder. All are deterministic: sorted rows, sorted JSON keys and `\n` line endings, so the same inputs give the same bytes (except `run_record.json`).

| File | Content |
|---|---|
| `identity_records.csv` | Every record, every field |
| `matched_verified.csv`, `ambiguous_matches.csv`, `unmatched_records.csv` | Records by identity status |
| `duplicate_identifiers.csv` | Shared DepMap IDs, CCLE names, RRIDs or accessions |
| `relationships_parent.csv`, `relationships_same_individual.csv` | Parent and same-individual relationships (Cellosaurus `oi` and DepMap PatientID) |
| `components.csv` | Component membership |
| `eligibility.csv` | Eligibility decisions, exclusion reasons and tissue classification |
| `attrition_by_tissue.csv` | Reasons × lineage, counting first reason and any reason |
| `tissue_counts.csv` | Records and components per tissue × taxonomy × population (primary, retaining problematic, haematopoietic stratum) |
| `problematic_entries.csv` | Fetched entries with a problem text |
| `moringa_lines.csv` | MCF-7 and DU145 availability |
| `summary.json` | See below |
| `run_record.json` | Git commit, dirty flag and diff hash; code, config and input hashes; package versions |

`summary.json` contains the counts from initial CLARIFi through unique verified identities to matched profiles, issue and reason counts, and links not expanded. Its feasibility blocks give, for each population and taxonomy:
- n, T10, qualifying tissues;
- pooled and MULTIPLE components;
- strata, and strata smaller than K;
- held-out-tissue training sizes;
- component-size histograms, overall and by stratum;
- the provisional floors, labelled "descriptive, not power".

No output contains an mSF2 value.

## 5. Transformation requirements (P01.12; nothing transformed now)

Specification from the statistical-reviewer, for the mandatory sensitivity analyses. Let y be the parsed double, with exact comparisons and no tolerance band unless one is declared before the freeze.

**Domains:**

| Scale | Domain | Boundary values | Undefined |
|---|---|---|---|
| Raw | Finite, 0 ≤ y ≤ 1 | — | Anything else is already `outcome_invalid_review` |
| −ln(y) | 0 < y ≤ 1 | y = 1 gives 0 (defined) | y = 0 |
| logit(y) | 0 < y < 1 | — | y = 0 and y = 1 |

**Boundary rule.** Fix one option per transform **before the freeze, without looking at counts**:
- **(E) Exclude** records where the transform is undefined, from that analysis only. This is a deterministic per-record filter applied **before** folds are formed. Also report raw-scale MAE on the same restricted set, so that a change of population is not mistaken for an effect of scale.
- **(O) Declare an offset:** either a fixed ε from a stated source-precision argument, replacing undefined-point values only, or Smithson–Verkuilen shrinkage of all values. That citation must be verified. N must be **fixed and pre-declared**, because computing it in-fold would give training and test folds different transforms.

**How the rule is applied:**
- identically to both arms and to the training and test folds; nothing is estimated from outer-test data;
- assert that every transformed value is finite, and fail loudly otherwise;
- predictions on transformed scales are not clipped; the raw-scale clip rule is separate and the same for all arms;
- no winsorising after the fact.

**Nothing is clipped, replaced or transformed in phase_01.** Counts of exactly 0 or exactly 1 were deliberately removed from the QC (D01.18).

## 6. Tests (written; NOT executed)

| File | Covers |
|---|---|
| `tests/test_safety_hooks.py` | Bash allow and deny lists (redirections, indirect writes, ruff, git, traversal, `cd`, expansions, parent folders, `.git`/`.venv`). File tools on protected paths (relative, absolute, traversal, symlinked folders and files) and on planned QC output paths. NotebookEdit path key. Malformed inputs. Read-only tools ignored. A static check of `settings.json` matchers, deny and ask rules. Mock payloads only; no command is run; symlinks only under `tmp_path` |
| `tests/test_cellosaurus.py` | Release-info parsing; relationship states; unavailable vs absent fields; truncation; missing `numFound`; malformed rows; secondary accessions; conflicting duplicates; saved-folder verification (missing COMPLETE.json, stray file, modified file, HTTP status, release and ID-list mismatch) |
| `tests/test_qc_identifiers.py` | Alias matching; duplicates; ambiguous candidates; RRID-only entries; names never matching; parent–child; three-level `hi` chains through bridges, complete and cut off; one-sided `oi`; `hi` to a secondary accession; same-individual; PatientID; problem flags spreading from bridge entries; disagreeing RRIDs; haematopoietic plus solid on the same donor; missing expression; review rules; tissue grouping, T10, pooling, MULTIPLE labels; attrition; exclusion accounting; changing outcome values not changing grouping; idempotent, order-independent, write-once outputs; no outcome columns; audit mode; file readers |

Every fixture is labelled **SYNTHETIC software-test data**.

**Hand-traced by reviewers:** the software-architect found one failure, a header-order assertion, which is now fixed. The auditor's re-check traced the hook tests as passing once `settings.json` was written. These traces are not test runs.

**Commands for the investigator** (`docs/phase_01_investigator_qc_checklist.md` Stage 1):

```bash
conda activate explainable-radiosensitivity-ml
ruff format src tests scripts
ruff check src tests scripts .claude/hooks
python3 -I -m compileall -q src tests scripts .claude/hooks
bash -n scripts/acquire_phase_01.sh
PYTHONPATH=src python3 -m pytest tests/test_safety_hooks.py tests/test_cellosaurus.py tests/test_qc_identifiers.py -q
```

Then run Stages 2–4 of the checklist: acquisition, Cellosaurus fetch, and the identifier QC plus the 23Q4 audit.

## 7. Other changes

- `scripts/acquire_phase_01.sh`:
  - rejects HTML responses;
  - makes files and `SHA256SUMS` read-only;
  - moves the acquisition log to `results/logs/phase_01/acquisition_log.tsv`.
- `provenance.py`: `SHA256SUMS` lines in text or binary mode; normalised manifest paths; write-once folders.
- Environment naming standardised (D01.21).
- `docs/phase_01_reconciliation.md` §3.3 amended (edge rule, D01.20).
- Docs updated: `docs/architecture.md` §7, `scripts/README.md`, `configs/README.md`, `README.md`.

## 8. Specialist consultations

### 8.1 First review round (code review)

| Agent | Main findings | Action |
|---|---|---|
| software-architect | 1 failing test (header order). Hook gaps: parent-folder moves, argument expansion, `git -C`, combined `tree` flags, ruff `--config`. Also empty RNA profile set, audit default output, config validation, hashing duplication, binary `SHA256SUMS` lines, unused reader, mutable-row ordering | All fixed. The mutable `IdentityRow` is kept, with the step order documented and enforced |
| radiogenomics-curator | Identity rule correct and conservative. Gap A: RRID-only entries never fetched. Gap B: fixed link depth. Gap C: contaminants named only in problem text. Gap D: non-cancer lines. Gap E: batched query semantics. Category and species rules | A, B, D and E fixed (RRID round; iterate-to-closure; review rules; single-ID re-queries plus a manual spot check). C: `problematic_entries.csv` for human review |
| reproducibility-auditor | Status of earlier findings A1–E6. New: governance record; Cellosaurus files writable; run-record gaps; `.git`/`.venv` writable; `tree -R`; `--pathspec-from-file` | Fixed or recorded. A2, A5 and A6 remain (§9) |
| reproducibility-auditor (re-check) | No failing tests traced. HIGH: ruff config and targets. Medium: user-level settings and git config | Fixed (ruff targets checked; ask rules; user-level deny rules) |
| statistical-reviewer | Missing: size distributions, attrition, sensitivity populations, LOTO sizes, MULTIPLE handling. **Exact 0/1 flags were an outcome look**, and per-record flags disclosed them | All added. Exact 0/1 removed; per record only `outcome_invalid` |
| ml-methodologist | Record key must be the row number. Unexpanded links must be flagged. Secondary-accession `hi`. 11 extra tests | All done except a mocked fetch-frontier test (§9) |
| claude-code-guide | Hook payload and permission-rule syntax | Used for the hook and settings |

### 8.2 Final review round (all read-only subagents; nothing executed)

| Agent | Verdict | Remaining points | Action |
|---|---|---|---|
| software-architect | **CONDITIONAL PASS.** Traced every test as passing | M1: config typos could silently disable rules. M2: code hashes depend on the working directory. M3: untracked files missing from the run record. Minor: constant reuse, pooled-stratum label, `\n` line endings, float truncation | All fixed: unknown or missing keys and non-integers are rejected; code hashes resolve from the repository root and fail if a file is missing; untracked files are hashed |
| radiogenomics-curator | **CONDITIONAL PASS.** Gaps A–E handled | Batched query could return only part of an ID's entries and hide an ambiguity. `normal` marker too broad. Contaminant relations visible only in problem text | Every ID is now also queried singly and differences are recorded; markers narrowed to `non-cancerous`; problem texts go to human review |
| reproducibility-auditor | **CONDITIONAL PASS.** Settings and static test consistent; no HIGH issues | `COMPLETE.json` hash not checked against a version-controlled value. Checklist commit order. `.partial` deletion wording. Folders stay writable | The QC now requires `cellosaurus.complete_json_sha256` in the config; checklist reordered and wording added; writable folders documented |
| statistical-reviewer | **CONDITIONAL PASS.** Outputs suffice for G-ID and G-n inputs; §5 correct apart from two fixes | MULTIPLE not tested against K. Records per stratum. Strandedness, Yard and PatientID-only seeding missing | MULTIPLE and records per stratum added; §5 corrected; the rest stays open (§9) |
| ml-methodologist | **CONDITIONAL PASS.** Split-key foundation fine for tiers (a) and (b); tier (c) blocked; fails safe | Phase_03: freeze `components.csv` by hash; check secondary-accession `ac:` matching; mocked fetch-frontier test; publication origin is a limitation, not a split key | Recorded (§9) |
| research-director | **CONDITIONAL PASS.** Framework preserved | D01.20 changes a pre-fixed rule; span rule over-excludes; pending reviews not separated; superseded text in docs | D01.20 now needs ratification (P01.14). Span over record-eligible members by default (P01.13). Pending-review counts added. Superseded passages fixed (O01.13 fallback withdrawn; O01.15 makes CI methods candidates and G-C3 exploratory). Title question raised as P01.15 |

**Note:** the fixes in the "Action" column were made after the final round. They passed `ruff check` but were **not** re-reviewed by the agents. The verdicts above refer to the code as reviewed.

**Unresolved disagreements:** none between specialists. Open points needing investigator rulings: P01.11, P01.13, P01.14, P01.15, P01.16.

## 9. Remaining uncertainties and open items

1. **No test has been run.** Pass or fail is unknown until the investigator runs §6.
2. **Hook activation:** whether the new Write/Edit hook entry is active in a running session (it may need `/hooks` review or a restart).
3. **Unverified until the real files are read:**
   - 24Q4 `OncotreeLineage`, `OncotreePrimaryDisease` and `DepmapModelType` strings;
   - presence of `EngineeredModel`/`ModelType`/`OncotreeCode`;
   - `ProfileType` values;
   - expression first-column layout.
4. **Cellosaurus behaviour not verified live:**
   - batched `dr:(A OR B)` and `ac:(…)` semantics (mitigated by single-ID re-queries and a manual spot check);
   - whether `ac:` matches secondary accessions;
   - whether contaminants are recorded in `hi`/`oi`.
5. **Not done yet:**
   - Yard mapping and CLARIFi ∪ Yard components (P01.08); tier (c) stays blocked;
   - per-tissue RNA strandedness mix;
   - mocked test of the fetch frontier loop (needs a fetch stub);
   - DepMap models outside CLARIFi reachable only through a PatientID are not fetched;
   - whether `ac:` queries match secondary accessions (if not, related records are over-excluded through `component_links_not_expanded_review`, which is conservative but shrinks n);
   - lines related only through a shared contaminant in the problem text stay separate in the `retaining_problematic` sensitivity population;
   - publication or batch origin cannot be grouped, because CLARIFi values are literature medians; this is a limitation, not a split key;
   - phase_03 must freeze `components.csv` by SHA-256 and split only on that file. Component IDs change whenever inputs change.
6. **Auditor items still open:**
   - A2: Yard files get a signature check only;
   - A5: the GEO matrix folder is named by date;
   - A6: manifest `sha256` fields are empty until Stage 2;
   - folders stay writable (files are read-only);
   - no lockfile (P00.02).
7. **Licences:** CLARIFi licence unresolved. QC tables contain CLARIFi names and are gitignored; do not commit them.
8. **Process:**
   - outcome-validity exclusion needs ratification (P01.11);
   - rulings P01.13;
   - D01.19 deviation (two mSF2 values seen);
   - phase gates unsigned.
9. `ruff format` wants cosmetic changes in 9 files; the hook does not allow Claude Code to write them.

## 10. Files changed

**Created:**
- `src/radiosensitivity_ml/data/cellosaurus.py`, `components.py`, `eligibility.py`, `qc_report.py`;
- `configs/phase_01_identifier_qc.yaml`;
- `tests/test_cellosaurus.py`;
- this report.

**Rewritten:**
- `.claude/hooks/block_model_execution.py`;
- `.claude/settings.json`;
- `src/radiosensitivity_ml/data/qc_identifiers.py`, `provenance.py`, `__init__.py`;
- `scripts/fetch_cellosaurus_phase_01.py`, `scripts/qc_phase_01_identifiers.py`;
- `tests/test_safety_hooks.py`, `tests/test_qc_identifiers.py`;
- `docs/phase_01_investigator_qc_checklist.md`.

**Edited:**
- `scripts/acquire_phase_01.sh`;
- `docs/decision_log.md`, `docs/architecture.md`, `docs/phase_01_reconciliation.md`, `docs/phase_01_recommendations.md`, `docs/phase_01_dataset_feasibility.md`;
- `README.md`, `scripts/README.md`, `configs/README.md`.

**Not modified:** any raw data file. **No commits or pushes.**
