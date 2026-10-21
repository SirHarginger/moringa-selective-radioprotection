# Phase 01 static review: acquisition, QC and safety code

**Status:** review for the investigator, 2026-10-21. **Static reading only.** Nothing was executed: no downloads, no `pytest`, no `bash -n`, no `compileall`, no `ruff`. No code was changed in this pass. Every patch below is a **proposal** awaiting investigator approval (decision log P01.07–P01.10).

**Reviewers:**
- Claude Code: first read, applying the `research-code-review` and `leakage-audit` skills.
- reproducibility-auditor (subagent): confirmed or refuted each item with file:line.
- radiogenomics-curator (subagent): identity and grouping logic.
- ml-methodologist (subagent): split-key perspective.

**Files reviewed:**
- `scripts/acquire_phase_01.sh`
- `scripts/fetch_cellosaurus_phase_01.py`
- `scripts/qc_phase_01_identifiers.py`
- `src/radiosensitivity_ml/data/qc_identifiers.py`
- `tests/test_qc_identifiers.py`
- `tests/test_safety_hooks.py`
- `.claude/hooks/block_model_execution.py`
- `.claude/settings.json`
- `.gitignore`
- `data/manifests/*.yaml`

---

## 1. Verdict

| Area | Verdict |
|---|---|
| Accidental ML execution | **None found.** No script fits, predicts, tunes, cross-validates or computes SHAP |
| Outcome blinding in the QC | **Pass.** No mSF2 value is retained or written (`qc_identifiers.py:135-141`, `:351-361`); tests assert this |
| Download integrity (DepMap) | **Pass.** MD5, size and the `.part` → rename sequence are checked before a file becomes raw |
| Download integrity (other sources) | **Partial.** See A1, A2 and A6 |
| **Grouping and split keys** | **FAIL, blocking.** Cellosaurus parent and same-individual links are parsed but never output (D1). The gate quantities *n* and T₁₀ are not produced (D2). **The QC must not be used for gating until this is patched** |
| Safety hook | **Partial.** The Bash allowlist works as designed, but there are write paths around it (E1–E5) |
| Test status | **UNKNOWN.** Tests have not been run by Claude Code (the hook blocks `pytest`) |

## 2. Findings

Severity: **H** = high, **M** = medium, **L** = low. All patch text is a proposal.

### 2.1 Acquisition (`scripts/acquire_phase_01.sh`)

| # | Finding (file:line) | Sev | Proposed patch |
|---|---|---|---|
| A1 | GEO `filelist.txt` is fetched with no MD5, signature or size check (`:119`), so an HTML error page with HTTP 200 would become a raw file | M | Reject the `.part` file if it contains `<html` (case-insensitive) |
| A2 | Yard xlsx and pdf get a signature check only (`:109-110`). `504b0304` matches any zip file | L | Record the byte size and sheet names in the manifest after download (§6 checklist) |
| A3 | `ACQUISITION_LOG.tsv` is appended inside `data/raw/…` (`:75-76`). It is a mutable file in the immutable area, and it is gitignored | L | Write the log to `results/logs/phase_01/` instead, or copy its rows into the manifests |
| A4 | Files are not made read-only after `mv` (`:74`) | L | `chmod a-w "$dest"`, and the same for `SHA256SUMS` |
| A5 | The GEO matrix folder is named by run date (`:122`), so a re-run on another day downloads it again | L | Skip if any `matrix_*` folder exists, or take an explicit date argument |
| A6 | `SHA256SUMS` sits in gitignored `data/raw`, and every new manifest still has `sha256: null` | M | Copy the hashes into the manifests (checklist step 6) before any `provenance_status` change |

### 2.2 Cellosaurus fetch (`scripts/fetch_cellosaurus_phase_01.py`)

