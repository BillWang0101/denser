"""Tests for the core compress API.

These tests use a mock backend — they don't hit the real Claude API. The
real-API integration test lives in `tests/integration/` (not run in CI by
default; requires `ANTHROPIC_API_KEY` and manual invocation).
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from denser.backends.base import Backend
from denser.cli import main
from denser.compress import CompressionResult, _parse_response, compress
from denser.inspection import inspect
from denser.taxonomy import TaskType


class _MockBackend(Backend):
    """A backend that returns a canned compressed response, for testing the pipeline."""

    def __init__(self, response: str, *, backend_name: str = "mock") -> None:
        self._response = response
        self._backend_name = backend_name
        self.calls: list[tuple[str, str, int]] = []

    def complete(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
        self.calls.append((system, user, max_tokens))
        return self._response

    @property
    def name(self) -> str:
        return self._backend_name

    @property
    def supports_caching(self) -> bool:
        return False


class TestParseResponse:
    def test_valid_response(self) -> None:
        raw = (
            "=== COMPRESSED ===\n"
            "Short text\n"
            "=== RATIONALE ===\n"
            "- Removed filler\n"
            "- Kept constraint\n"
        )
        compressed, rationale = _parse_response(raw)
        assert compressed == "Short text"
        assert "Removed filler" in rationale
        assert "Kept constraint" in rationale

    def test_multiline_compressed(self) -> None:
        raw = (
            "=== COMPRESSED ===\nLine one\nLine two\nLine three\n=== RATIONALE ===\n- Explanation\n"
        )
        compressed, _ = _parse_response(raw)
        assert "Line one" in compressed
        assert "Line three" in compressed

    def test_missing_markers_raises(self) -> None:
        with pytest.raises(ValueError, match="did not match the output contract"):
            _parse_response("just some text without markers")

    def test_empty_compressed_raises(self) -> None:
        raw = "=== COMPRESSED ===\n\n=== RATIONALE ===\n- nothing\n"
        with pytest.raises(ValueError, match="empty"):
            _parse_response(raw)


class TestCompress:
    def test_basic_flow(self) -> None:
        backend = _MockBackend("=== COMPRESSED ===\nShort\n=== RATIONALE ===\n- Did stuff\n")
        result = compress(
            "Some longer input text that we expect to be shortened.",
            task_type="skill",
            backend=backend,
        )
        assert isinstance(result, CompressionResult)
        assert result.task_type == TaskType.SKILL
        assert result.compressed == "Short"
        assert result.backend_name == "mock"
        assert len(backend.calls) == 1

    def test_empty_input_raises(self) -> None:
        backend = _MockBackend("irrelevant")
        with pytest.raises(ValueError, match="empty"):
            compress("", task_type="skill", backend=backend)
        with pytest.raises(ValueError, match="empty"):
            compress("   \n  ", task_type="skill", backend=backend)

    def test_invalid_target_density_raises(self) -> None:
        backend = _MockBackend("irrelevant")
        with pytest.raises(ValueError, match="target_density"):
            compress("x" * 100, task_type="skill", target_density=0.0, backend=backend)
        with pytest.raises(ValueError, match="target_density"):
            compress("x" * 100, task_type="skill", target_density=1.5, backend=backend)

    def test_default_target_density_matches_taxonomy(self) -> None:
        backend = _MockBackend("=== COMPRESSED ===\nS\n=== RATIONALE ===\n- ok\n")
        result = compress("some text", task_type="skill", backend=backend)
        # SKILL spec: density_range=(0.30, 0.45), default midpoint = 0.375
        assert result.target_density == pytest.approx(0.375, abs=0.01)

    def test_target_density_propagates(self) -> None:
        backend = _MockBackend("=== COMPRESSED ===\nS\n=== RATIONALE ===\n- ok\n")
        result = compress("some text", task_type="skill", target_density=0.25, backend=backend)
        assert result.target_density == 0.25

    def test_string_task_type(self) -> None:
        backend = _MockBackend("=== COMPRESSED ===\nS\n=== RATIONALE ===\n- ok\n")
        result = compress("text", task_type="memory", backend=backend)
        assert result.task_type == TaskType.MEMORY_ENTRY

    def test_malformed_response_raises(self) -> None:
        backend = _MockBackend("this is not in the expected format")
        with pytest.raises(ValueError, match="did not match the output contract"):
            compress("input text", task_type="skill", backend=backend)

    def test_actual_density_computed(self) -> None:
        backend = _MockBackend("=== COMPRESSED ===\nshort\n=== RATIONALE ===\n- compressed\n")
        long_input = "This is a much longer input. " * 20
        result = compress(long_input, task_type="skill", backend=backend)
        assert result.original_tokens > result.compressed_tokens
        assert 0 < result.actual_density < 1
        assert result.savings_pct > 0

    def test_preservation_contract_is_passed_as_input_data(self) -> None:
        backend = _MockBackend("=== COMPRESSED ===\nShort\n=== RATIONALE ===\n- ok\n")
        source = "MUST preserve `status=ready`."
        contract = inspect(source, task_type="skill", min_tokens=1).contract

        compress(
            source,
            task_type="skill",
            backend=backend,
            preservation_contract=contract,
        )

        user_message = backend.calls[0][1]
        assert '"preservation_contract"' in user_message
        assert '"source_text"' in user_message
        assert "status=ready" in user_message


class TestCompressCli:
    def test_refuses_existing_output_before_backend_creation(self, tmp_path, monkeypatch) -> None:
        source = tmp_path / "source.md"
        output = tmp_path / "source.dense.md"
        source.write_text("Some source text.", encoding="utf-8")
        output.write_text("existing user content", encoding="utf-8")
        called = False

        def build_backend(*args, **kwargs):
            nonlocal called
            called = True
            return _MockBackend("unused")

        monkeypatch.setattr("denser.cli._build_backend", build_backend)
        result = CliRunner().invoke(
            main,
            ["compress", str(source), "--type", "skill", "--out", str(output)],
        )

        assert result.exit_code != 0
        assert "Refusing to overwrite existing output" in result.output
        assert output.read_text(encoding="utf-8") == "existing user content"
        assert not called
