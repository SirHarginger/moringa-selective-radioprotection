# phase_00 verification and closure report

Date: 2026-10-20. Prepared by Claude Code for investigator review. This report covers both phase_00 passes: standardisation, and closure.

Throughout phase_00, nothing:
- trained, ran or evaluated a model;
- analysed data values;
- downloaded a dataset;
- installed a package;
- created a commit or push, or changed the remote.

**Recommendation: CONDITIONAL PASS for opening phase_01** (§12).

## 1. Final directory tree

Excludes `.git/`, `.venv/`, `.claude/vendor-review/` (community material held for vetting) and the ignored `graphify-out/`.

```
explainable-radiosensitivity-ml/   (local folder and remote still named moringa-selective-radioprotection)
├── .claude/
│   ├── agents/      9 agents (unchanged)       ├── rules/   plotting.md, reproducible-python.md, scientific-integrity.md
│   ├── skills/      7 skills (unchanged)       ├── hooks/   block_model_execution.py, session_note.py
│   └── settings.json
├── configs/README.md
├── data/
│   ├── raw/CLARIFi.csv (unchanged, gitignored), .gitkeep
│   ├── interim/.gitkeep    processed/.gitkeep
│   └── manifests/  README.md, _template.yaml, clarifi__v1_0.yaml
├── docs/  agent_workflow.md, architecture.md, claude_research_setup.md, data_management.md,
│          decision_log.md, figure_standards.md, moringa_scientific_linkage.md,
│          phase_00_verification.md, prototype_history.md, research_roadmap.md
├── references/source_manuscripts/  README.md, manifest.yaml, moringa_original.pdf (gitignored)
├── src/radiosensitivity_ml/  __init__.py, config.py, data/ (provenance, identifiers),
│                             evaluation/ (splits), features/, models/, explainability/, visualization/
├── scripts/README.md
├── tests/  README.md, test_safety_hooks.py, fixtures/README.md
├── figures/  README.md, specs/_template.yaml, generated/.gitkeep
├── results/  README.md, tables/ models/ logs/ (.gitkeep)
├── manuscript/README.md
└── README.md  CLAUDE.md  pyproject.toml  environment.yml  .gitignore
```

All Python modules are docstring placeholders.

## 2. Files changed

**Standardisation pass:**
- Rewrote the safety hook; fixed the hook paths in settings.
- Renamed the project, distribution and environment.
- Renamed phases and figure IDs throughout.
- Rewrote the docs.
- Added the CLARIFi manifest and hook tests.
- Moved `README_RESEARCH_SETUP.md` to `docs/claude_research_setup.md`.
- Removed the empty `config/` and `docs/latex/`.
- Created the archive tag.

**Closure pass:**

| Action | Path |
|---|---|
| Copied (unchanged, MD5-identical) | `~/Downloads/Scanned manuscript RAMSRI.pdf` → `references/source_manuscripts/moringa_original.pdf` |
| Created | `references/source_manuscripts/manifest.yaml` |
| Rewritten | `docs/moringa_scientific_linkage.md`, `docs/decision_log.md`, `docs/phase_00_verification.md` |
| Modified | `data/manifests/clarifi__v1_0.yaml` (separate licences; row count corrected), `docs/data_management.md`, `README.md`, `CLAUDE.md` (phase_05 added to the phase order), `.gitignore`, `results/README.md`, `docs/architecture.md`, `docs/figure_standards.md`, `docs/prototype_history.md`, `references/source_manuscripts/README.md` |
| Retired (uncommitted deletions; originals in the archive tag) | `Makefile`, `requirements.txt`, `results/figures/.gitkeep`, `results/screening/.gitkeep` |

Retired files were moved to the session scratchpad, because the hook blocks `rm`. No scientific value, DOI, identifier or hash was changed by search-and-replace.

## 3. Naming conventions

- Project: "Explainable Radiosensitivity ML".
- Distribution and environment: `explainable-radiosensitivity-ml`.
- Package: `radiosensitivity_ml`.
- Phases `phase_00`–`phase_05`; figures `fig_01` / `fig_s01`; tables `table_01` / `table_s01`; decision IDs `D00.01`.
- Docs: lowercase `snake_case.md`.

