# Claude Code research environment

> Moved from `README_RESEARCH_SETUP.md` in phase_00 (lowercase docs naming rule; `docs/decision_log.md` D00.18). Original text kept below unchanged. Notes:
> - The installer `setup_research_claude.py` is **not** in this repository.
> - The safety hook has since been rewritten (`docs/architecture.md` §7).
> - The investigator authorised lint and hook tests for phase_00.

## Install
Run from the project root: `python3 setup_research_claude.py` (optional `--fetch-upstream` stages community resources). Existing files are preserved; inspect differences before editing them. Restart Claude Code to load project instructions.

## Safety
No model runs by Claude Code, including notebooks, predictions, CV, SHAP or scientific data pipelines. Hook guards are best-effort and DO NOT constitute a sandbox; inspect permissions and use a restricted workspace. The installer itself never launches models. Tests/lint may be performed only with deliberate approval. Never grant Claude unrestricted Bash access. Running the installer does not start Claude Code.

## Research workflow
Ask Claude to use `/dataset-feasibility` and `/literature-evidence-map` first; then `/protocol-first`. The repository prototype is not a trusted scientific specification. Human investigator will separately run the approved code, record outputs, and return them for interpretation.

## External materials
With `--fetch-upstream`, clone github/awesome-copilot into a temporary directory, inventory the upstream resource names, and copy matching **text files only** to `.claude/vendor-review/` for human vetting. Files are never activated, installed as plugins, or executed. The manifest logs upstream commit and hashes. This step requires network and git. Community instructions must be adapted from Copilot to Claude Code. Inspect licences before redistribution.
