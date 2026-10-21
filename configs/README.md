# configs/

The only active configuration folder: YAML files for paths, seeds, split definitions and endpoint definitions. File names are lowercase and descriptive (e.g. `paths.yaml`, `splits.yaml`).

No analysis configuration is written before the protocol (`docs/protocol.md`) fixes the design. The one exception is `phase_01_identifier_qc.yaml`. It holds the pre-fixed, descriptive identity and eligibility rules for the investigator-run identifier QC (decision log D01.16). It contains no model or analysis settings.

Rules:
- All paths are relative to the repository root.
- Every random seed is recorded here, never hard-coded in code.
- No outcome values or unexplained constants.
