"""Generate the README hero image — the Signal Density Curve concept illustration.

This script is reproducible (fixed seeds, deterministic output). It produces
`docs/assets/hero.png` which README.md references.

Run: `python docs/assets/hero.py`
Requires: `pip install denser[plot]`
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

OUT_PATH = Path(__file__).parent / "hero.png"


def _curve(x: np.ndarray, peak: float, height: float, width: float) -> np.ndarray:
    """A concave curve peaked at `peak` with given height and width."""
    return height * np.exp(-((x - peak) ** 2) / (2 * width**2))


def main() -> None:
    x = np.linspace(0.05, 1.05, 300)

    # Three illustrative curves — different task types with different sweet spots.
    # Values here are schematic, not measured.
    curves = [
        {"label": "skill", "peak": 0.34, "height": 0.98, "width": 0.16, "color": "#e04b4b"},
        {
            "label": "system_prompt",
            "peak": 0.48,
            "height": 0.96,
            "width": 0.18,
            "color": "#4b8ae0",
        },
        {
            "label": "memory_entry",
            "peak": 0.68,
            "height": 0.92,
            "width": 0.20,
            "color": "#3ba374",
        },
    ]

    fig, ax = plt.subplots(figsize=(10, 5.5))

    for c in curves:
        y = _curve(x, c["peak"], c["height"], c["width"])
        ax.plot(x, y, linewidth=2.5, label=c["label"], color=c["color"])
        # Mark the peak with a dotted vertical.
        ax.axvline(c["peak"], color=c["color"], linestyle=":", alpha=0.5, linewidth=1)
        ax.annotate(
            f"ρ*={c['peak']:.2f}",
            xy=(c["peak"], c["height"]),
            xytext=(c["peak"], c["height"] + 0.04),
            ha="center",
            fontsize=10,
            color=c["color"],
            fontweight="bold",
        )

    ax.set_xlabel("compression ratio ρ  (compressed tokens / original)", fontsize=11)
    ax.set_ylabel("task pass-rate", fontsize=11)
    ax.set_title(
        "Signal Density Curve — each task type has its own sweet spot",
        fontsize=13,
        pad=14,
    )
    ax.set_xlim(0, 1.08)
    ax.set_ylim(0, 1.15)
    ax.invert_xaxis()  # denser → smaller ρ on the right
    ax.grid(alpha=0.25)
    ax.legend(title="task type", loc="lower left", frameon=True)

    # Subtle shading for the "danger zones"
    ax.axvspan(0.0, 0.15, color="red", alpha=0.06, zorder=-1)
    ax.axvspan(0.9, 1.08, color="orange", alpha=0.06, zorder=-1)
    ax.text(
        0.075,
        0.08,
        "over-compressed\n(information loss)",
        ha="center",
        va="center",
        fontsize=8.5,
        color="#c23030",
        alpha=0.8,
    )
    ax.text(
        0.99,
        0.08,
        "uncompressed\n(attention dilution)",
        ha="right",
        va="center",
        fontsize=8.5,
        color="#c2800b",
        alpha=0.8,
    )

    fig.tight_layout()
    fig.savefig(OUT_PATH, dpi=150, bbox_inches="tight")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
