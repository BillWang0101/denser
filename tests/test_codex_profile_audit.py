"""Tests for the reproducible Codex capability-profile benchmark."""

from __future__ import annotations

from pathlib import Path

from benchmarks.codex_profile_audit import SCENARIO_SETS, _sha256, _summarize
from denser.replay import load_replay_suite


def test_source_hash_is_stable_across_line_endings(tmp_path: Path) -> None:
    lf = tmp_path / "lf.txt"
    crlf = tmp_path / "crlf.txt"
    lf.write_bytes(b"one\ntwo\n")
    crlf.write_bytes(b"one\r\ntwo\r\n")

    assert _sha256(lf) == _sha256(crlf)


def test_uv_public_pilot_has_fourteen_preregistered_cases() -> None:
    scenarios = SCENARIO_SETS["uv-public-pilot"]
    assert [scenario.name for scenario in scenarios] == [
        "uv_issue_triage_snapshot",
        "uv_workflow_failure_snapshot",
    ]
    case_counts = [
        sum(len(task.cases) for task in load_replay_suite(scenario.suite).tasks)
        for scenario in scenarios
    ]
    assert case_counts == [8, 6]
    for scenario in scenarios:
        asset = scenario.asset.read_text(encoding="utf-8")
        assert "5cc226096ea4424d021be17259bae51d761a827b" in asset
        assert "decision-only projection" in asset


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