The full table is in `docs/architecture.md` §2. The remote and the local folder are **not** renamed (P00.07).

## 4. Legacy items

| Item | Status |
|---|---|
| Prototype source, scripts, tests, config, LaTeX report | Deleted from the working tree (uncommitted); preserved in the tag; commit pending (P00.01) |
| `Makefile`, `requirements.txt` | **Retired** (D00.21). No active dependency; only documentation referred to them |
| `results/figures/`, `results/screening/` | **Retired** (D00.22) |
| `graphify-out/` | Ignored; still in the git index. Untrack with `git rm -r --cached graphify-out` (P00.06) |
| Prototype packages in `environment.yml` | Kept, marked LEGACY; decisions deferred per package (decision log, "Dependency decisions") |
| `.claude/vendor-review/` | Kept for human vetting |

## 5. Git archive

| Check | Result |
|---|---|
| Commit `76f9e6f` exists | Yes (`git cat-file -t` → `commit`), full hash `76f9e6f30042c55b22ef44e8ef1973ea0dadbc50`, contains `src/moringa_radioprotection/` (14 files) and the prototype scripts, tests, config and report |
| Tag | `archive/pre-radiosensitivity-ml`, annotated (`git cat-file -t` → `tag`) |
| Tag target (rechecked at closure) | `git rev-parse 'archive/pre-radiosensitivity-ml^{commit}'` → `76f9e6f30042c55b22ef44e8ef1973ea0dadbc50` |
| Pushed / commits made / history rewritten | No / No / No |

Recovery steps: `docs/prototype_history.md`.

## 6. Manuscript verification

| Check | Result |
|---|---|
| Expected path existed when closure began | **No.** The file was found at `~/Downloads/Scanned manuscript RAMSRI.pdf` (modified 2026-10-20). Page 1 was inspected, the title matched, and the file was copied unchanged |
| Opens correctly | Yes. PDF 1.3, 8 pages, all rendered as page images |
| SHA-256 / MD5 / size | `7f644f55a2e1eca3cfd95ba48a74096cedf676bd3fac9910b5e6b8db8e870fb9` / `1ae1f270e77fa1e14095be400adb6eea` (identical to the source file) / 8,192,004 bytes |
| Gitignored | Yes (`.gitignore` rule `references/source_manuscripts/*`) |
| Pages present | Printed **1, 2, 4, 5, 6, 13, 14, 15**. **Printed 3 and 7–12 missing** (confirmed by the radiobiologist) |
| Extraction | All eight pages read by Claude Code. Every item checked against the page images by the radiobiologist. Recorded with PDF and printed page references in `docs/moringa_scientific_linkage.md` |

**Key verified facts:**

