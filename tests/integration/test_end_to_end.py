"""End-to-end integration tests against the real Claude API.

Gated by the `integration` pytest marker and skipped automatically when
`ANTHROPIC_API_KEY` is not set. These tests are not run in CI by default;
run locally before releases with:

    pytest tests/integration/ -m integration -v
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from denser import compress
from denser.backends import ClaudeBackend
from denser.taxonomy import TaskType

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not set",
    ),
]


def _examples_root() -> Path:
    return Path(__file__).resolve().parents[2] / "examples"


def test_live_compress_skill() -> None:
    """Compress the PR-review example skill and verify sane output."""
    sample = (_examples_root() / "skills" / "01_pr_review" / "verbose.md").read_text(
        encoding="utf-8"
    )
    backend = ClaudeBackend(model="claude-opus-4-6")
    result = compress(sample, task_type=TaskType.SKILL, backend=backend)

    # Compression should produce non-empty output well short of the original.
    assert result.compressed.strip()
    assert result.compressed_tokens < result.original_tokens
    # Skill sweet spot is 0.30-0.45; allow generous margin (±0.2) to avoid
    # test flakiness from model-day variance.
    assert 0.10 <= result.actual_density <= 0.70


def test_live_compress_tool_description() -> None:
    """Compress the web_search example and verify core preservations."""
    sample = (_examples_root() / "tool_descriptions" / "01_web_search" / "verbose.md").read_text(
        encoding="utf-8"
    )
    backend = ClaudeBackend(model="claude-opus-4-6")
    result = compress(sample, task_type=TaskType.TOOL_DESCRIPTION, backend=backend)

    # Tool descriptions should keep the "when to use" and "when NOT to use" distinctions.
    lower = result.compressed.lower()
    assert result.compressed.strip()
    assert "use" in lower  # mentions some form of usage guidance
    assert result.compressed_tokens < result.original_tokens
