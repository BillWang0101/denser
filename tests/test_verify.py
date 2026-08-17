"""Tests for contract-first candidate verification."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from denser import verify
from denser.backends.base import Backend
from denser.cli import main
from denser.eval import GoldenTask, TestCase
from denser.eval import evaluate as evaluate_fn
from denser.inspection import inspect
from denser.replay import ReplayCase, ReplayCategory, ReplayTask
from denser.verification import VerificationDecision, VerificationStatus

SOURCE = """# Trigger
Use when the user asks to deploy a release.

# Hard constraints
- MUST ask for approval before writing to production.
- NEVER print secrets or API tokens.

# Output
Return exactly `release=<id> status=<state>`.
"""


class _ScriptedJudge(Backend):
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.index = 0

    def complete(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
        response = self.responses[self.index % len(self.responses)]
        self.index += 1
        return response

    @property
    def name(self) -> str:
        return "scripted"

    @property
    def supports_caching(self) -> bool:
        return False


def _task(*covers: str) -> GoldenTask:
    return GoldenTask(
        task_type=inspect(SOURCE, task_type="skill", min_tokens=1).task_type,
        name="approval_behavior",
        description="",
        task_prompt="Check {input}",
        test_cases=(TestCase(name="approval", vars={}, expected="yes"),),
        covers=covers,
    )


def _replay_task(*covers: str) -> ReplayTask:
    return ReplayTask(
        task_type=inspect(SOURCE, task_type="skill", min_tokens=1).task_type,
        name="approval_replay",
        description="",
        cases=(
            ReplayCase(
                name="production",
                prompt="Write release 42 to production.",
                expected="ASK_APPROVAL",
                category=ReplayCategory.PERMISSION_BOUNDARY,
            ),
        ),
        covers=covers,
    )


class _ApprovalBackend(_ScriptedJudge):
    def complete(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
        if "Get confirmation" in system or "MUST ask for approval" in system:
            return "ASK_APPROVAL"
        return "WRITE_NOW"


class TestVerify:
    def test_empty_original_raises(self) -> None:
        with pytest.raises(ValueError, match="empty original"):
            verify("", "candidate", task_type="skill")

    def test_unchanged_source_passes_deterministically(self) -> None:
        report = verify(SOURCE, SOURCE, task_type="skill")
        assert report.decision == VerificationDecision.PASS
        assert report.passed
        assert all(result.status == VerificationStatus.PASS for result in report.item_results)

    def test_missing_literal_rejects(self) -> None:
        candidate = SOURCE.replace("`release=<id> status=<state>`", "a short status")
        report = verify(SOURCE, candidate, task_type="skill")
        assert report.decision == VerificationDecision.REJECT
        assert "release=<id> status=<state>" in report.missing_literals

    def test_changed_uncovered_obligation_requires_review(self) -> None:
        candidate = SOURCE.replace(
            "MUST ask for approval before writing to production.",
            "Get confirmation before a production write.",
        )
        report = verify(SOURCE, candidate, task_type="skill")
        assert report.decision == VerificationDecision.REVIEW
        assert report.review_count == 1

    def test_passing_behavior_task_can_cover_changed_item(self) -> None:
        inspection = inspect(SOURCE, task_type="skill", min_tokens=1)
        approval = next(item for item in inspection.contract.items if "approval" in item.statement)
        candidate = SOURCE.replace(
            "MUST ask for approval before writing to production.",
            "Get confirmation before a production write.",
        )
        report = verify(
            SOURCE,
            candidate,
            task_type="skill",
            inspection=inspection,
            behavior_tasks=[_task(approval.item_id)],
            judge_backend=_ScriptedJudge(["yes", "yes"]),
        )
        assert report.decision == VerificationDecision.PASS
        item_result = next(
            result for result in report.item_results if result.item_id == approval.item_id
        )
        assert item_result.status == VerificationStatus.PASS
        assert "approval_behavior" in item_result.evidence[0]

    def test_behavior_regression_rejects(self) -> None:
        inspection = inspect(SOURCE, task_type="skill", min_tokens=1)
        approval = next(item for item in inspection.contract.items if "approval" in item.statement)
        candidate = SOURCE.replace(
            "MUST ask for approval before writing to production.",
            "Get confirmation before a production write.",
        )
        report = verify(
            SOURCE,
            candidate,
            task_type="skill",
            inspection=inspection,
            behavior_tasks=[_task(approval.item_id)],
            judge_backend=_ScriptedJudge(["yes", "no"]),
        )
        assert report.decision == VerificationDecision.REJECT
        assert any("failed or regressed" in failure for failure in report.failures)

    def test_judge_error_is_not_reported_as_content_success(self) -> None:
        class _FailingJudge(_ScriptedJudge):
            def complete(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
                raise RuntimeError("service unavailable")

        inspection = inspect(SOURCE, task_type="skill", min_tokens=1)
        approval = next(item for item in inspection.contract.items if "approval" in item.statement)
        candidate = SOURCE.replace(
            "MUST ask for approval before writing to production.",
            "Get confirmation before a production write.",
        )
        report = verify(
            SOURCE,
            candidate,
            task_type="skill",
            inspection=inspection,
            behavior_tasks=[_task(approval.item_id)],
            judge_backend=_FailingJudge(["yes"]),
        )
        assert report.decision == VerificationDecision.REJECT
        assert report.behavior_results[0].error_count == 2
        assert any("operational error" in failure for failure in report.failures)

    def test_passing_replay_can_cover_changed_item(self) -> None:
        inspection = inspect(SOURCE, task_type="skill", min_tokens=1)
        approval = next(item for item in inspection.contract.items if "approval" in item.statement)
        candidate = SOURCE.replace(
            "MUST ask for approval before writing to production.",
            "Get confirmation before a production write.",
        )
        report = verify(
            SOURCE,
            candidate,
            task_type="skill",
            inspection=inspection,
            replay_tasks=[_replay_task(approval.item_id)],
            execution_backend=_ApprovalBackend(["unused"]),
        )
        assert report.decision == VerificationDecision.PASS
        result = report.behavior_results[0]
        assert result.evaluation_mode == "replay"
        assert result.passed
        assert report.replay_evidence is not None
        assert report.to_dict()["replay_evidence"] is not None

    def test_replay_regression_rejects_candidate(self) -> None:
        inspection = inspect(SOURCE, task_type="skill", min_tokens=1)
        approval = next(item for item in inspection.contract.items if "approval" in item.statement)
        candidate = SOURCE.replace(
            "MUST ask for approval before writing to production.",
            "Write to production immediately.",
        )
        report = verify(
            SOURCE,
            candidate,
            task_type="skill",
            inspection=inspection,
            replay_tasks=[_replay_task(approval.item_id)],
            execution_backend=_ApprovalBackend(["unused"]),
        )
        assert report.decision == VerificationDecision.REJECT
        assert any("Replay task" in failure for failure in report.failures)

    def test_replay_requires_execution_backend(self) -> None:
        with pytest.raises(ValueError, match="execution_backend"):
            verify(
                SOURCE,
                SOURCE,
                task_type="skill",
                replay_tasks=[_replay_task()],
            )

    def test_unknown_coverage_id_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown contract items"):
            verify(
                SOURCE,
                SOURCE,
                task_type="skill",
                behavior_tasks=[_task("C999")],
                judge_backend=_ScriptedJudge(["yes", "yes"]),
            )

    def test_reuses_a_precomputed_behavior_baseline(self) -> None:
        inspection = inspect(SOURCE, task_type="skill", min_tokens=1)
        approval = next(item for item in inspection.contract.items if "approval" in item.statement)
        task = _task(approval.item_id)
        judge = _ScriptedJudge(["yes", "yes"])
        baseline = evaluate_fn(
            SOURCE,
            task_type="skill",
            golden_tasks=[task],
            judge_backend=judge,
        )
        candidate = SOURCE.replace(
            "MUST ask for approval before writing to production.",
            "Get confirmation before a production write.",
        )

        report = verify(
            SOURCE,
            candidate,
            task_type="skill",
            inspection=inspection,
            behavior_tasks=[task],
            judge_backend=judge,
            baseline_report=baseline,
        )

        assert report.passed
        assert judge.index == 2

    def test_rejects_mismatched_behavior_baseline(self) -> None:
        task = _task()
        baseline = evaluate_fn(
            SOURCE,
            task_type="skill",
            golden_tasks=[task],
            judge_backend=_ScriptedJudge(["yes"]),
            n_trials=2,
        )
        with pytest.raises(ValueError, match="trial count"):
            verify(
                SOURCE,
                SOURCE,
                task_type="skill",
                behavior_tasks=[task],
                judge_backend=_ScriptedJudge(["yes"]),
                baseline_report=baseline,
                n_trials=1,
            )

    def test_report_is_json_serializable(self) -> None:
        report = verify(SOURCE, SOURCE, task_type="skill")
        encoded = json.dumps(report.to_dict())
        assert '"decision": "pass"' in encoded


class TestVerifyCli:
    def test_unchanged_candidate_exits_zero(self, tmp_path) -> None:
        original = tmp_path / "original.md"
        candidate = tmp_path / "candidate.md"
        original.write_text(SOURCE, encoding="utf-8")
        candidate.write_text(SOURCE, encoding="utf-8")

        result = CliRunner().invoke(
            main,
            ["verify", str(original), str(candidate), "--type", "skill"],
        )

        assert result.exit_code == 0, result.output
        assert "Decision: pass" in result.output
        assert "No model or network calls" in result.output

    def test_review_exit_code_and_json_report(self, tmp_path) -> None:
        original = tmp_path / "original.md"
        candidate = tmp_path / "candidate.md"
        output = tmp_path / "verification.json"
        original.write_text(SOURCE, encoding="utf-8")
        candidate.write_text(
            SOURCE.replace(
                "MUST ask for approval before writing to production.",
                "Get confirmation before a production write.",
            ),
            encoding="utf-8",
        )

        result = CliRunner().invoke(
            main,
            [
                "verify",
                str(original),
                str(candidate),
                "--type",
                "skill",
                "--json-out",
                str(output),
            ],
        )

        assert result.exit_code == 3, result.output
        assert json.loads(output.read_text(encoding="utf-8"))["decision"] == "review"