| # | Finding | Sev | Proposed patch |
|---|---|---|---|
| B1 | Reads CLARIFi IDs without first checking the CLARIFi SHA-256 (`:97`). The QC script checks it later | L | Compare against the manifest hash before opening the file |
| B2 | The release check is a regex over the whole JSON text (`:107-110`). An unrelated `"56.0"` would pass | L | After the first run, parse the JSON and pin the key name |
| B3 | `count_data_rows` skips lines starting with `#` (`:82`); the parser skips only `##` (`qc_identifiers.py:203`) | L | One shared predicate |
| B4 | A failure mid-run leaves a partial folder, and the QC globs whatever `*.tsv` files exist (`qc_phase_01_identifiers.py:129`). A truncated fetch would show up only as extra `no_match` lines | **M** | Write `COMPLETE.json` (batch count, ID count) at the end; the QC requires it and checks the counts |
| B5 | The sidecar `http_status` and `content_type` are recorded but never checked | L | Assert 200 and a TSV content type |
| B6 | The API field `prob` ("known problems") is not requested. The problematic flag relies on the text "Problematic cell line" appearing in the row (curator) | L | Request `prob` if the API accepts it (unverified); otherwise keep the text search but limit it to the `cc` column (D4) |

### 2.3 QC runner (`scripts/qc_phase_01_identifiers.py`)

| # | Finding | Sev | Proposed patch |
|---|---|---|---|
| C1 | `release_info.json` is optional, its sidecar is not checked, and the release is not re-checked (`:139-141`) | M | Require it, verify the sidecar SHA and re-check the expected release |
| C2 | A missing sidecar raises an uncaught `FileNotFoundError` (`:134`). It still fails closed | L | Route it through `fail()` |
| C3 | The 23Q4 audit run mixes the 23Q4 `Model.csv` with 24Q4 profile and expression files. The outputs do not say so | M | Write `"mixed_release": true` and drop the RNA and expression counts in that mode |
| C4 | The never-overwrite guard checks only `run_record.json` (`:110`); the table and summary are opened with `"w"` | L | Refuse to run if `--out` is not empty |
| C5 | `lockfile_sha256: None`. No lockfile exists yet | M | After the environment review (P00.02) |

### 2.4 QC library (`src/radiosensitivity_ml/data/qc_identifiers.py`)

| # | Finding | Sev | Proposed patch |
|---|---|---|---|
| **D1** | `CellosaurusRecord.linked_accessions` (`hi` parent and `oi` same-individual) is parsed (`:216-227`) but is not in `MatchRow` (`:84-103`), the summary or the CSV. Same-donor and parent links are lost, so grouping would fall back to DepMap `PatientID` only. `docs/phase_01_dataset_feasibility.md` §5.3 wrongly describes these links as captured | **H** | Add `cellosaurus_linked_accessions` and `cellosaurus_name` to `MatchRow` and write them out |
| **D1b** | Only `ac` is a required column (`:207`). If the API drops or renames `hi`/`oi` (their acceptance is unverified), every line silently becomes a singleton | **H** | Require `hi` and `oi` unless an explicit `--no-hierarchy` flag is passed, and record `hi_oi_columns_present` in the summary |
| **D2** | The summary counts *lines* across *all* lineages (`:331-336`). There is no solid-tumour filter and no component collapse, so the decision quantities *n* and T₁₀ are not produced and cannot be derived from `clarifi_identifier_match.csv` alone | **H** | Add a pure `build_components()` (union–find over PatientID, accepted ACH→CVCL, and `hi`/`oi` including bridge accessions outside CLARIFi). Report *n* and T₁₀ under the pre-fixed solid rule and taxonomy |
| D2b | `EngineeredModel`, `ModelType`, `OncotreeCode` and `GrowthPattern` are not in `MODEL_COLUMNS` (their existence in 24Q4 is reported by the curator but **UNVERIFIED**), so the non-cancer and engineered exclusion rule cannot be applied | M | Add them as *optional* columns; record them as absent if missing |
| D2c | No check for alias duplicates (two ACH IDs → one CVCL; duplicate RRIDs) | M | Fail loudly, or flag them for human resolution |
| D3 | D01.05 says "blank and non-numeric counts", but the code counts only blanks (`:135`, `:312`) | L | Add `outcome_non_numeric` (parse as float, discard the value) |
| D4 | The `problematic` flag is a substring search over the whole row, synonyms included (`:214`) | L | Search the `cc` column only, and record the category if available |

### 2.5 Safety hook and settings (`.claude/hooks/block_model_execution.py`, `.claude/settings.json`)

These items concern Claude Code's guard rails. They do not affect the investigator's own commands. **Claude Code has not changed the hook or the settings**: both are investigator decisions (agent_workflow §4).

