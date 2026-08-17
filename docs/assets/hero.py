"""Generate the README hero image — an experimental density-sweep illustration.

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
    """One possible non-universal shape used in the schematic."""
    return height * np.exp(-((x - peak) ** 2) / (2 * width**2))


def main() -> None:
    """Render the schematic density-curve hero image."""
    x = np.linspace(0.05, 1.05, 300)

    # Three possible shapes. Values are schematic and deliberately not tied to
    # task types or measured results.
    curves = [
        {
            "label": "interior best",
            "values": _curve(x, 0.48, 0.96, 0.18),
            "color": "#e04b4b",
        },
        {
            "label": "original best",
            "values": 0.58 + 0.36 * np.clip(x, 0, 1),
            "color": "#4b8ae0",
        },
        {
            "label": "flat / noisy",
            "values": 0.78 + 0.035 * np.sin(25 * x) + 0.02 * x,
            "color": "#3ba374",
        },
    ]

    # 12.8 x 6.4 inches @ 100 dpi → 1280 x 640 pixels exactly,
    # which is GitHub's recommended Social preview size (2:1 aspect).
    fig, ax = plt.subplots(figsize=(12.8, 6.4))

    for c in curves:
        ax.plot(x, c["values"], linewidth=2.5, label=c["label"], color=c["color"])

    ax.set_xlabel("compression ratio ρ  (compressed tokens / original)", fontsize=11)
    ax.set_ylabel("observed check score", fontsize=11)
    ax.set_title(
        "Experimental Density Sweep — possible shapes, not measured results",
        fontsize=13,
        pad=14,
    )
    ax.set_xlim(0, 1.08)
    ax.set_ylim(0, 1.15)
    ax.invert_xaxis()  # denser → smaller ρ on the right
    ax.grid(alpha=0.25)
    ax.legend(title="illustrative shape", loc="upper right", frameon=True)

    # Subtle shading for the "danger zones"
    ax.axvspan(0.0, 0.15, color="red", alpha=0.06, zorder=-1)
    ax.axvspan(0.9, 1.08, color="orange", alpha=0.06, zorder=-1)
    ax.text(
        0.075,
        0.08,
        "higher information-loss risk",
        ha="center",
        va="center",
        fontsize=8.5,
        color="#c23030",
        alpha=0.8,
    )
    ax.text(
        0.99,
        0.08,
        "original candidate",
        ha="right",
        va="center",
        fontsize=8.5,
        color="#c2800b",
        alpha=0.8,
    )

    fig.tight_layout()
    # Exactly 100 dpi + 12.8×6.4 figsize → 1280×640 pixels, GitHub social preview spec.
    # Do NOT use bbox_inches="tight" here; that would crop and change dimensions.
    fig.savefig(OUT_PATH, dpi=100)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
