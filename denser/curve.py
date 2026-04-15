"""Signal Density Curve.

For a given (text, task type), sweep several target densities, compress at
each, evaluate, and locate the peak — the sweet spot.

The curve is modeled as concave. We fit a quadratic `f(ρ) = aρ² + bρ + c`
via least squares and locate the peak at `ρ* = -b / (2a)` (clamped to the
sampled range). If the fit fails (a ≥ 0, or fewer than 3 points), we fall
back to the highest raw-data density.

Public API:
    curve(text, task_type, ...) -> DensityCurve
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from denser.backends import Backend, ClaudeBackend
from denser.compress import compress
from denser.eval import GoldenTask, evaluate, load_golden_tasks
from denser.taxonomy import TaskType

logger = logging.getLogger(__name__)

DEFAULT_DENSITIES = (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)


@dataclass
class DensityPoint:
    """One sample on the Signal Density Curve."""

    target_density: float
    actual_density: float
    pass_rate: float
    compressed_text: str


@dataclass
class DensityCurve:
    """The signal density curve for one (text, task type) pair."""

    task_type: TaskType
    original_text: str
    points: list[DensityPoint] = field(default_factory=list)
    peak_density: float = 1.0
    peak_pass_rate: float = 0.0
    fit_coeffs: tuple[float, float, float] | None = None

    def to_dict(self) -> dict:
        return {
            "task_type": self.task_type.value,
            "points": [
                {
                    "target_density": p.target_density,
                    "actual_density": p.actual_density,
                    "pass_rate": p.pass_rate,
                }
                for p in self.points
            ],
            "peak_density": self.peak_density,
            "peak_pass_rate": self.peak_pass_rate,
            "fit_coeffs": list(self.fit_coeffs) if self.fit_coeffs else None,
        }

    def plot(self, out: str | Path | None = None) -> None:
        """Render the curve to a matplotlib PNG.

        Raises `ImportError` if matplotlib isn't installed. Install the `plot`
        extra: `pip install denser[plot]`.
        """
        try:
            import matplotlib.pyplot as plt  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "matplotlib required for plotting. Run: pip install denser[plot]"
            ) from exc

        xs = [p.actual_density for p in self.points]
        ys = [p.pass_rate for p in self.points]

        fig, ax = plt.subplots(figsize=(7, 5))
        ax.scatter(xs, ys, label="measured", s=60, zorder=3)

        if self.fit_coeffs:
            a, b, c = self.fit_coeffs
            import numpy as np  # type: ignore[import-not-found]

            rho = np.linspace(min(xs), max(xs), 100)
            fit = a * rho * rho + b * rho + c
            ax.plot(rho, fit, linestyle="--", alpha=0.7, label="quadratic fit")

        ax.axvline(
            self.peak_density,
            color="tab:red",
            linestyle=":",
            alpha=0.7,
            label=f"peak ρ* = {self.peak_density:.2f}",
        )
        ax.set_xlabel("compression ratio ρ (compressed / original)")
        ax.set_ylabel("task pass-rate")
        ax.set_title(f"Signal Density Curve — {self.task_type.value}")
        ax.set_xlim(0, 1.05)
        ax.set_ylim(0, 1.05)
        ax.grid(alpha=0.3)
        ax.legend()

        if out is None:
            plt.show()
        else:
            fig.tight_layout()
            fig.savefig(out, dpi=150)
            plt.close(fig)


def _fit_quadratic(xs: list[float], ys: list[float]) -> tuple[float, float, float] | None:
    """Least-squares quadratic fit y = a*x² + b*x + c.

    Returns `(a, b, c)` or `None` if fitting fails (too few points, singular).
    """
    if len(xs) < 3:
        return None

    # Build normal equations for y = a*x² + b*x + c
    n = len(xs)
    sx = sum(xs)
    sx2 = sum(x * x for x in xs)
    sx3 = sum(x**3 for x in xs)
    sx4 = sum(x**4 for x in xs)
    sy = sum(ys)
    sxy = sum(x * y for x, y in zip(xs, ys, strict=True))
    sx2y = sum(x * x * y for x, y in zip(xs, ys, strict=True))

    # Solve 3x3 linear system via Cramer's rule.
    #   [sx4 sx3 sx2] [a]   [sx2y]
    #   [sx3 sx2 sx ] [b] = [ sxy]
    #   [sx2 sx  n  ] [c]   [  sy]
    def det3(m: list[list[float]]) -> float:
        return (
            m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
        )

    base = [
        [sx4, sx3, sx2],
        [sx3, sx2, sx],
        [sx2, sx, float(n)],
    ]
    d = det3(base)
    if abs(d) < 1e-10:
        return None

    da = det3(
        [
            [sx2y, sx3, sx2],
            [sxy, sx2, sx],
            [sy, sx, float(n)],
        ]
    )
    db = det3(
        [
            [sx4, sx2y, sx2],
            [sx3, sxy, sx],
            [sx2, sy, float(n)],
        ]
    )
    dc = det3(
        [
            [sx4, sx3, sx2y],
            [sx3, sx2, sxy],
            [sx2, sx, sy],
        ]
    )
    return (da / d, db / d, dc / d)


def _locate_peak(
    coeffs: tuple[float, float, float] | None,
    xs: list[float],
    ys: list[float],
) -> tuple[float, float]:
    """Locate the curve's peak, clamped to the sampled density range.

    If the fit is concave (a < 0), use `-b / (2a)`. Otherwise, fall back to
    argmax over raw data.
    """
    if coeffs is not None:
        a, b, c = coeffs
        if a < -1e-6:  # concave (as expected)
            xstar = -b / (2 * a)
            xstar = max(min(xs), min(max(xs), xstar))
            ystar = a * xstar * xstar + b * xstar + c
            return xstar, ystar

    # Fallback: argmax of raw data
    best_idx = max(range(len(xs)), key=lambda i: ys[i])
    return xs[best_idx], ys[best_idx]


def curve(
    text: str,
    *,
    task_type: TaskType | str,
    densities: tuple[float, ...] | list[float] = DEFAULT_DENSITIES,
    golden_tasks: list[GoldenTask] | None = None,
    compressor_backend: Backend | None = None,
    judge_backend: Backend | None = None,
    n_trials: int = 1,
) -> DensityCurve:
    """Compute the Signal Density Curve for `text` at `task_type`.

    For each target density in `densities`, compresses the text, evaluates
    pass-rate, and adds a point to the curve. Fits a concave quadratic and
    locates the peak.

    Parameters
    ----------
    text : str
        The text to analyze.
    task_type : TaskType | str
        Task type driving compression strategy and golden tasks.
    densities : tuple | list
        Target density values to sample. Values at 1.0 are treated as
        "original text, uncompressed" (no API call to the compressor).
    golden_tasks : list | None
        Override tasks. If None, loads built-in fixtures.
    compressor_backend : Backend | None
        Backend for compression. Defaults to Claude Opus 4.6.
    judge_backend : Backend | None
        Backend for evaluation. Defaults to Claude Haiku 4.5.
    n_trials : int
        Evaluation trials per density.
    """
    if not text or not text.strip():
        raise ValueError("Cannot compute curve for empty text")

    tt = task_type if isinstance(task_type, TaskType) else TaskType.parse(task_type)
    densities = tuple(sorted(set(densities)))
    if not all(0.1 <= d <= 1.0 for d in densities):
        raise ValueError("All densities must lie in [0.1, 1.0]")

    if compressor_backend is None:
        compressor_backend = ClaudeBackend()

    points: list[DensityPoint] = []
    for rho in densities:
        if rho >= 1.0:
            # Uncompressed baseline; don't spend a compressor call.
            compressed_text = text
            actual_rho = 1.0
        else:
            result = compress(
                text,
                task_type=tt,
                target_density=rho,
                backend=compressor_backend,
            )
            compressed_text = result.compressed
            actual_rho = result.actual_density

        eval_report = evaluate(
            compressed_text,
            task_type=tt,
            golden_tasks=golden_tasks,
            judge_backend=judge_backend,
            n_trials=n_trials,
        )
        points.append(
            DensityPoint(
                target_density=rho,
                actual_density=actual_rho,
                pass_rate=eval_report.overall_pass_rate,
                compressed_text=compressed_text,
            )
        )
        logger.info(
            "curve: ρ=%.2f (actual=%.2f) → pass_rate=%.3f",
            rho,
            actual_rho,
            eval_report.overall_pass_rate,
        )

    xs = [p.actual_density for p in points]
    ys = [p.pass_rate for p in points]
    coeffs = _fit_quadratic(xs, ys)
    peak_x, peak_y = _locate_peak(coeffs, xs, ys)

    return DensityCurve(
        task_type=tt,
        original_text=text,
        points=points,
        peak_density=peak_x,
        peak_pass_rate=peak_y,
        fit_coeffs=coeffs,
    )


# Expose an unused-import guard for module consumers using `from denser.curve import *`.
_ = statistics
_ = load_golden_tasks


__all__ = ["DensityCurve", "DensityPoint", "curve"]