| # | Finding | Sev | Proposed patch |
|---|---|---|---|
| **E1** | The hook covers the Bash tool only (`settings.json:25`). Claude Code's Write and Edit tools are not stopped from writing into `data/raw/` or `.claude/`. `tests/test_safety_hooks.py:152` asserts this as intended behaviour | **H** | Add permission deny rules for `Write`/`Edit` on `data/raw/**` and `.claude/**` (exact rule syntax to be checked against the installed Claude Code version) |
| **E3** | `ruff check --fix-only` and `ruff check --output-file <path>` are allowed; `RUFF_FORBIDDEN` (`:98`) lacks both. The second could overwrite any file, including settings | **H** | Add `--fix-only`, `--output-file` and `-o` to `RUFF_FORBIDDEN` |
| E2 | `sort -o FILE`, `uniq IN OUT` and `tree -o FILE` write files and are not blocked | M | Deny `-o`/`--output*` for sort and tree, and more than one positional argument for uniq |
| E4 | `git mv` and `git add` are allowed without the protected-path check. `git add -f data/raw/…` could stage gitignored raw data, a redistribution risk while the CLARIFi licence is unresolved | M | Apply the path check to git `mv`/`add`; deny `-f`/`--force` on `add` |
| E5 | The path check is a substring match: `cd data/raw && mv a b`, `data//raw` and `data/./raw` get past it | M | Normalise paths, and deny file operations after `cd` into a protected path |
| E6 | The deny rule `Bash(*python* *)` does not match a bare `python` (the hook still blocks it), and it also blocks harmless `grep python`. How mid-pattern `*` behaves in this Claude Code version is **UNKNOWN** | L | Keep the hook as the backstop; optionally add `Bash(python*)` |

### 2.6 Test coverage (`tests/`)

**Not covered:**
- B1–B5, `count_data_rows`, the release regex, `listed_sha256`;
- the QC `main()` paths: dirty tree, sidecar mismatch, missing release info, partial Cellosaurus fetch;
- non-numeric outcome cells;
- `linked_accessions` propagation, components, *n* and T₁₀;
- hook cases for `sort -o`, `uniq IN OUT`, `tree -o`, `ruff --fix-only` / `--output-file`, `git add -f`, `git mv .claude/…`, `cd data/raw && mv`, and `data//raw`.

All new tests must use labelled synthetic fixtures only.

## 3. Unsafe commands or ambiguities needing investigator review

1. **Do not run the identifier QC for gating** until D1, D1b and D2 are patched and reviewed (P01.07). Running it now would give a component count based on PatientID only, which undercounts linked lines and overstates *n*.
2. The `--allow-dirty` flag is needed because phase_00 changes are uncommitted. The flag is recorded, but a QC run on an uncommitted tree cannot be tied to a commit. **Commit first (P00.01), then run without `--allow-dirty`.**
3. The 23Q4 audit run (recommendations §5): read only its Model-table counts. Its RNA and expression columns refer to 24Q4 (C3).
4. `fetch_cellosaurus_phase_01.py` falls back to a field list without `hi`/`oi` if the API rejects them. **The fallback gives no hierarchy links and must not be used for grouping** without a recorded decision.
5. The `--optional` acquisition (GEO, ICLAC) is not needed for the primary analysis. ICLAC is CC BY-NC-ND (use only as an unmodified lookup).
6. Hook gaps E1 and E3 (high) let Claude Code write to protected locations through routes other than the Bash allowlist. Decide whether to close them before phase_03 (P01.09).
7. **Not scripted:** the Yard name → ModelID → CVCL mapping. It needs an exact-match script with a manual-review log before any cross-assay overlap count (P01.08).

## 4. Checks performed and not performed

**Performed:**
- full read of the files listed above;
- grep of the hook's allowlist, git rules and protected paths;
- cross-check of the CLARIFi hash constant against the manifest (they match; auditor).

**Not performed:**
- `pytest` and `bash -n`/shellcheck;
- `compileall`, `ruff` and `mypy`;
- any download or check of live API behaviour (`hi`/`oi` acceptance, TSV header prefix, release-info JSON key);
- the layout of the expression file's first column;
- whether `EngineeredModel`/`ModelType`/`OncotreeCode` exist in 24Q4 `Model.csv`;
- how the settings deny glob actually behaves.
