# Repository architecture

Status: phase_00. All Python modules are docstring placeholders. Nothing is implemented, run or validated.

## 1. Design principles

- **One place for each thing.**
  - configuration: `configs/`;
  - figure outputs: `figures/generated/`;
  - analytical outputs: `results/`;
  - provenance: `data/manifests/`;
  - source manuscripts: `references/source_manuscripts/`;
  - code: one Python package, `src/radiosensitivity_ml/`.
- **Stages are separate.** Acquisition, parsing and harmonisation, splitting, feature construction, modelling, evaluation, explanation and plotting live in separate modules. No module reaches backwards in the chain.
- **Raw data are read-only.** Every transformation writes a new file to `data/interim/` or `data/processed/` and is recorded.
- **Everything is driven by config.** Paths, seeds and choices come from YAML in `configs/`, resolved relative to the repository root. Code contains no personal or absolute paths and no outcome values.
- **Small, pure, typed functions.** Explicit inputs and outputs, no hidden state, and no class hierarchies unless they earn their place.
- **Simple baselines first.** scikit-learn only until the protocol justifies more. No deep-learning frameworks.
- **Claude Code writes code; humans run it.** See `CLAUDE.md`.

## 2. Naming conventions

| Element | Convention |
|---|---|
| Project title | Explainable Radiosensitivity ML |
| Proposed repository | `explainable-radiosensitivity-ml` (remote not renamed; `docs/decision_log.md` P00.07) |
| Distribution / conda environment | `explainable-radiosensitivity-ml` |
| Python package | `radiosensitivity_ml` |
| Modules, functions, variables | `snake_case` |
| Classes | `PascalCase` |
| Folders | lowercase `snake_case` (established names such as `.claude`, `src` excepted) |
| Config files | lowercase, descriptive, `.yaml` |
| Documentation | lowercase `snake_case.md`; except `README.md`, `CLAUDE.md` |
| Phases | `phase_00` … `phase_05` |
| Figures / tables | `fig_01`, `fig_s01` / `table_01`, `table_s01` |
| Decision-log IDs | `D00.01`, `P00.01`, `O00.01` |
| Manifests | `<source_slug>__<release>.yaml`, e.g. `clarifi__v1_0.yaml` |

## 3. Directory layout

```
.claude/                  Claude Code agents, skills, rules, hooks, settings
configs/                  YAML configuration (written from phase_02/03)
data/
  raw/                    immutable source files (gitignored)
  interim/                intermediate tables (gitignored)
  processed/              analysis-ready tables (gitignored)
  manifests/              tracked provenance records
docs/                     protocol, decisions, standards, design documents
references/
  source_manuscripts/     source PDFs (gitignored) + tracked checksum manifest
src/radiosensitivity_ml/
  config.py               config loading, path resolution, seed recording
  data/                   loaders; provenance.py; identifiers.py; qc_identifiers.py (phase_01)
  features/               fold-safe feature transformers
  models/                 prespecified models (blocked until protocol approval)
  evaluation/             splits.py (group splits, leakage checks); metrics
  explainability/         attribution methods (blocked until protocol approval)
  visualization/          figure style and pure plotting functions
scripts/                  thin CLI entry points, run by the investigator
tests/                    unit tests; fixtures/ holds labelled synthetic data only
figures/
  specs/                  tracked per-figure specifications
  generated/              rendered figures + provenance sidecars (gitignored)
results/                  analytical outputs: tables/, models/, logs/ (gitignored)
manuscript/               manuscript sources (phase_05)
```

## 4. Module responsibilities

| Module | Responsibility | Must not |
|---|---|---|
| `config` | Load YAML, resolve paths from the repository root, expose seeds, hash config | Hold defaults that silently change results |
| `data.provenance` | Manifest schema; checksum verification of raw files | Load a file without a manifest entry |
| `data.identifiers` | Map source IDs to Cellosaurus accessions; flag ambiguous, misidentified and same-donor lines; overlap reports | Rewrite original ID strings |
| `data.qc_identifiers` (phase_01) | Descriptive identifier QC: match CLARIFi to DepMap and Cellosaurus; count availability | Keep outcome values or expression values; compute statistics |
| `data` (loaders, phase_03) | Parse each source into a long table with an `endpoint_class` | Merge endpoint classes |
| `evaluation.splits` | Group splits by cell line (plus donor, lineage, study or dataset as the protocol says); duplicate and overlap checks | Let a cell line cross partitions |
| `features` | scikit-learn transformers fitted inside training folds only | Fit on the full dataset |
| `models` | Prespecified estimators wrapped in `Pipeline`s | Exist before `docs/protocol.md` is approved |
| `evaluation` (metrics) | Prespecified metrics with uncertainty | Touch the held-out test set during tuning |
| `explainability` | Attribution methods named in the protocol | Present attributions as mechanisms |
| `visualization` | Style constants, export helper, plotting functions on tidy tables | Accept synthetic fixtures as manuscript inputs |

