"""Tests for the eval harness."""

from __future__ import annotations

import json

import pytest

from denser.backends.base import Backend
from denser.eval import (
    GoldenTask,
    TestCase,
    _normalize_judge_output,
    compare,
    evaluate,
    load_golden_tasks,
)
from denser.taxonomy import TaskType


class _ScriptedJudge(Backend):
    """Judge that returns pre-scripted responses, cycling through the list."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self._idx = 0
        self.calls: list[tuple[str, str]] = []

    def complete(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
        self.calls.append((system, user))
        resp = self._responses[self._idx % len(self._responses)]
        self._idx += 1
        return resp

    @property
    def name(self) -> str:
        return "scripted"

    @property
    def supports_caching(self) -> bool:
        return False


class TestNormalizeJudgeOutput:
    def test_yes_variants(self) -> None:
        assert _normalize_judge_output("yes") == "yes"
        assert _normalize_judge_output("Yes") == "yes"
        assert _normalize_judge_output("YES.") == "yes"
        assert _normalize_judge_output("  yes  ") == "yes"
        assert _normalize_judge_output("yes, because the skill mentions...") == "yes"

    def test_no_variants(self) -> None:
        assert _normalize_judge_output("no") == "no"
        assert _normalize_judge_output("No.") == "no"
        assert _normalize_judge_output("no it doesn't") == "no"

    def test_non_yesno(self) -> None:
        assert _normalize_judge_output("call_tool") == "call tool"
        assert _normalize_judge_output("option A") == "option a"

    def test_empty(self) -> None:
        assert _normalize_judge_output("") == ""
        assert _normalize_judge_output(None) == ""  # type: ignore[arg-type]


class TestTestCase:
    def test_matches_exact(self) -> None:
        case = TestCase(name="t", vars={}, expected="yes")
        assert case.matches("yes")
        assert case.matches("Yes.")
        assert not case.matches("no")

    def test_matches_list(self) -> None:
        case = TestCase(name="t", vars={}, expected=["yes", "correct"])
        assert case.matches("yes")
        assert case.matches("CORRECT")
        assert not case.matches("maybe")


class TestLoadGoldenTasks:
    def test_load_skill_fixtures(self) -> None:
        tasks = load_golden_tasks(TaskType.SKILL)
        assert len(tasks) >= 2
        names = {t.name for t in tasks}
        assert "trigger_accuracy" in names
        assert "procedure_preservation" in names

    def test_load_via_string(self) -> None:
        tasks = load_golden_tasks("skill")
        assert all(t.task_type == TaskType.SKILL for t in tasks)

    def test_every_task_type_has_fixtures(self) -> None:
        for tt in TaskType:
            tasks = load_golden_tasks(tt)
            assert len(tasks) >= 1, f"{tt.value}: no fixtures shipped"

    def test_invalid_fixture_skipped(self, tmp_path, monkeypatch) -> None:
        # Ensure load_golden_tasks doesn't crash on malformed JSON.
        from denser import eval as eval_mod

        # Create a fake fixtures dir with a bad file
        fake_dir = tmp_path / "fixtures" / "golden" / "skill"
        fake_dir.mkdir(parents=True)
        (fake_dir / "broken.json").write_text("{not valid json}")
        (fake_dir / "good.json").write_text(
            json.dumps(
                {
                    "task_type": "skill",
                    "name": "good",
                    "description": "",
                    "task_prompt": "prompt {input}",
                    "test_cases": [{"name": "c", "vars": {}, "expected": "yes"}],
                    "pass_threshold": 0.9,
                }
            )
        )

        def fake_dir_fn():
            return tmp_path / "fixtures" / "golden"

        monkeypatch.setattr(eval_mod, "_fixtures_dir", fake_dir_fn)
        tasks = load_golden_tasks("skill")
        # The bad file is skipped with a warning; the good file loads.
        assert len(tasks) == 1
        assert tasks[0].name == "good"


class TestGoldenTaskFill:
    def test_fill_substitutes_input(self) -> None:
        gt = GoldenTask(
            task_type=TaskType.SKILL,
            name="t",
            description="",
            task_prompt="Skill: {input}. Request: {request}.",
            test_cases=(TestCase(name="c", vars={"request": "do X"}, expected="yes"),),
        )
        filled = gt.fill("my skill", gt.test_cases[0])
        assert "Skill: my skill" in filled
        assert "Request: do X" in filled

    def test_fill_requires_input_placeholder(self) -> None:
        gt = GoldenTask(
            task_type=TaskType.SKILL,
            name="t",
            description="",
            task_prompt="no placeholder here",
            test_cases=(TestCase(name="c", vars={}, expected="yes"),),
        )
        with pytest.raises(ValueError, match="task_prompt must contain"):
            gt.fill("text", gt.test_cases[0])


class TestEvaluate:
    def test_empty_text_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            evaluate("", task_type="skill", judge_backend=_ScriptedJudge(["yes"]))

    def test_invalid_n_trials(self) -> None:
        with pytest.raises(ValueError, match="n_trials"):
            evaluate("text", task_type="skill", n_trials=0, judge_backend=_ScriptedJudge(["yes"]))

    def test_no_tasks_returns_empty_report(self) -> None:
        report = evaluate(
            "some skill text",
            task_type="skill",
            golden_tasks=[],
            judge_backend=_ScriptedJudge(["yes"]),
        )
        assert report.n_tasks == 0
        assert report.overall_pass_rate == 0.0

    def test_single_task_all_pass(self) -> None:
        task = GoldenTask(
            task_type=TaskType.SKILL,
            name="t",
            description="",
            task_prompt="Check {input}",
            test_cases=(
                TestCase(name="c1", vars={}, expected="yes"),
                TestCase(name="c2", vars={}, expected="yes"),
            ),
        )
        judge = _ScriptedJudge(["yes", "yes"])
        report = evaluate(
            "skill text",
            task_type="skill",
            golden_tasks=[task],
            judge_backend=judge,
        )
        assert report.overall_pass_rate == 1.0
        assert report.n_cases == 2

    def test_mixed_pass_fail(self) -> None:
        task = GoldenTask(
            task_type=TaskType.SKILL,
            name="t",
            description="",
            task_prompt="Check {input}",
            test_cases=(
                TestCase(name="c1", vars={}, expected="yes"),
                TestCase(name="c2", vars={}, expected="yes"),
            ),
        )
        judge = _ScriptedJudge(["yes", "no"])
        report = evaluate(
            "skill text",
            task_type="skill",
            golden_tasks=[task],
            judge_backend=judge,
        )
        assert report.overall_pass_rate == 0.5

    def test_multi_trial_averages(self) -> None:
        task = GoldenTask(
            task_type=TaskType.SKILL,
            name="t",
            description="",
            task_prompt="Check {input}",
            test_cases=(TestCase(name="c", vars={}, expected="yes"),),
        )
        judge = _ScriptedJudge(["yes", "no", "yes", "yes"])
        report = evaluate(
            "skill text",
            task_type="skill",
            golden_tasks=[task],
            judge_backend=judge,
            n_trials=4,
        )
        cr = report.task_results[0].case_results[0]
        assert cr.n_passed == 3
        assert cr.pass_rate == 0.75

    def test_judge_exception_counts_as_failure(self) -> None:
        class _FailingJudge(Backend):
            @property
            def name(self) -> str:
                return "fail"

            @property
            def supports_caching(self) -> bool:
                return False

            def complete(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
                raise RuntimeError("boom")

        task = GoldenTask(
            task_type=TaskType.SKILL,
            name="t",
            description="",
            task_prompt="Check {input}",
            test_cases=(TestCase(name="c", vars={}, expected="yes"),),
        )
        report = evaluate(
            "skill text",
            task_type="skill",
            golden_tasks=[task],
            judge_backend=_FailingJudge(),
        )
        assert report.overall_pass_rate == 0.0


class TestCompare:
    def test_delta_positive(self) -> None:
        task = GoldenTask(
            task_type=TaskType.SKILL,
            name="t",
            description="",
            task_prompt="Check {input}",
            test_cases=(TestCase(name="c", vars={}, expected="yes"),),
        )
        # Original judged "no" (fail), compressed judged "yes" (pass)
        judge = _ScriptedJudge(["no", "yes"])
        report = compare(
            original="long verbose text",
            compressed="dense text",
            task_type="skill",
            golden_tasks=[task],
            judge_backend=judge,
        )
        assert report.original.overall_pass_rate == 0.0
        assert report.compressed.overall_pass_rate == 1.0
        assert report.delta == 1.0

    def test_delta_negative(self) -> None:
        task = GoldenTask(
            task_type=TaskType.SKILL,
            name="t",
            description="",
            task_prompt="Check {input}",
            test_cases=(TestCase(name="c", vars={}, expected="yes"),),
        )
        judge = _ScriptedJudge(["yes", "no"])
        report = compare(
            original="verbose",
            compressed="over-compressed",
            task_type="skill",
            golden_tasks=[task],
            judge_backend=judge,
        )
        assert report.delta == -1.0
