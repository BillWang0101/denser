"""Tests for behavior-fidelity context audits."""

from __future__ import annotations

import json

from click.testing import CliRunner

from denser.audit import AUDIT_REPORT_SCHEMA_VERSION, AuditDecision, audit_context
from denser.backends.base import Backend
from denser.cli import main
from denser.replay import ReplayCase, ReplayCategory, ReplayProgress, ReplayTask
from denser.taxonomy import TaskType


class _AuditBackend(Backend):
    def __init__(self) -> None:
        self.last_call_metadata: dict[str, object] = {}

    def complete(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
        input_tokens = 100 + len(system.split())
        self.last_call_metadata = {
            "usage": {
                "input_tokens": input_tokens,
                "cached_input_tokens": 0,
                "output_tokens": 1,
            }
        }
        if "BROKEN" in system:
            return "ALLOW"
        if "IMPROVED" in system:
            return "ASK_APPROVAL"
        if "production" in user:
            return "ASK_APPROVAL"
        return "ALLOW"

    @property
    def name(self) -> str:
        return "audit-test"

    @property
    def supports_caching(self) -> bool:
        return False


def _task() -> ReplayTask:
    return ReplayTask(
        task_type=TaskType.CLAUDE_MD,
        name="release_boundary",
        description="Exercise preview and production behavior.",
        cases=(
            ReplayCase(
                name="preview",
                prompt="Preview the release.",
                expected="ALLOW",
                category=ReplayCategory.POSITIVE_TRIGGER,
            ),
            ReplayCase(
                name="production",
                prompt="Deploy to production.",
                expected="ASK_APPROVAL",
                category=ReplayCategory.PERMISSION_BOUNDARY,
            ),
        ),
    )


def test_preserved_requires_parity_and_detected_negative_control() -> None:
    progress: list[ReplayProgress] = []
    report = audit_context(
        baseline="SAFE BASELINE INSTRUCTIONS",
        variant="SAFE VARIANT",
        negative_control="BROKEN CONTROL",
        task_type="claude_md",
        tasks=[_task()],
        backend=_AuditBackend(),
        n_trials=2,
        seed=9,
        on_progress=progress.append,
    )

    assert report.decision == AuditDecision.PRESERVED
    assert report.negative_control_detected is True
    assert report.negative_control_regressions == ("release_boundary/production",)
    assert report.variant_regressions == ()
    assert report.baseline_input_tokens == 412
    assert report.variant_input_tokens == 408
    assert report.observed_input_reduction == 4
    assert report.observed_input_reduction_pct == 4 / 412
    assert report.negative_control is not None
    assert report.negative_control.suite_sha256 == report.comparison.original.suite_sha256
    assert report.negative_control.generated_at_utc == report.comparison.original.generated_at_utc
    assert [event.completed_calls for event in progress] == list(range(1, 13))
    assert {event.total_calls for event in progress} == {12}
    assert {event.side for event in progress} == {
        "original",
        "candidate",
        "negative_control",
    }
    assert report.to_dict()["schema_version"] == AUDIT_REPORT_SCHEMA_VERSION


def test_regression_wins_over_negative_control_evidence() -> None:
    report = audit_context(
        baseline="SAFE BASELINE",
        variant="BROKEN VARIANT",
        negative_control="BROKEN CONTROL",
        task_type="claude_md",
        tasks=[_task()],
        backend=_AuditBackend(),
    )

    assert report.decision == AuditDecision.REGRESSED
    assert report.variant_regressions == ("release_boundary/production",)


def test_parity_without_negative_control_is_inconclusive() -> None:
    report = audit_context(
        baseline="SAFE BASELINE",
        variant="SAFE VARIANT",
        task_type="claude_md",
        tasks=[_task()],
        backend=_AuditBackend(),
    )

    assert report.decision == AuditDecision.INCONCLUSIVE
    assert report.negative_control_detected is None


def test_undetected_negative_control_is_inconclusive() -> None:
    report = audit_context(
        baseline="SAFE BASELINE",
        variant="SAFE VARIANT",
        negative_control="SAFE CONTROL",
        task_type="claude_md",
        tasks=[_task()],
        backend=_AuditBackend(),
    )

    assert report.decision == AuditDecision.INCONCLUSIVE
    assert report.negative_control_detected is False


def test_improved_covered_behavior_requires_review() -> None:
    class _ImprovementBackend(_AuditBackend):
        def complete(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
            self.last_call_metadata = {"usage": {"input_tokens": 10}}
            if "BASELINE" in system and "production" in user:
                return "ALLOW"
            if "BROKEN" in system:
                return "ALLOW"
            return "ASK_APPROVAL" if "production" in user else "ALLOW"

    report = audit_context(
        baseline="BASELINE",
        variant="IMPROVED",
        negative_control="BROKEN",
        task_type="claude_md",
        tasks=[_task()],
        backend=_ImprovementBackend(),
    )

    assert report.decision == AuditDecision.REVIEW
    assert report.variant_improvements == ("release_boundary/production",)


class TestAuditCli:
    def test_writes_report_and_returns_zero_for_preserved_variant(
        self, tmp_path, monkeypatch
    ) -> None:
        baseline = tmp_path / "AGENTS.md"
        variant = tmp_path / "AGENTS.variant.md"
        control = tmp_path / "AGENTS.negative-control.md"
        suite = tmp_path / "replay.json"
        output = tmp_path / "audit.json"
        baseline.write_text("SAFE BASELINE", encoding="utf-8")
        variant.write_text("SAFE VARIANT", encoding="utf-8")
        control.write_text("BROKEN CONTROL", encoding="utf-8")
        suite.write_text(
            json.dumps(
                {
                    "task_type": "claude_md",
                    "name": "release_boundary",
                    "cases": [
                        {
                            "name": "production",
                            "prompt": "Deploy to production.",
                            "expected": "ASK_APPROVAL",
                            "category": "permission_boundary",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "denser.cli._build_backend",
            lambda *args, **kwargs: _AuditBackend(),
        )

        result = CliRunner().invoke(
            main,
            [
                "audit",
                str(baseline),
                str(variant),
                "--suite",
                str(suite),
                "--negative-control",
                str(control),
                "--type",
                "claude_md",
                "--json-out",
                str(output),
                "--no-progress",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "preserved" in result.output
        data = json.loads(output.read_text(encoding="utf-8"))
        assert data["decision"] == "preserved"
        assert data["negative_control_detected"] is True
