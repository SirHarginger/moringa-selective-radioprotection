# Agent and skill workflow

Specialist agents and skills are installed in `.claude/`. They advise; they never run models or analyses. Agents have read and web tools only (Read, Grep, Glob, WebSearch, WebFetch). They cannot edit files or run shell commands.

## 1. Installed agents (`.claude/agents/`)

| Agent | Responsibility |
|---|---|
| `research-director` | Aims, novelty, primary outcomes, competing hypotheses, decision gates; challenges unjustified claims |
| `radiobiologist` | Dose, SF2, assay meaning, proliferation vs survival, normal vs tumour selectivity, confounding |
| `radiogenomics-curator` | Public datasets (CLARIFi, DepMap/CCLE, Yard, NCI-60): releases, licences, identifiers, overlap, dataset cards, ETL specifications |
| `ml-methodologist` | Leakage-safe pipelines, group-aware splits, nested CV design, baselines, calibration |
| `statistical-reviewer` | Unit of analysis, replicates, multiplicity, uncertainty, feature-importance confidence, transportability |
| `reproducibility-auditor` | Versioning, checksum manifests, licences, deduplication, environment locks, audit trails, hooks; reports pass/fail/unknown |
| `literature-reviewer` | Search strategies, evidence tables, DOI/PMID verification, novelty matrix |
| `software-architect` | Package layout, naming, data contracts, typed modules, configuration, dependencies, tests, static-only CI |
| `figure-editor` | Figure and table specs, units, uncertainty, accessible palettes, exports, captions |

## 2. Installed skills (`.claude/skills/`)

| Skill | Use when |
|---|---|
| `dataset-feasibility` | phase_01: dataset cards and go/no-go matrix |
| `literature-evidence-map` | phase_01: verifiable evidence map and novelty matrix |
| `protocol-first` | phase_02: writing `docs/protocol.md` |
| `leakage-audit` | phase_02–03: split keys, aliases, in-fold preprocessing |
| `research-code-review` | phase_00 onwards: any code or configuration change |
| `publication-figures` | Any figure or table spec, or plotting code |
| `manuscript-methods` | phase_05: drafting methods, only after verification |

Rules in `.claude/rules/` (`scientific-integrity`, `reproducible-python`, `plotting`) apply automatically. The Bash hook in `.claude/hooks/` blocks model and analysis execution. It is best-effort and not a sandbox (`docs/architecture.md` §7).

## 3. Required review by phase

| Phase | Lead | Required reviewers |
|---|---|---|
| phase_00 Architecture and repository standardisation | software-architect | research-director, radiobiologist, radiogenomics-curator, reproducibility-auditor, figure-editor |
| phase_01 Literature review and dataset feasibility | literature-reviewer, radiogenomics-curator | research-director, radiobiologist, reproducibility-auditor |
| phase_02 Scientific study design | research-director | ml-methodologist, statistical-reviewer, radiobiologist |
| phase_03 ML pipeline development | software-architect | ml-methodologist (leakage), reproducibility-auditor, figure-editor (plotting code) |
| phase_04 Investigator-controlled execution and validation | investigator | reproducibility-auditor (run records), statistical-reviewer |
| phase_05 Interpretation, visualisation and manuscript preparation | research-director | statistical-reviewer, radiobiologist, figure-editor, literature-reviewer (citations) |

Choose specialists to fit the task. Small changes do not need every reviewer.

## 4. Reconciling recommendations

1. Collect each specialist's recommendations, verbatim or as faithful short summaries.
2. Where specialists agree, adopt the recommendation.
3. Where they disagree:
   - prefer the investigator's explicit instructions;
   - then the more conservative option scientifically (less claim, more verification);
   - then the simpler option for software.
   Record the disagreement and the reason for the choice.
4. Anything that changes scope, endpoints or data sources, deletes files, or touches hooks or permissions without the investigator's instruction goes to the investigator as an open decision.

## 5. Documenting reviews

Record each consultation in `docs/decision_log.md` (agent consultations table) and in the phase's verification report. Each record gives:

- date and phase;
- agents and skills **actually** invoked, and how (subagent delegation, or instructions read manually);
- key recommendations;
- what was adopted, what was not, and why;
- unresolved disagreements.

Never describe a review as done if it did not happen.

## 6. phase_00 record

See `docs/phase_00_verification.md` §10.
