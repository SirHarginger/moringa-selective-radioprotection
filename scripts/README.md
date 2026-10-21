# scripts/

Thin command-line entry points. Run each one from the repository root; every script adds `src/` to the path itself. The full workflow is in the top-level `README.md`.

| Script | Status | Purpose |
|---|---|---|
| `acquire_data.py` | WORKING | Downloads and verifies DepMap 24Q4 core files and Cellosaurus 56.0 (`--verify`, `--dry-run`, `--batch-corrected`, `--audit-23q4`, `--yard`, `--skip-cellosaurus`) |
| `run_preprocessing.py` | WORKING | Identifier QC and analysis-population definition (`--config configs/preprocessing.yaml`, `--check-inputs`) |
| `run_model.py`, `evaluate_models.py`, `run_explainability.py`, `generate_figures.py` | PLANNED | Specified in `docs/phase_03_implementation_spec.md`; not created until implemented and tested |
| `acquire_phase_01.sh` | SUPERSEDED | Kept only for the optional GEO/ICLAC context downloads |

Scripts that fit, evaluate, predict or explain models are run only by the human investigator, never by Claude Code or CI.
