"""Tests for the Signal Density Curve module."""

from __future__ import annotations

import pytest

from denser.backends.base import Backend
from denser.curve import _fit_quadratic, _locate_peak, curve
from denser.eval import GoldenTask, TestCase
from denser.taxonomy import TaskType


class _DeterministicCompressor(Backend):
    """Compressor backend that always returns the same canned output.

    Useful for testing the curve machinery without hitting a live API.
    """

    def __init__(self, response: str) -> None:
        self._response = response

    def complete(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
        return self._response

    @property
    def name(self) -> str:
        return "deterministic"

    @property
    def supports_caching(self) -> bool:
        return False


class _DensityRespectingCompressor(Backend):
    """Compressor mock that honors target density by truncating the input.

    Reads the target percentage from the system prompt (looking for the
    `X%` token the real prompt builder inserts) and returns a truncated
    version of the user text at that density. Enables realistic curve tests.
    """

    def complete(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
        import re as _re

        m = _re.search(r"(\d+)%\s+of the\s+original", system)
        pct = int(m.group(1)) if m else 50
        keep_chars = max(4, int(len(user) * pct / 100))
        truncated = user[:keep_chars]
        return (
            "=== COMPRESSED ===\n"
            f"{truncated}\n"
            "=== RATIONALE ===\n"
            f"- Truncated to {pct}% per target density.\n"
        )

    @property
    def name(self) -> str:
        return "density_respecting_mock"

    @property
    def supports_caching(self) -> bool:
        return False


class _ScriptedJudge(Backend):
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self._idx = 0

    def complete(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
        resp = self._responses[self._idx % len(self._responses)]
        self._idx += 1
        return resp

    @property
    def name(self) -> str:
        return "scripted"

    @property
    def supports_caching(self) -> bool:
        return False


class TestFitQuadratic:
    def test_exact_quadratic(self) -> None:
        # y = -2x² + 4x + 1 — peak at x=1, y=3
        xs = [0.0, 0.5, 1.0, 1.5, 2.0]
        ys = [-2 * x * x + 4 * x + 1 for x in xs]
        coeffs = _fit_quadratic(xs, ys)
        assert coeffs is not None
        a, b, c = coeffs
        assert a == pytest.approx(-2, abs=1e-6)
        assert b == pytest.approx(4, abs=1e-6)
        assert c == pytest.approx(1, abs=1e-6)

    def test_too_few_points(self) -> None:
        assert _fit_quadratic([0.5, 0.7], [0.8, 0.9]) is None
        assert _fit_quadratic([0.5], [0.8]) is None

    def test_singular_input(self) -> None:
        # Constant x — no quadratic fit possible
        assert _fit_quadratic([0.5, 0.5, 0.5], [0.1, 0.2, 0.3]) is None


class TestLocatePeak:
    def test_concave_fit(self) -> None:
        # y = -2x² + 4x + 1 — peak at x=1, y=3
        xs = [0.0, 0.5, 1.0, 1.5, 2.0]
        ys = [-2 * x * x + 4 * x + 1 for x in xs]
        coeffs = _fit_quadratic(xs, ys)
        peak_x, peak_y = _locate_peak(coeffs, xs, ys)
        assert peak_x == pytest.approx(1.0, abs=1e-3)
        assert peak_y == pytest.approx(3.0, abs=1e-3)

    def test_clamps_to_sampled_range(self) -> None:
        # Quadratic peak is at x=10, but sampled range is [0, 2]
        xs = [0.0, 1.0, 2.0]
        ys = [0.0, 0.5, 1.0]  # monotone within sampled range
        coeffs = _fit_quadratic(xs, ys)
        peak_x, _ = _locate_peak(coeffs, xs, ys)
        assert min(xs) <= peak_x <= max(xs)

    def test_convex_falls_back_to_argmax(self) -> None:
        # y = x² (convex, bowl) — peak should fall back to argmax of raw data
        xs = [0.0, 0.5, 1.0, 1.5, 2.0]
        ys = [x * x for x in xs]  # increasing → argmax at x=2
        coeffs = _fit_quadratic(xs, ys)
        assert coeffs is not None
        assert coeffs[0] > 0  # convex
        peak_x, _ = _locate_peak(coeffs, xs, ys)
        assert peak_x == 2.0


class TestCurve:
    def test_empty_text_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            curve(
                "",
                task_type="skill",
                densities=(0.3, 0.5, 1.0),
                compressor_backend=_DeterministicCompressor("x"),
                judge_backend=_ScriptedJudge(["yes"]),
            )

    def test_out_of_range_density_raises(self) -> None:
        with pytest.raises(ValueError, match="densities"):
            curve(
                "x" * 100,
                task_type="skill",
                densities=(0.3, 1.5),
                compressor_backend=_DeterministicCompressor("x"),
                judge_backend=_ScriptedJudge(["yes"]),
            )

    def test_basic_sweep(self) -> None:
        # Compressor always returns the same short text.
        # Judge always returns yes.
        task = GoldenTask(
            task_type=TaskType.SKILL,
            name="t",
            description="",
            task_prompt="Check {input}",
            test_cases=(TestCase(name="c", vars={}, expected="yes"),),
        )
        comp_response = "=== COMPRESSED ===\nshort\n=== RATIONALE ===\n- compressed\n"
        result = curve(
            "a longer original text that gets compressed",
            task_type="skill",
            densities=(0.3, 0.5, 1.0),
            golden_tasks=[task],
            compressor_backend=_DeterministicCompressor(comp_response),
            judge_backend=_ScriptedJudge(["yes"]),
        )
        assert len(result.points) == 3
        # ρ=1.0 point is uncompressed (no compressor call)
        assert result.points[-1].actual_density == 1.0
        # ρ<1.0 points use the compressor
        assert all(p.pass_rate == 1.0 for p in result.points)

    def test_peak_located_for_concave_shape(self) -> None:
        # Judge returns pass for middle densities, fail at extremes — the canonical
        # concave-curve shape. Use the density-respecting compressor so each
        # sampled density produces a different actual density.
        task = GoldenTask(
            task_type=TaskType.SKILL,
            name="t",
            description="",
            task_prompt="Check {input}",
            test_cases=(TestCase(name="c", vars={}, expected="yes"),),
        )
        # Judge script: densities 0.2, 0.4, 0.6, 0.8, 1.0 → no, yes, yes, yes, no
        judge_script = ["no", "yes", "yes", "yes", "no"]
        text_input = "x" * 200  # long enough for density truncation to produce variance
        result = curve(
            text_input,
            task_type="skill",
            densities=(0.2, 0.4, 0.6, 0.8, 1.0),
            golden_tasks=[task],
            compressor_backend=_DensityRespectingCompressor(),
            judge_backend=_ScriptedJudge(judge_script),
        )
        # Peak should land in the mid-density zone where judge says yes.
        assert 0.3 < result.peak_density < 0.9
        assert result.peak_pass_rate >= 0.9
