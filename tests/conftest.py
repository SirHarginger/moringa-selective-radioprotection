"""Shared pytest configuration.

Marker ``model_fit``: the test fits a (tiny) estimator on SYNTHETIC software-test data.
Such tests never touch real data and produce no scientific result, but they do execute
model fitting, so Claude Code never runs them; the investigator does
(``python -m pytest -m model_fit``). Run everything else with ``-m "not model_fit"``.
"""

from __future__ import annotations


def pytest_configure(config) -> None:
    config.addinivalue_line(
        "markers", "model_fit: fits a small estimator on synthetic data (investigator-run)"
    )
