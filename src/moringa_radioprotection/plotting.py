from __future__ import annotations

import matplotlib.pyplot as plt


def style_publication_axes(ax, *, xlabel: str | None = None, ylabel: str | None = None) -> None:
    """Apply simple journal-like formatting to a matplotlib axis."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="both", which="both", direction="out", length=4, width=1)
    if xlabel is not None:
        ax.set_xlabel(xlabel, labelpad=8)
    if ylabel is not None:
        ax.set_ylabel(ylabel, labelpad=8)
    plt.setp(ax.get_xticklabels(), rotation=0)
    plt.setp(ax.get_yticklabels(), rotation=0)
