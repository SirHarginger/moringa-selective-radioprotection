# tests/

Unit tests for pure functions such as schemas, identifier mapping, split and leakage checks, figure style and the Claude Code safety hook. Tests must never train, tune, predict or run scientific analyses.

- `test_safety_hooks.py` feeds mocked hook payloads to `.claude/hooks/block_model_execution.py`. No command is executed.
- `fixtures/` holds small synthetic inputs only. Every fixture file name starts with `SYNTHETIC_`, and its first line or first field says "SYNTHETIC - TEST ONLY". Fixtures must never reach `figures/generated/` or `manuscript/`.

How to run them (investigator only): `python3 -m pytest tests`. Project permission settings stop Claude Code from running Python.
