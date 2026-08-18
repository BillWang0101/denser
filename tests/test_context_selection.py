"""Tests for conservative context-component selection."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from denser.audit import AuditDecision
from denser.backends.base import Backend
from denser.cli import main
from denser.context_selection import (
    CONTEXT_SELECTION_SCHEMA_VERSION,
    load_context_bundle,
    minimize_context,
)
from denser.replay import (
    ReplayCase,
    ReplayCategory,
    ReplaySuite,
    ReplaySuiteAuthoring,
    ReplaySuiteFreeze,
    ReplaySuiteRole,
    ReplayTask,
    load_replay_suite,
)
from denser.taxonomy import TaskType

REPO_ROOT = Path(__file__).parents[1]


class _SelectionBackend(Backend):
    def __init__(self, *, report_usage: bool = True) -> None:
        self.last_call_metadata: dict[str, object] = {}
        self._report_usage = report_usage

    def complete(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
        del max_tokens
        self.last_call_metadata = (
            {"usage": {"input_tokens": 100 + len(system.split()), "output_tokens": 1}}
            if self._report_usage
            else {}
        )
        if "CORE_SAFETY" not in system and "production" in user:
            return "ALLOW"
        if "production" in user:
            return "ASK_APPROVAL" if "RELEASE_POLICY" in system else "ALLOW"
        return "ALLOW"

    @property
    def name(self) -> str:
        return "selection-test"

    @property
    def supports_caching(self) -> bool:
        return False


def _suite() -> ReplaySuite:
    return ReplaySuite(
        tasks=(
            ReplayTask(
                task_type=TaskType.SYSTEM_PROMPT,
                name="release",
                description="Release permission behavior.",
                cases=(
                    ReplayCase(
                        name="preview",
                        prompt="preview release",
                        expected="ALLOW",
                        category=ReplayCategory.POSITIVE_TRIGGER,
                    ),
                    ReplayCase(
                        name="production",
                        prompt="production release",
                        expected="ASK_APPROVAL",
                        category=ReplayCategory.PERMISSION_BOUNDARY,
                    ),
                ),
            ),
        )
    )


def _write_bundle(tmp_path: Path) -> Path:
    (tmp_path / "core.md").write_text("CORE_SAFETY\nReturn exact labels.", encoding="utf-8")
    (tmp_path / "release.md").write_text(
        "RELEASE_POLICY\nProduction needs approval.", encoding="utf-8"
    )
    (tmp_path / "noise.md").write_text(
        "IRRELEVANT_STYLE " * 240,
        encoding="utf-8",
    )
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "denser.context-bundle/v1",
                "name": "release-context",
                "task_type": "system_prompt",
                "negative_control_drop": ["core"],
                "components": [
                    {
                        "id": "core",
                        "kind": "system_prompt",
                        "path": "core.md",
                        "required": True,
                    },
                    {
                        "id": "release-policy",
                        "kind": "system_prompt",
                        "path": "release.md",
                    },
                    {
                        "id": "style-noise",
                        "kind": "memory_entry",
                        "path": "noise.md",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_minimize_removes_only_behaviorally_safe_components(tmp_path: Path) -> None:
    bundle = load_context_bundle(_write_bundle(tmp_path))

    selected_text, report = minimize_context(
        bundle=bundle,
        tasks=_suite(),
        backend=_SelectionBackend(),
        selection_trials=1,
        validation_trials=2,
        min_input_reduction=0.10,
    )

    assert report.removed_ids == ("style-noise",)
    assert report.selected_ids == ("core", "release-policy")
    assert "IRRELEVANT_STYLE" not in selected_text
    assert "RELEASE_POLICY" in selected_text
    attempts = {attempt.component_id: attempt for attempt in report.attempts}
    assert attempts["style-noise"].removed is True
    assert attempts["release-policy"].removed is False
    assert attempts["release-policy"].decision == AuditDecision.REGRESSED
    assert report.final_audit.decision == AuditDecision.PRESERVED
    assert report.target_met is True
    assert report.to_dict()["schema_version"] == CONTEXT_SELECTION_SCHEMA_VERSION


def test_missing_provider_usage_cannot_meet_savings_target(tmp_path: Path) -> None:
    bundle = load_context_bundle(_write_bundle(tmp_path))

    _selected, report = minimize_context(
        bundle=bundle,
        tasks=_suite(),
        backend=_SelectionBackend(report_usage=False),
        validation_trials=1,
    )

    assert report.final_audit.decision == AuditDecision.PRESERVED
    assert report.observed_input_reduction_pct is None
    assert report.target_met is False
    assert "did not report" in report.outcome_reason


def test_manifest_rejects_component_path_outside_bundle(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.md"
    outside.write_text("do not load", encoding="utf-8")
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "denser.context-bundle/v1",
                "name": "unsafe",
                "task_type": "system_prompt",
                "negative_control_drop": ["core"],
                "components": [
                    {
                        "id": "core",
                        "kind": "system_prompt",
                        "path": "../outside.md",
                        "required": True,
                    },
                    {
                        "id": "optional",
                        "kind": "memory_entry",
                        "path": "optional.md",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "optional.md").write_text("optional", encoding="utf-8")

    with pytest.raises(ValueError, match="stay inside"):
        load_context_bundle(manifest)


def test_minimize_rejects_holdout_suite(tmp_path: Path) -> None:
    bundle = load_context_bundle(_write_bundle(tmp_path))
    holdout = ReplaySuite(
        tasks=_suite().tasks,
        role=ReplaySuiteRole.HOLDOUT,
        freeze=ReplaySuiteFreeze(
            original_sha256="a" * 64,
            candidate_sha256="b" * 64,
            candidate_commit="c" * 40,
            frozen_at_utc="2026-08-18T00:00:00Z",
        ),
        authoring=ReplaySuiteAuthoring(
            method="blind",
            authored_at_utc="2026-08-18T00:00:00Z",
            candidate_visible=False,
            backend="test",
            model="test",
            reasoning_effort="medium",
        ),
    )

    with pytest.raises(ValueError, match="development replay suite"):
        minimize_context(bundle=bundle, tasks=holdout, backend=_SelectionBackend())


def test_cli_writes_selected_context_and_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _write_bundle(tmp_path)
    suite = tmp_path / "suite.json"
    suite.write_text(json.dumps(_suite().to_dict()), encoding="utf-8")
    selected = tmp_path / "selected.md"
    evidence = tmp_path / "selection.json"
    monkeypatch.setattr(
        "denser.cli._build_backend",
        lambda *args, **kwargs: _SelectionBackend(),
    )

    result = CliRunner().invoke(
        main,
        [
            "minimize-context",
            str(manifest),
            "--suite",
            str(suite),
            "--validation-trials",
            "1",
            "--out",
            str(selected),
            "--json-out",
            str(evidence),
            "--no-progress",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Target met: true" in result.output
    assert "IRRELEVANT_STYLE" not in selected.read_text(encoding="utf-8")
    data = json.loads(evidence.read_text(encoding="utf-8"))
    assert data["target_met"] is True
    assert data["components"]["removed"] == ["style-noise"]


def test_cli_does_not_write_context_when_final_audit_is_inconclusive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _FinalFailureBackend(_SelectionBackend):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def complete(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
            self.calls += 1
            if self.calls > 12:
                raise RuntimeError("simulated final validation outage")
            return super().complete(system=system, user=user, max_tokens=max_tokens)

    manifest = _write_bundle(tmp_path)
    suite = tmp_path / "suite.json"
    suite.write_text(json.dumps(_suite().to_dict()), encoding="utf-8")
    selected = tmp_path / "selected.md"
    evidence = tmp_path / "selection.json"
    monkeypatch.setattr(
        "denser.cli._build_backend",
        lambda *args, **kwargs: _FinalFailureBackend(),
    )

    result = CliRunner().invoke(
        main,
        [
            "minimize-context",
            str(manifest),
            "--suite",
            str(suite),
            "--validation-trials",
            "1",
            "--out",
            str(selected),
            "--json-out",
            str(evidence),
            "--no-progress",
        ],
    )

    assert result.exit_code == 3, result.output
    assert not selected.exists()
    assert evidence.exists()
    assert "Did not write selected context" in result.output
    data = json.loads(evidence.read_text(encoding="utf-8"))
    assert data["final_audit"]["decision"] == "inconclusive"


def test_committed_tool_workflow_evidence_is_bound_and_clears_gate() -> None:
    example = REPO_ROOT / "examples" / "context_bundles" / "tool_workflows"
    bundle = load_context_bundle(example / "bundle.json")
    selected = (example / "selected.codex-standard.2026-08-18.md").read_text(encoding="utf-8")
    report = json.loads(
        (example / "selection.codex-standard.3x.2026-08-18.json").read_text(encoding="utf-8")
    )
    suite = load_replay_suite(example / "replay.json")

    assert report["schema_version"] == CONTEXT_SELECTION_SCHEMA_VERSION
    assert report["target_met"] is True
    assert report["parallelism"] == 6
    assert report["components"]["removed"] == ["archived-handbook"]
    assert report["components"]["selected"] == [
        "execution-contract",
        "release-policy",
        "ci-policy",
    ]
    assert (
        report["baseline_sha256"]
        == hashlib.sha256(bundle.baseline_text.encode("utf-8")).hexdigest()
    )
    assert report["selected_sha256"] == hashlib.sha256(selected.encode("utf-8")).hexdigest()
    prompts = "\n".join(case.prompt for task in suite.tasks for case in task.cases)
    for identifier in ("rel-7Q4M", "ci-9K2P"):
        assert identifier not in bundle.baseline_text
        assert identifier not in prompts

    final = report["final_audit"]
    assert final["decision"] == "preserved"
    assert final["negative_control_detected"] is True
    assert final["measurements"]["observed_input_reduction_pct"] >= 0.10
    runtime = final["comparison"]["runtime_config"]
    assert runtime["capability_profile"] == "standard"
    assert runtime["reasoning_effort"] == "medium"
    assert all(
        capability not in runtime["disabled_features"]
        for capability in ("shell_tool", "plugins", "skill_search")
    )
    for side in ("original", "candidate"):
        side_report = final["comparison"][side]
        assert side_report["overall_pass_rate"] == 1.0
        assert side_report["n_errors"] == 0
        assert all(
            case["n_passed"] == case["n_trials"] == 3
            for task in side_report["task_results"]
            for case in task["case_results"]
        )