## 5. Data flow (planned)

```
public sources (verified URL / DOI / licence)
   │  investigator-approved acquisition; manifest + checksums in data/manifests/
   ▼
data/raw/                      read-only
   │  parse + identifier harmonisation
   ▼
data/interim/                  one long table per endpoint class
   │  documented inclusion/exclusion; overlap report
   ▼
data/processed/                analysis-ready tables + run record
   │  splits → in-fold features → models → evaluation → explainability
   │  ── EXECUTED BY THE INVESTIGATOR ONLY (phase_04) ──
   ▼
results/{tables,models,logs}/  each output has a run record
   │  visualization + figures/specs/
   ▼
figures/generated/             PDF/SVG/PNG + .meta.json sidecar
   ▼
manuscript/                    curated copies only
```

## 6. Configuration and environment

- `pyproject.toml` is the package definition and the intended single dependency source.
  - It currently declares no runtime dependencies, because the package contains placeholders only.
  - It has a `dev` extra (pytest, ruff) and the ruff and pytest settings.
- `environment.yml` (conda environment `explainable-radiosensitivity-ml`) is unpinned. Prototype-only packages are marked LEGACY.
- There is no lockfile. One will be generated by the investigator after the environment review (`docs/decision_log.md` P00.02).
- The prototype `Makefile` and the empty `requirements.txt` were retired in phase_00 (D00.21). There is no task runner; commands are documented per script.
- Dependency decisions for packages left over from the prototype are deferred to phase_01–phase_03 (`docs/decision_log.md`, "Dependency decisions").

## 7. Safety hooks

`.claude/hooks/block_model_execution.py` runs before every Bash, Write, Edit, MultiEdit and NotebookEdit call, invoked via `"$CLAUDE_PROJECT_DIR"`.

**Protected locations:**
- `data/raw/` (immutable raw data);
- `.claude/` (hooks, settings, agents, skills, rules);
- `.git/` and `.venv/` (git configuration and environment executables).

**File tools:** the target path is resolved lexically and through symlinks. A path inside a protected location is denied, and malformed input is denied.

**Bash:**
- compound commands are split into segments, and every segment's command must be on an allowlist of read-only and static-check tools;
- always denied: substitutions, here-documents, redirections other than to `/dev/null`, environment-variable prefixes and unknown commands;
- denied when they could write files: `sort -o`, `uniq IN OUT`, `tree -o/-R`, `file -C`, and ruff output, fix, cache and inline-config options;
- file operations and `git add`/`git mv` may not name a protected path, a folder containing one, or an argument with shell expansions; `cd` into a protected path is denied, and file operations after any `cd` are denied.

**Fails closed:** unparseable input is denied.

**Permission rules (`.claude/settings.json`):**
- deny any Bash command containing `python`;
- deny `Edit(...)` on the protected locations (Edit rules cover every file-editing tool);
- ask before editing `.gitignore` or `data/manifests/`.

**Limits.** This is **not a sandbox**. It does not cover:
- MCP tools;
- programs that open files themselves;
- subagent internals, shell aliases and hard links.

Behaviour and tests: `docs/phase_01_remediation_report.md` §2 and `tests/test_safety_hooks.py`.

### 7.1 Changing the hooks or settings (narrowly scoped procedure)

Once the Write/Edit protection is active, Claude Code cannot change anything in `.claude/`. That is intended. Changes follow this procedure:

1. Claude Code writes the proposed change as a patch file outside `.claude/` (for example `docs/proposed_patches/<date>_<topic>.patch`), with matching mock tests in `tests/`.
2. The investigator reviews the patch and the reviewer notes, and applies it by hand in their own editor or shell.
3. The investigator runs `PYTHONPATH=src python3 -m pytest tests/test_safety_hooks.py -q` and records the result in `docs/decision_log.md`.
4. New hook entries may need `/hooks` review or a Claude Code restart before they take effect.

Protections are never disabled globally to make a change.

The only exception so far is the phase_01 remediation (D01.17): the investigator's brief of 2026-10-21 authorised Claude Code to edit the hook and settings directly, before the protection was switched on.

## 8. Main architecture risks

1. **Leakage.** Mitigation:
   - all splitting goes through `evaluation.splits`;
   - all preprocessing is a `Pipeline` step fitted inside folds;
   - cross-dataset and cross-study overlap is checked on harmonised identifiers before any split.
2. **Endpoint conflation.** Mitigation: every table carries a required `endpoint_class`; classes are never merged silently.
3. **Provenance drift.** Mitigation: a manifest for every raw file, a run record for every output, a sidecar for every figure, and one environment specification.
