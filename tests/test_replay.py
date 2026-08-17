"""Tests for deterministic behavior replay."""

from __future__ import annotations

import hashlib
import json

import pytest
from click.testing import CliRunner

from denser.backends.base import Backend
from denser.cli import main
from denser.replay import (
    MatchMode,
    ReplayCase,
    ReplayCategory,
    ReplayProgress,
    ReplaySuiteRole,
    ReplayTask,
    compare_replay,
    load_replay_suite,
    load_replay_tasks,
    replay,
)
from denser.taxonomy import TaskType


class _RoutingBackend(Backend):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def complete(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
        self.calls.append((system, user))
        if "BROKEN" in system:
            return "ALLOW"
        if "production" in user:
            return "ASK_APPROVAL"
        return "ALLOW"

    @property
    def name(self) -> str:
        return "routing"

    @property
    def supports_caching(self) -> bool:
        return False


class _ConfiguredRoutingBackend(_RoutingBackend):
    @property
    def runtime_config(self) -> dict[str, object]:
        return {
            "backend_kind": "fake",
            "model": "routing-v1",
            "timeout_seconds": 12,
            "ephemeral": True,
            "capability_profile": "text-only",
            "disabled_features": ("apps",),
            "api_key": "must-not-be-recorded",
            "executable": "C:/Users/private/tool.exe",
        }


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
        covers=("C001",),
    )


class TestReplayCase:
    def test_exact_match_ignores_outer_whitespace(self) -> None:
        case = ReplayCase(
            name="exact",
            prompt="prompt",
            expected="ALLOW",
            category=ReplayCategory.POSITIVE_TRIGGER,
        )
        assert case.matches("  ALLOW\n")
        assert not case.matches("ALLOW now")

    def test_accepts_alternatives_and_rejects_forbidden_text(self) -> None:
        case = ReplayCase(
            name="alternatives",
            prompt="prompt",
            expected=("REFUSE", "BLOCK"),
            category=ReplayCategory.ADVERSARIAL,
            forbidden=("secret",),
        )
        assert case.matches("BLOCK")
        assert not case.matches("BLOCK secret")

    def test_contains_and_regex_modes(self) -> None:
        contains = ReplayCase(
            name="contains",
            prompt="prompt",
            expected="ticket=42",
            category=ReplayCategory.FAILURE_PATH,
            match_mode=MatchMode.CONTAINS,
        )
        regex = ReplayCase(
            name="regex",
            prompt="prompt",
            expected=r"status=(ok|safe)",
            category=ReplayCategory.NEAR_MISS,
            match_mode=MatchMode.REGEX,
        )
        assert contains.matches("error ticket=42 retry=false")
        assert regex.matches("status=safe")
        assert not regex.matches("prefix status=safe")

    def test_invalid_regex_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="invalid regex"):
            ReplayCase(
                name="bad",
                prompt="prompt",
                expected="[",
                category=ReplayCategory.NEAR_MISS,
                match_mode=MatchMode.REGEX,
            )


