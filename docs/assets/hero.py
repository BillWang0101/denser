"""Generate denser's reproducible README and social-preview hero image.

The image uses only measured results from the committed Codex tool-workflow
pilot. It produces `docs/assets/hero.png`, which README.md references and which
can also be uploaded as the repository social preview.

Run: `python docs/assets/hero.py`
Requires: `pip install denser[plot]`
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

OUT_PATH = Path(__file__).parent / "hero.png"


BG = "#07111F"
SURFACE = "#0D1C2E"
SURFACE_STRONG = "#10263B"
GRID = "#16324A"
TEXT = "#F5F8FC"
MUTED = "#8FA8C1"
CYAN = "#28D7C2"
BLUE = "#73A7FF"
AMBER = "#F5C76B"


def _rounded_box(
    ax: plt.Axes,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    facecolor: str,
    edgecolor: str,
    linewidth: float = 1.0,
    radius: float = 0.018,
) -> None:
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            width,
            height,
            boxstyle=f"round,pad=0.008,rounding_size={radius}",
            facecolor=facecolor,
            edgecolor=edgecolor,
            linewidth=linewidth,
        )
    )


def main() -> None:
    """Render the measured-results hero image."""
    fig = plt.figure(figsize=(12.8, 6.4), facecolor=BG)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # Quiet instrument-panel grid: enough structure to feel technical without
    # competing with the evidence.
    for x in [i / 20 for i in range(1, 20)]:
        ax.plot([x, x], [0, 1], color=GRID, linewidth=0.45, alpha=0.35)
    for y in [i / 10 for i in range(1, 10)]:
        ax.plot([0, 1], [y, y], color=GRID, linewidth=0.45, alpha=0.35)
    ax.add_patch(Rectangle((0, 0), 0.012, 1, facecolor=CYAN, edgecolor="none"))

    ax.text(
        0.065,
        0.875,
        "OPEN-SOURCE RESEARCH TOOL  /  ALPHA",
        color=CYAN,
        fontsize=12,
        fontweight="bold",
        family="DejaVu Sans",
        va="center",
    )
    ax.text(
        0.06,
        0.705,
        "DENSER",
        color=TEXT,
        fontsize=60,
        fontweight="bold",
        family="DejaVu Sans",
        va="center",
    )
    ax.text(
        0.064,
        0.585,
        "Behavior-validated context reduction",
        color=BLUE,
        fontsize=21,
        fontweight="bold",
        family="DejaVu Sans",
        va="center",
    )
    ax.text(
        0.064,
        0.515,
        "Remove unnecessary context. Preserve required behavior.",
        color=MUTED,
        fontsize=14,
        family="DejaVu Sans",
        va="center",
    )

    # Measured end-to-end flow from the committed six-call Codex pilot.
    _rounded_box(
        ax,
        0.585,
        0.625,
        0.16,
        0.16,
        facecolor=SURFACE,
        edgecolor=GRID,
        linewidth=1.3,
    )
    ax.text(0.665, 0.735, "COMPLETE", color=MUTED, fontsize=10, fontweight="bold", ha="center")
    ax.text(0.665, 0.675, "277,871", color=TEXT, fontsize=22, fontweight="bold", ha="center")
    ax.text(0.665, 0.64, "full input tokens", color=MUTED, fontsize=9, ha="center")

    ax.annotate(
        "",
        xy=(0.805, 0.705),
        xytext=(0.755, 0.705),
        arrowprops={"arrowstyle": "-|>", "color": CYAN, "lw": 2.2},
    )
    ax.text(0.78, 0.745, "SELECT", color=CYAN, fontsize=8, fontweight="bold", ha="center")

    _rounded_box(
        ax,
        0.815,
        0.625,
        0.14,
        0.16,
        facecolor=SURFACE_STRONG,
        edgecolor=CYAN,
        linewidth=1.6,
    )
    ax.text(0.885, 0.735, "SELECTED", color=CYAN, fontsize=10, fontweight="bold", ha="center")
    ax.text(0.885, 0.675, "243,210", color=TEXT, fontsize=22, fontweight="bold", ha="center")
    ax.text(0.885, 0.64, "full input tokens", color=MUTED, fontsize=9, ha="center")

    ax.text(
        0.77,
        0.55,
        "Required policies kept  /  archived handbook removed",
        color=MUTED,
        fontsize=9.5,
        family="DejaVu Sans",
        ha="center",
    )

    stats = [
        ("12.47%", "LESS FULL INPUT", CYAN),
        ("6 / 6", "SELECTED RUNS PASSED", BLUE),
        ("6 / 6", "REGRESSIONS DETECTED", AMBER),
    ]
    start_x = 0.06
    width = 0.28
    gap = 0.025
    for index, (value, label, accent) in enumerate(stats):
        x = start_x + index * (width + gap)
        _rounded_box(
            ax,
            x,
            0.16,
            width,
            0.19,
            facecolor=SURFACE,
            edgecolor=GRID,
            linewidth=1.1,
        )
        ax.add_patch(
            Rectangle((x + 0.018, 0.181), 0.006, 0.145, facecolor=accent, edgecolor="none")
        )
        ax.text(x + 0.045, 0.275, value, color=TEXT, fontsize=24, fontweight="bold", va="center")
        ax.text(x + 0.045, 0.215, label, color=accent, fontsize=9.5, fontweight="bold", va="center")

    ax.text(
        0.94,
        0.07,
        "Measured on the committed Codex tool-workflow pilot",
        color=MUTED,
        fontsize=8.5,
        ha="right",
    )

    # Exactly 1280 x 640 pixels. Do not crop: GitHub expects a 2:1 preview.
    fig.savefig(OUT_PATH, dpi=100, facecolor=BG)
    plt.close(fig)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