| Topic | Fact | Page (PDF/printed) |
|---|---|---|
| Title | "Dichloromethane seed and leaf extracts of *Moringa oleifera* (Lam) enhance proliferation in irradiated rodent fibroblasts *in vitro*" | 1/1 |
| Objective | Proliferation ("a requirement for wound healing and tissue remodeling"), in a preoperative-radiotherapy wound-healing context | 1/1, 2/2 |
| Cell lines | V79 "apparently normal Chinese hamster lung fibroblasts"; DU145 "human prostate cancer cells"; MCF-7 "human mammary adenocarcinoma cells". Tables call V79 "murine" (inconsistent) | 2/2; 6/13 |
| Extracts | Crude DCM seed and leaf extracts, reconstituted in PBS, filtered at 0.22 µm. Preparation otherwise not in the supplied pages | 2/2, 3/4 |
| Treatment | 0–100 µg/ml; extract, then immediately 0 or 2 Gy X-rays; Precision MultiRad 160; 1 Gy/min; 2 ml per well | 3/4 |
| Assay | 5 000 cells/well, 24-well plates, 3 h attachment, 72 h incubation; 70% ethanol fixation, 0.5% crystal violet, 10% SDS, OD 590 nm; 3 wells per sample; one plate per dose | 3/4 |
| Control subtraction | Mean (±SE) OD of each dose-matched untreated triplicate control subtracted from each extract-treated sample | 3/4 |
| PEF | *A*D = area under the change-in-OD vs concentration plot; **PEF = *A*2Gy/*A*0Gy** | 3/4 |
| Statistics | GraphPad Prism; unpaired two-sided Student's t-test; P < 0.05; error propagation | 3/4–4/5 |
| Seed PEF | V79 1.25 ± 0.04 (P = 0.0016); DU145 1.12 ± 0.03 (P = 0.0072); MCF-7 1.16 ± 0.01 (P < 0.0001) | 6/13 |
| Leaf PEF | V79 1.26 ± 0.04 (P = 0.0021); DU145 0.90 ± 0.01 (P = 0.0003); MCF-7 0.99 ± 0.05 (P = 0.8072) | 6/13 |

**Issues recorded rather than resolved:**
- **Unit inconsistency:** "mg/ml" vs µg/ml, and 25–50, 30–50 or >20 µg/ml in different places.
- **Species wording:** hamster, murine and rodent are all used for V79.
- ***A*D does not match the figures:** the tabulated *A*D values are positive, but the plotted changes in OD are mostly negative. The computation, its units and its SE are not described.
- **"Enhancement" means two things:** PEF > 1 for all seed-treated lines, yet the tumour lines are below untreated control.
- **Replication:** technical wells only, with dose confounded with plate.
- **Figures:** the 0 Gy and 2 Gy series cannot be told apart in the scan.

PEF is documented as **not SF2** (linkage §12). The manuscript establishes no molecular mechanism, clinical radioprotection, wound-healing efficacy or selective tumour protection (linkage §10).

## 7. CLARIFi

| Check | Result |
|---|---|
| File unchanged | MD5 rechecked at closure: `6f52f03db6d33ad9a0cac9f3dbbcbb2d`, matches Zenodo. SHA-256 `fb0ec352…68503` |
| Row count | **Corrected:** 286 lines = header + **285** data rows. The last line has no trailing newline, so the earlier `wc -l` figure of 284 rows was wrong. Matches the article's 285 cell lines |
| Dataset licence (Zenodo, accessed 2026-10-20) | CC BY 4.0. Owner user 1690077 (unnamed); creators match the article authors |
| Article licence (Crossref, Europe PMC XML, PMC, accessed 2026-10-20) | CC BY-NC 4.0. No Data Availability Statement. Database said to be at researchmap.jp (HTTP 403). Zenodo not mentioned |
| Assessment | **Unresolved.** The article licence is not assumed to supersede the dataset's. `redistribution_allowed: unresolved`; stricter terms (attribution, non-commercial) applied; raw file stays gitignored; authors to be contacted (O00.02) |

## 8. Safety hooks

The hook changes and live checks from the standardisation pass are unchanged: 7 block probes and several allow probes all behaved as expected. Details are in the decision log (D00.16) and `docs/architecture.md` §7.

`tests/test_safety_hooks.py` was **reviewed at closure** by Claude Code and the reproducibility-auditor:
- It loads the hook with `importlib`; the hook's `main()` only runs under `__main__`.
- It feeds mocked strings to `classify`, `evaluate_payload` and `tokenize`.
- **It executes no commands and uses no subprocesses.**

It has **not been run**: the project permission rule `Bash(*python* *)` stops Claude Code from running Python.

**Remaining checks for the investigator** (run from the repository root):

```
python3 -m pytest tests/test_safety_hooks.py -q          # hook tests (mocked inputs only)
python3 -I -m compileall -q src tests .claude/hooks       # syntax compile check
git rm -r --cached graphify-out                           # P00.06, if approved
git status --short                                        # review before any commit (P00.01)
```

Checked by directory listing:
- pytest is **not** installed in `.venv/`.
- It **is** present in the existing conda environment `moringa-rad` (created under the old name; `environment.yml` now names it `explainable-radiosensitivity-ml`).
- To run the tests: `conda activate moringa-rad`, then run the commands above. Claude Code installed nothing.

## 9. Static checks (closure)

| Check | Result |
|---|---|
| `ruff check src tests .claude/hooks` | All checks passed |
| `ruff format --check src tests .claude/hooks` | 14 files already formatted |
| `git check-ignore --no-index --verbose --non-matching` | Raw CSV, manuscript PDF, `results/tables/*`, `figures/generated/*`: ignored. Manifests and `references/source_manuscripts/{manifest.yaml,README.md}`: tracked |
| Stale-reference sweep (`grep` for old phase, figure and ID patterns, old filenames, "284 data rows", "not yet supplied") | Only intentional history remains (prototype history, "former ID" column, rename records in this report) |
| Python compile, pytest | Not run (permission rule) |

## 10. Specialists and skills

All consultations ran as Claude Code subagents (read-only tools; no execution).

**Closure pass:**

| Agent | Contribution |
|---|---|
| radiobiologist | Read the PDF and checked every extracted item:<br>- confirmed the missing printed pages and corrected the page mapping;<br>- added the control description, the sign rule and the Discussion's own caveat;<br>- found the *A*D/figure mismatch, the dual meaning of "enhancement", the pseudo-replication and the dose/plate confounding;<br>- explained why PEF is not SF2;<br>- separated measured results from interpretation |
| research-director | Drafted the scientific-connection section (adopted as linkage §13) and the wording guidance; flagged that the repository's "selective radioprotection" framing goes further than the manuscript (O00.10) |
| reproducibility-auditor | Licence investigation with sources and access dates; flagged the 285-row discrepancy (now resolved); readiness audit; confirmed the hook tests use mocked inputs only |
| software-architect | Confirmed that no active code depends on the legacy items; listed the documentation edits needed; drafted the dependency-decision table; found inconsistencies (CLAUDE.md phase order, ID notes, Python version) |

**Earlier passes:** software-architect, research-director, radiobiologist, radiogenomics-curator, reproducibility-auditor and figure-editor (see the decision log).

**Skills:**
- `publication-figures` and `research-code-review` were invoked in earlier passes.
- No skill was re-invoked at closure. The scientific-integrity and reproducible-python rules were applied.
- Not consulted at any point: ml-methodologist, statistical-reviewer and literature-reviewer (not needed before phase_01–02).

## 11. Outstanding issues

**Need investigator approval:**
- P00.01: commit the deletions.
- P00.02 and P00.03: dependencies and lockfile.
- P00.06: untrack `graphify-out/`.
- P00.07: rename the repository.
- P00.08 and P00.09: hook settings.
- P00.10: proposed phase_02 gate.

**Need investigator input:**
- **O00.01:** the missing manuscript pages, the citation, and how *A*D was computed.
- **O00.02:** CLARIFi licence and uploader.
- O00.03–O00.09: scope questions.
- **O00.10:** project framing.

## 12. Readiness for phase_01

| Criterion | Status |
|---|---|
| Consistent structure, naming and documentation | PASS |
| Prototype archived and recoverable | PASS (local tag verified) |
| CLARIFi integrity | PASS (MD5 match; 285 rows) |
| CLARIFi licence | UNRESOLVED (conservative handling in place) |
| Manuscript integrated with page references | PASS, with limits (pages 3 and 7–12 missing; *A*D computation unexplained) |
| Scientific linkage documented, PEF ≠ SF2 | PASS |
| Legacy cleanup | PASS (retired items are uncommitted deletions; `graphify-out/` untracking pending) |
| Safety hooks | PASS on live checks; pytest pending (investigator) |
| Gate sign-off | Pending |

**Recommendation: CONDITIONAL PASS.** phase_01 (literature review and dataset feasibility) can begin once the investigator signs the gate. Conditions:

1. Run the commands in §8 and confirm the hook tests pass.
2. Carry O00.02 (licence) into phase_01 as a blocker for any **redistribution** or publication of derived CLARIFi data. It is not a blocker for feasibility work.
3. Carry O00.01 (missing manuscript pages) as a limitation. It does not affect phase_01, because the manuscript is motivation only.

Claude Code will not start phase_01 without explicit approval.
