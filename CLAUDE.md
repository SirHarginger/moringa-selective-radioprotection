# CLAUDE.md — Explainable Radiosensitivity ML

## Project identity
Project: **Explainable Radiosensitivity ML** (field: radiogenomics and explainable machine learning). Python package: `radiosensitivity_ml`. Proposed repository name: `explainable-radiosensitivity-ml`; the remote has not been renamed. The earlier prototype is archived as git tag `archive/pre-radiosensitivity-ml` (`docs/prototype_history.md`). Naming conventions: `docs/architecture.md` §2. Phases: phase_00 Architecture and repository standardisation; phase_01 Literature review and dataset feasibility; phase_02 Scientific study design; phase_03 ML pipeline development; phase_04 Investigator-controlled execution and validation; phase_05 Interpretation, visualisation and manuscript preparation.

## Mandate and boundaries
Build a transparent, reviewer-defensible, completely reproducible *research codebase* for a planned paper about explainable ML prediction of cellular radiosensitivity across datasets and cancer types. The attached Moringa radiobiology manuscript is motivation, not an ML training dataset. The existing moringa-selective-radioprotection repository is a preliminary prototype, NOT ground truth and NOT the scientific specification. Always substantiate new scientific claims with traceable primary literature and data documentation.

**HARD RULE: Claude Code must NOT execute model fitting, training, tuning, prediction/inference, SHAP evaluation, grid search, cross-validation, or full scientific data-analysis pipelines.** Prepare code, tests, configs, documentation and commands for a human to run later. Do not trigger ML runs in notebooks, shell, Python, CI, subprocesses, background tasks, MCP tools or delegated subagents. Do not bypass hooks. Only run static analysis, formatters, compile checks and safe lightweight unit tests that do not train or infer models (ask before any ambiguous test). Do not install packages or download datasets without permission. Do not run data extraction without explicit authorization.

## Scientific discipline
- No fabricated citations, datasets, results, metrics, p-values, graphs or biological mechanisms. Label proposals as hypotheses.
- Separate cell viability, clonogenic SF2, crystal violet proliferation, and differential gene expression. They are NOT interchangeable endpoints.
- The Moringa manuscript used V79, DU145 and MCF-7 lines and 0/2 Gy; these are the biological motivation, not enough for standalone ML development.
- No claim of selective phytochemical radioprotection unless treated normal AND tumour-cell measurements support it.
- Explicitly document differences among assays, radiation dose, tissue class, batches, cell line IDs, and publication origins.
- Check train-test duplication and cross-dataset overlap by stable cell line identifiers before any split; split by relevant biological groups.
- All preprocessing and feature selection belong INSIDE training folds; held-out tests must remain untouched.
- Define primary endpoints and preregister evaluation design in docs/protocol.md before implementing models.
- Track dataset URLs, DOIs, licenses, access dates, immutable versions, SHA256, inclusion/exclusion and all transformations.
- Raw data immutable, data never invented or silently imputed. Document missingness and uncertainty. Data sources must be verified before writing download logic.
- Do not confuse statistical association, explanation, causation and experimentally demonstrated protection.

## Code quality
Python >=3.11; src/ package layout; type hints, docstrings, small pure functions, no hidden state; pathlib, ruff, pytest, optional mypy; YAML config with recorded random seeds; no machine-specific absolute paths. No hard-coded outcome data or unexplained constants. No model training or analysis in CI. Pin dependencies using a lockfile after environment review. Use simple scikit-learn baselines before complex architectures. DVC or manifest-based provenance may be proposed but not silently installed.

## Figure and table excellence
Figures must answer a scientific question, display sample sizes/units, distinguish observations from predictions, show uncertainty when estimable, and remain legible in grayscale and colour-blind-safe palettes. Prefer vector PDF/SVG and 300–600 dpi PNG; consistent font sizes, reproducible styles, versioned scripts and captions. Do not manufacture empirical plots. Synthetic fixtures are for tests only and MUST be labelled; never place them in manuscript output.

## Roles / workflow
Use project agents: research-director, radiobiologist, radiogenomics-curator, ml-methodologist, reproducibility-auditor, figure-editor, literature-reviewer, software-architect, statistical-reviewer. Consult them for reviews and specifications; they must not execute model runs.

### Permanent specialist-agent workflow
At the beginning of each substantive research task, identify which installed agents, skills and project instructions are relevant. Consult the appropriate specialists before major scientific or architectural decisions. Use specialists selectively according to the task, rather than invoking every agent unnecessarily. Record which agents and skills were actually used, their recommendations and any unresolved disagreements. Never describe an unperformed consultation as completed.
- Scientific decisions (endpoints, datasets, claims, protocol) need domain review: research-director plus the relevant domain specialists (radiobiologist, radiogenomics-curator, statistical-reviewer, ml-methodologist, literature-reviewer).
- Implementations need software-engineering review (software-architect, `research-code-review` skill) and reproducibility review (reproducibility-auditor; `leakage-audit` skill for data and split code).
- Record consultations in `docs/decision_log.md`. The per-phase reviewer matrix and reconciliation rules are in `docs/agent_workflow.md`.
- Phase gates are listed in `docs/research_roadmap.md`. A gate is passed only when the investigator signs it off in the decision log.
- Before any substantive task, state which agents, skills (`.claude/skills/`) and project instructions (`CLAUDE.md`, `.claude/rules/`) apply, then use them where needed.

Work in staged increments with a plan, assumptions, change list, validation checklist, and explicit user decision gates. Order: phase_01 source inventory, literature evidence map, dataset feasibility; phase_02 scientific protocol; phase_03 implementation; only afterward phase_04 human-executed analyses; then phase_05 interpretation and manuscript.

## Deliverable reporting
For every task specify: files changed; decisions made; sources verified; checks actually performed; checks NOT performed; unresolved blockers. Never claim a model was run, downloaded data verified, or figure generated unless it actually happened.
