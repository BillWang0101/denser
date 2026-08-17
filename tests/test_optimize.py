"""Tests for multi-candidate contract-first optimization."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from denser.backends.base import Backend, BackendError
from denser.cli import main
from denser.eval import GoldenTask, TestCase
from denser.inspection import inspect
from denser.optimization import EVIDENCE_SCHEMA_VERSION, CandidateKind, optimize
from denser.tokens import TokenCountError

SOURCE = """# Trigger
Use when the user asks to deploy a release.

# Hard constraints
- MUST ask for approval before writing to production.
- NEVER print secrets or API tokens.

# Output
Return exactly `status=ready`.

# Background
Background explanation that can be removed safely.
Another line of non-binding historical commentary.
"""

SHORTER_PASSING = """# Trigger
Use when the user asks to deploy a release.
# Hard constraints
- MUST ask for approval before writing to production.
- NEVER print secrets or API tokens.
# Output
Return exactly `status=ready`.
"""


def _response(text: str) -> str:
    return f"=== COMPRESSED ===\n{text}\n=== RATIONALE ===\n- Removed non-binding prose.\n"


class _SequenceBackend(Backend):
    def __init__(self, responses: list[str | Exception]) -> None:
        self.responses = responses
        self.calls = 0

    def complete(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
        response = self.responses[self.calls]
        self.calls += 1
        if isinstance(response, Exception):
            raise response
        return response

    @property
    def name(self) -> str:
        return "sequence"

    @property
    def supports_caching(self) -> bool:
        return False


class _WordCounter:
    method = "word-count-test"
    provider = "test-provider"
    model = "test-model"
    exact = True

    def __init__(self, *, fail_after: int | None = None) -> None:
        self.calls = 0
        self.fail_after = fail_after

    def count(self, text: str) -> int:
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise TokenCountError("provider failure")
        return len(text.split())


class TestOptimize:
    def test_short_source_keeps_original_without_model_calls(self) -> None:
        backend = _SequenceBackend([_response("unused")])
        report = optimize(
            "MUST keep this.",
            task_type="skill",
            backend=backend,
            target_densities=(0.5,),
        )
        assert report.recommended.kind == CandidateKind.ORIGINAL
        assert report.logical_generation_calls == 0
        assert backend.calls == 0

    def test_selects_shortest_passing_candidate(self) -> None:
        missing_literal = SHORTER_PASSING.replace("`status=ready`", "a status")
        backend = _SequenceBackend([_response(SHORTER_PASSING), _response(missing_literal)])
        report = optimize(
            SOURCE,
            task_type="skill",
            backend=backend,
            target_densities=(0.5, 0.7),
            min_tokens=1,
        )
        assert report.recommended_candidate_id == "candidate-001"
        assert report.changed
        assert report.candidates[1].eligible
        assert not report.candidates[2].eligible

    def test_malformed_response_is_recorded_and_other_candidates_continue(self) -> None:
        backend = _SequenceBackend(["malformed", _response(SHORTER_PASSING)])
        report = optimize(
            SOURCE,
            task_type="skill",
            backend=backend,
            target_densities=(0.4, 0.6),
            min_tokens=1,
        )
        assert report.candidates[1].generation_error == "ValueError"
        assert report.candidates[2].eligible
        assert report.recommended_candidate_id == "candidate-002"

    def test_backend_error_is_recorded_without_message(self) -> None:
        backend = _SequenceBackend([BackendError("secret-bearing upstream detail")])
        report = optimize(
            SOURCE,
            task_type="skill",
            backend=backend,
            target_densities=(0.5,),
            min_tokens=1,
        )
        candidate = report.candidates[1]
        assert candidate.generation_error == "BackendError"
        assert "secret-bearing" not in json.dumps(report.to_dict())
        assert report.recommended.kind == CandidateKind.ORIGINAL

    def test_behavior_baseline_is_reused_across_candidates(self) -> None:
        inspection = inspect(SOURCE, task_type="skill", min_tokens=1)
        approval = next(item for item in inspection.contract.items if "approval" in item.statement)
        task = GoldenTask(
            task_type=inspection.task_type,
            name="approval_behavior",
            description="",
            task_prompt="Check {input}",
            test_cases=(TestCase(name="approval", vars={}, expected="yes"),),
            covers=(approval.item_id,),
        )
        changed = SHORTER_PASSING.replace(
            "MUST ask for approval before writing to production.",
            "Get confirmation before a production write.",
        )
        generator = _SequenceBackend([_response(changed), _response(changed)])
        judge = _SequenceBackend(["yes", "yes", "yes"])

        report = optimize(
            SOURCE,
            task_type="skill",
            backend=generator,
            target_densities=(0.4, 0.6),
            behavior_tasks=[task],
            judge_backend=judge,
            min_tokens=1,
        )

        assert report.logical_judge_calls == 3
        assert judge.calls == 3
        assert report.recommended.kind == CandidateKind.GENERATED

    def test_unreliable_baseline_stops_before_generation(self) -> None:
        inspection = inspect(SOURCE, task_type="skill", min_tokens=1)
        task = GoldenTask(
            task_type=inspection.task_type,
            name="behavior",
            description="",
            task_prompt="Check {input}",
            test_cases=(TestCase(name="case", vars={}, expected="yes"),),
        )
        generator = _SequenceBackend([_response(SHORTER_PASSING)])
        judge = _SequenceBackend([BackendError("offline")])

        report = optimize(
            SOURCE,
            task_type="skill",
            backend=generator,
            behavior_tasks=[task],
            judge_backend=judge,
            target_densities=(0.5,),
            min_tokens=1,
        )

        assert generator.calls == 0
        assert report.logical_generation_calls == 0
        assert report.recommended.kind == CandidateKind.ORIGINAL

    def test_invalid_density_raises(self) -> None:
        with pytest.raises(ValueError, match="target_densities"):
            optimize(SOURCE, task_type="skill", target_densities=(0.0,), min_tokens=1)

    def test_evidence_report_is_versioned_and_serializable(self) -> None:
        backend = _SequenceBackend([_response(SHORTER_PASSING)])
        report = optimize(
            SOURCE,
            task_type="skill",
            backend=backend,
            target_densities=(0.5,),
            min_tokens=1,
            source_name="SKILL.md",
        )
        data = report.to_dict()
        json.dumps(data)
        assert data["schema_version"] == EVIDENCE_SCHEMA_VERSION
        assert data["source_name"] == "SKILL.md"
        assert len(data["source_sha256"]) == 64
        redacted = report.to_dict(include_text=False)
        assert all("text" not in candidate for candidate in redacted["candidates"])

    def test_records_explicit_token_count_method(self) -> None:
        backend = _SequenceBackend([_response(SHORTER_PASSING)])
        counter = _WordCounter()
        report = optimize(
            SOURCE,
            task_type="skill",
            backend=backend,
            token_counter=counter,
            target_densities=(0.5,),
            min_tokens=1,
        )
        assert report.token_count_method == "word-count-test"
        assert report.token_count_provider == "test-provider"
        assert report.token_count_exact
        assert report.logical_token_count_calls == 2
        assert counter.calls == 2

    def test_counting_failure_makes_candidate_ineligible(self) -> None:
        backend = _SequenceBackend([_response(SHORTER_PASSING)])
        report = optimize(
            SOURCE,
            task_type="skill",
            backend=backend,
            token_counter=_WordCounter(fail_after=1),
            target_densities=(0.5,),
            min_tokens=1,
        )
        assert report.candidates[1].measurement_error == "TokenCountError"
        assert not report.candidates[1].eligible
        assert report.recommended.kind == CandidateKind.ORIGINAL


class TestOptimizeCli:
    def test_short_source_does_not_require_backend_credentials(self, tmp_path, monkeypatch) -> None:
        source = tmp_path / "short.md"
        source.write_text("MUST keep this.", encoding="utf-8")
        called = False

        def build_backend(*args, **kwargs):
            nonlocal called
            called = True
            raise AssertionError("backend must not be created")

        monkeypatch.setattr("denser.cli._build_backend", build_backend)
        result = CliRunner().invoke(main, ["optimize", str(source), "--type", "skill"])

        assert result.exit_code == 0, result.output
        assert "Recommended" in result.output
        assert not called

    def test_writes_recommendation_and_evidence_without_overwriting(
        self, tmp_path, monkeypatch
    ) -> None:
        source = tmp_path / "SKILL.md"
        output = tmp_path / "SKILL.optimized.md"
        evidence = tmp_path / "evidence.json"
        source.write_text(SOURCE, encoding="utf-8")
        backend = _SequenceBackend([_response(SHORTER_PASSING)])
        monkeypatch.setattr("denser.cli._build_backend", lambda *args, **kwargs: backend)

        result = CliRunner().invoke(
            main,
            [
                "optimize",
                str(source),
                "--type",
                "skill",
                "--densities",
                "0.5",
                "--min-tokens",
                "1",
                "--out",
                str(output),
                "--evidence-out",
                str(evidence),
            ],
        )

        assert result.exit_code == 0, result.output
        assert output.read_text(encoding="utf-8") == SHORTER_PASSING.strip()
        assert json.loads(evidence.read_text(encoding="utf-8"))["changed"] is True
        assert source.read_text(encoding="utf-8") == SOURCE

    def test_refuses_source_overwrite_before_backend_creation(self, tmp_path, monkeypatch) -> None:
        source = tmp_path / "SKILL.md"
        source.write_text(SOURCE, encoding="utf-8")
        called = False

        def build_backend(*args, **kwargs):
            nonlocal called
            called = True
            return _SequenceBackend([_response(SHORTER_PASSING)])

        monkeypatch.setattr("denser.cli._build_backend", build_backend)
        result = CliRunner().invoke(
            main,
            ["optimize", str(source), "--type", "skill", "--out", str(source)],
        )

        assert result.exit_code != 0
        assert "Refusing to overwrite the source" in result.output
        assert not called
