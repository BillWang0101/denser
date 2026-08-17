"""Tests for the reproducible Codex capability-profile benchmark."""

from __future__ import annotations

from pathlib import Path

from benchmarks.codex_profile_audit import _sha256, _summarize


def test_source_hash_is_stable_across_line_endings(tmp_path: Path) -> None:
    lf = tmp_path / "lf.txt"
    crlf = tmp_path / "crlf.txt"
    lf.write_bytes(b"one\ntwo\n")
    crlf.write_bytes(b"one\r\ntwo\r\n")

    assert _sha256(lf) == _sha256(crlf)


def test_summarize_profile_calls() -> None:
    calls = [
        {
            "status": "completed",
            "passed": True,
            "transport_fallback": False,
            "usage": {
                "input_tokens": 100,
                "cached_input_tokens": 20,
                "cache_write_input_tokens": 0,
                "output_tokens": 5,
                "reasoning_output_tokens": 2,
            },
        },
        {
            "status": "completed",
            "passed": False,
            "transport_fallback": True,
            "usage": {
                "input_tokens": 120,
                "cached_input_tokens": 0,
                "cache_write_input_tokens": 0,
                "output_tokens": 7,
                "reasoning_output_tokens": 3,
            },
        },
    ]

    assert _summarize(calls) == {
        "calls": 2,
        "completed_calls": 2,
        "passed_calls": 1,
        "pass_rate": 0.5,
        "operational_errors": 0,
        "input_tokens": 220,
        "input_tokens_per_call": 110,
        "cached_input_tokens": 20,
        "cache_write_input_tokens": 0,
        "output_tokens": 12,
        "reasoning_output_tokens": 5,
        "transport_fallback_calls": 1,
    }