class TestReplay:
    def test_single_asset_replay(self) -> None:
        report = replay(
            "SAFE INSTRUCTIONS",
            task_type="claude_md",
            tasks=[_task()],
            backend=_RoutingBackend(),
            n_trials=2,
        )
        assert report.overall_pass_rate == 1.0
        assert report.n_cases == 2
        assert report.n_errors == 0
        assert report.n_trials == 2
        assert len(report.instruction_sha256) == 64
        assert len(report.suite_sha256) == 64
        assert report.generated_at_utc.endswith("Z")
        assert report.task_results[0].case_results[0].n_passed == 2

    def test_paired_comparison_detects_candidate_regression(self) -> None:
        backend = _RoutingBackend()
        progress: list[ReplayProgress] = []
        report = compare_replay(
            original="SAFE INSTRUCTIONS",
            candidate="BROKEN INSTRUCTIONS",
            task_type="claude_md",
            tasks=[_task()],
            backend=backend,
            n_trials=2,
            seed=7,
            on_progress=progress.append,
        )
        assert report.original.overall_pass_rate == 1.0
        assert report.candidate.overall_pass_rate == 0.5
        assert report.delta == -0.5
        assert report.original.generated_at_utc == report.candidate.generated_at_utc
        assert report.original.suite_sha256 == report.candidate.suite_sha256
        assert len(backend.calls) == 8
        assert {system for system, _prompt in backend.calls} == {
            "SAFE INSTRUCTIONS",
            "BROKEN INSTRUCTIONS",
        }
        assert [event.completed_calls for event in progress] == list(range(1, 9))
        assert {event.total_calls for event in progress} == {8}
        assert {event.side for event in progress} == {"original", "candidate"}
        assert {event.trial_index for event in progress} == {1, 2}
        assert {event.task_name for event in progress} == {"release_boundary"}
        assert {event.case_name for event in progress} == {"preview", "production"}

    def test_operational_error_is_separate_from_content_failure(self) -> None:
        class _FailingBackend(_RoutingBackend):
            def complete(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
                raise RuntimeError("service unavailable")

        report = replay(
            "SAFE INSTRUCTIONS",
            task_type="claude_md",
            tasks=[_task()],
            backend=_FailingBackend(),
        )
        assert report.overall_pass_rate == 0.0
        assert report.n_errors == 2
        assert report.task_results[0].case_results[0].errors == ("RuntimeError",)

    def test_validation_rejects_mismatched_type_and_trials(self) -> None:
        with pytest.raises(ValueError, match="expected 'skill'"):
            replay(
                "text",
                task_type="skill",
                tasks=[_task()],
                backend=_RoutingBackend(),
            )
        with pytest.raises(ValueError, match="n_trials"):
            replay(
                "text",
                task_type="claude_md",
                tasks=[_task()],
                backend=_RoutingBackend(),
                n_trials=0,
            )

    def test_empty_task_list_returns_empty_report(self) -> None:
        report = replay(
            "text",
            task_type="claude_md",
            tasks=[],
            backend=_RoutingBackend(),
        )
        assert report.n_tasks == 0
        assert report.overall_pass_rate == 0.0


class TestLoadReplayTasks:
    def test_loads_json_suite_and_serializes_report(self, tmp_path) -> None:
        path = tmp_path / "suite.json"
        path.write_text(
            json.dumps(
                {
                    "task_type": "claude_md",
                    "name": "release_boundary",
                    "description": "",
                    "covers": ["C001"],
                    "cases": [
                        {
                            "name": "preview",
                            "prompt": "Preview the release.",
                            "expected": "ALLOW",
                            "category": "positive_trigger",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        tasks = load_replay_tasks(path)
        report = replay(
            "SAFE INSTRUCTIONS",
            task_type="claude_md",
            tasks=tasks,
            backend=_RoutingBackend(),
        )
        assert tasks[0].covers == ("C001",)
        assert report.to_dict()["schema_version"] == "denser.replay-report/v4"
        assert report.to_dict()["backend_name"] == "routing"
        assert report.to_dict()["runtime_config"] == {}
        assert report.to_dict()["usage_totals"]["input_tokens"] == 0

    def test_report_and_comparison_include_sanitized_runtime_config(self) -> None:
        backend = _ConfiguredRoutingBackend()
        report = replay(
            "SAFE INSTRUCTIONS",
            task_type="claude_md",
            tasks=[_task()],
            backend=backend,
        )
        expected = {
            "backend_kind": "fake",
            "model": "routing-v1",
            "timeout_seconds": 12,
            "ephemeral": True,
            "capability_profile": "text-only",
            "disabled_features": ["apps"],
        }
        assert report.to_dict()["runtime_config"] == expected

        comparison = compare_replay(
            original="SAFE INSTRUCTIONS",
            candidate="BROKEN INSTRUCTIONS",
            task_type="claude_md",
            tasks=[_task()],
            backend=backend,
        )
        data = comparison.to_dict()
        assert data["runtime_config"] == expected
        assert data["original"]["runtime_config"] == expected
        assert data["candidate"]["runtime_config"] == expected
        assert "api_key" not in json.dumps(data)
        assert "C:/Users/private" not in json.dumps(data)

    def test_invalid_suite_has_actionable_error(self, tmp_path) -> None:
        path = tmp_path / "suite.json"
        path.write_text("[]", encoding="utf-8")
        with pytest.raises(ValueError, match="must contain"):
            load_replay_tasks(path)

    def test_rejects_unknown_versioned_suite_schema(self, tmp_path) -> None:
        path = tmp_path / "suite.json"
        path.write_text(
            json.dumps({"schema_version": "denser.replay-suite/v99", "tasks": []}),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="Unsupported replay suite schema"):
            load_replay_tasks(path)

    def test_rejects_string_instead_of_covers_list(self, tmp_path) -> None:
        path = tmp_path / "suite.json"
        path.write_text(
            json.dumps(
                {
                    "task_type": "claude_md",
                    "name": "bad",
                    "cases": [
                        {
                            "name": "case",
                            "prompt": "prompt",
                            "expected": "answer",
                            "category": "positive_trigger",
                        }
                    ],
                    "covers": "C001",
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="covers must be a list"):
            load_replay_tasks(path)

    def test_holdout_suite_binds_frozen_assets_and_reports_provenance(self, tmp_path) -> None:
        original = "SAFE INSTRUCTIONS\n"
        candidate = "SAFE DENSE\n"
        path = tmp_path / "holdout.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": "denser.replay-suite/v2",
                    "suite_role": "holdout",
                    "freeze": {
                        "original_sha256": hashlib.sha256(original.encode()).hexdigest(),
                        "candidate_sha256": hashlib.sha256(candidate.encode()).hexdigest(),
                        "candidate_commit": "a" * 40,
                        "frozen_at_utc": "2026-08-17T05:44:42Z",
                    },
                    "authoring": {
                        "method": "independent_process",
                        "authored_at_utc": "2026-08-17T05:48:00Z",
                        "candidate_visible": False,
                        "backend": "codex-cli",
                        "model": "test-model",
                        "reasoning_effort": "medium",
                        "cli_version": "0.147.0",
                    },
                    "tasks": [_task().to_dict()],
                }
            ),
            encoding="utf-8",
        )

        suite = load_replay_suite(path)
        report = compare_replay(
            original=original.replace("\n", "\r\n"),
            candidate=candidate.replace("\n", "\r\n"),
            task_type="claude_md",
            tasks=suite,
            backend=_RoutingBackend(),
        )

        assert suite.role == ReplaySuiteRole.HOLDOUT
        assert report.to_dict()["schema_version"] == "denser.replay-report/v4"
        assert report.to_dict()["suite_metadata"]["role"] == "holdout"
        assert report.to_dict()["suite_metadata"]["freeze"]["candidate_commit"] == "a" * 40

    def test_holdout_suite_rejects_a_changed_candidate_before_execution(self, tmp_path) -> None:
        original = "SAFE INSTRUCTIONS"
        candidate = "SAFE DENSE"
        path = tmp_path / "holdout.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": "denser.replay-suite/v2",
                    "suite_role": "holdout",
                    "freeze": {
                        "original_sha256": hashlib.sha256(original.encode()).hexdigest(),
                        "candidate_sha256": hashlib.sha256(candidate.encode()).hexdigest(),
                        "candidate_commit": "b" * 40,
                        "frozen_at_utc": "2026-08-17T05:44:42Z",
                    },
                    "authoring": {
                        "method": "independent_process",
                        "authored_at_utc": "2026-08-17T05:48:00Z",
                        "candidate_visible": False,
                        "backend": "codex-cli",
                        "model": "test-model",
                        "reasoning_effort": "medium",
                        "cli_version": None,
                    },
                    "tasks": [_task().to_dict()],
                }
            ),
            encoding="utf-8",
        )
        backend = _RoutingBackend()

        with pytest.raises(ValueError, match="frozen candidate"):
            compare_replay(
                original=original,
                candidate="CHANGED",
                task_type="claude_md",
                tasks=load_replay_suite(path),
                backend=backend,
            )

        assert backend.calls == []

    def test_holdout_suite_rejects_visible_candidate_claim(self, tmp_path) -> None:
        path = tmp_path / "holdout.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": "denser.replay-suite/v2",
                    "suite_role": "holdout",
                    "freeze": {
                        "original_sha256": "a" * 64,
                        "candidate_sha256": "b" * 64,
                        "candidate_commit": "c" * 40,
                        "frozen_at_utc": "2026-08-17T05:44:42Z",
                    },
                    "authoring": {
                        "method": "not_blind",
                        "authored_at_utc": "2026-08-17T05:48:00Z",
                        "candidate_visible": True,
                        "backend": "codex-cli",
                        "model": "test-model",
                        "reasoning_effort": "medium",
                    },
                    "tasks": [_task().to_dict()],
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="candidate_visible=true"):
            load_replay_suite(path)


class TestReplayCli:
    def test_help_lists_codex_cli_backend(self) -> None:
        result = CliRunner().invoke(main, ["replay", "--help"])

        assert result.exit_code == 0, result.output
        assert "codex-cli" in result.output
        assert "--openai-thinking-mode" in result.output
        assert "--codex-capability-profile" in result.output
        assert "text-only" in result.output

    def test_compares_files_and_writes_json(self, tmp_path, monkeypatch) -> None:
        original = tmp_path / "AGENTS.md"
        candidate = tmp_path / "AGENTS.dense.md"
        suite = tmp_path / "suite.json"
        output = tmp_path / "report.json"
        original.write_text("SAFE INSTRUCTIONS", encoding="utf-8")
        candidate.write_text("BROKEN INSTRUCTIONS", encoding="utf-8")
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
            lambda *args, **kwargs: _RoutingBackend(),
        )

        result = CliRunner().invoke(
            main,
            [
                "replay",
                str(original),
                "--suite",
                str(suite),
                "--type",
                "claude_md",
                "--compare-to",
                str(candidate),
                "--json-out",
                str(output),
            ],
        )

        assert result.exit_code == 2, result.output
        assert "Replay progress 1/2" in result.output
        assert "Replay progress 2/2" in result.output
        assert "original vs. candidate" in result.output
        data = json.loads(output.read_text(encoding="utf-8"))
        assert data["delta"] == -1.0
