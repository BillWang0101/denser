"""Integrity checks for the redistributable AGENTS.md replay pilot."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from denser.inspection import inspect
from denser.replay import ReplayCategory, ReplaySuiteRole, load_replay_suite, load_replay_tasks
from denser.verification import VerificationDecision, verify

CASE_DIR = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "project_instructions"
    / "01_codex_release_ops"
)
PYTHON_POLICY_CASE_DIR = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "project_instructions"
    / "02_openai_python_version_policy"
)
PROJECT_INSTRUCTIONS_DIR = CASE_DIR.parent


def _normalized_text_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def test_replay_suite_covers_every_contract_item_and_boundary_category() -> None:
    original = (CASE_DIR / "AGENTS.md").read_text(encoding="utf-8")
    contract = inspect(original, task_type="claude_md", min_tokens=1).contract
    tasks = load_replay_tasks(CASE_DIR / "replay.json")

    covered = {item_id for task in tasks for item_id in task.covers}
    categories = {case.category for task in tasks for case in task.cases}

    assert covered == {item.item_id for item in contract.items}
    assert categories == set(ReplayCategory)


def test_dense_candidate_retains_every_protected_literal() -> None:
    original = (CASE_DIR / "AGENTS.md").read_text(encoding="utf-8")
    candidate = (CASE_DIR / "AGENTS.dense.md").read_text(encoding="utf-8")
    report = verify(original, candidate, task_type="claude_md")

    assert report.decision == VerificationDecision.REVIEW
    assert report.missing_literals == ()


def test_validated_v3_report_only_adds_sanitized_runtime_metadata() -> None:
    v2_path = CASE_DIR / "replay-report.codex-gpt-5.6-sol-medium.2026-08-17.validated.json"
    v3_path = CASE_DIR / "replay-report.codex-gpt-5.6-sol-medium.2026-08-17.validated.v3.json"
    v2_bytes = v2_path.read_bytes()
    canonical_v2_bytes = v2_bytes.replace(b"\r\n", b"\n")
    v2 = json.loads(v2_bytes)
    v3 = json.loads(v3_path.read_bytes())
    expected_config = {
        "backend_kind": "codex-cli",
        "model": "gpt-5.6-sol",
        "codex_cli_version": "0.147.0",
        "reasoning_effort": "medium",
        "sandbox": "read-only",
        "ephemeral": True,
        "ignore_user_config": True,
        "respect_system_proxy": True,
        "timeout_seconds": 180.0,
        "disabled_features": ["apps", "memories", "multi_agent"],
    }

    assert v3["schema_version"] == "denser.replay-report/v3"
    assert v3["runtime_config"] == expected_config
    assert v3["original"]["runtime_config"] == expected_config
    assert v3["candidate"]["runtime_config"] == expected_config
    assert v3["provenance"] == {
        "transformation": "metadata-only migration; no model calls rerun",
        "source_schema_version": "denser.replay-report/v2",
        "source_report_sha256": hashlib.sha256(canonical_v2_bytes).hexdigest(),
    }

    excluded = {"schema_version", "runtime_config", "provenance"}

    def without_migration_metadata(value: object) -> object:
        if isinstance(value, dict):
            return {
                key: without_migration_metadata(item)
                for key, item in value.items()
                if key not in excluded
            }
        if isinstance(value, list):
            return [without_migration_metadata(item) for item in value]
        return value

    assert without_migration_metadata(v3) == without_migration_metadata(v2)


def test_python_policy_holdout_is_frozen_and_covers_its_contract() -> None:
    original = (PYTHON_POLICY_CASE_DIR / "AGENTS.md").read_text(encoding="utf-8")
    candidate = (PYTHON_POLICY_CASE_DIR / "AGENTS.dense.md").read_text(encoding="utf-8")
    contract = json.loads(
        (PYTHON_POLICY_CASE_DIR / "preservation-contract.json").read_text(encoding="utf-8")
    )
    suite = load_replay_suite(PYTHON_POLICY_CASE_DIR / "replay.holdout.json")

    suite.validate_assets(original, candidate)
    covered = {item_id for task in suite.tasks for item_id in task.covers}
    categories = {case.category for task in suite.tasks for case in task.cases}

    assert suite.role == ReplaySuiteRole.HOLDOUT
    assert suite.authoring is not None and not suite.authoring.candidate_visible
    assert suite.freeze is not None
    assert suite.freeze.frozen_at_utc < suite.authoring.authored_at_utc
    assert covered == {item["id"] for item in contract["items"]}
    assert categories == set(ReplayCategory)
    assert sum(len(task.cases) for task in suite.tasks) == 23


def test_python_policy_candidate_retains_protected_literals() -> None:
    original = (PYTHON_POLICY_CASE_DIR / "AGENTS.md").read_text(encoding="utf-8")
    candidate = (PYTHON_POLICY_CASE_DIR / "AGENTS.dense.md").read_text(encoding="utf-8")
    report = verify(original, candidate, task_type="claude_md")

    assert report.decision == VerificationDecision.REVIEW
    assert report.missing_literals == ()


def test_python_policy_audit_is_bound_to_raw_reports() -> None:
    audit = json.loads(
        (PYTHON_POLICY_CASE_DIR / "blind-audit.2026-08-17.json").read_text(encoding="utf-8")
    )
    report_entries = [audit["source_report"], *audit["negative_controls"]]
    for entry in report_entries:
        path_key = "path" if "path" in entry else "report_path"
        raw = (PYTHON_POLICY_CASE_DIR / entry[path_key]).read_bytes()
        canonical = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        assert hashlib.sha256(canonical).hexdigest() == entry["repository_sha256"]

    blind = json.loads(
        (PYTHON_POLICY_CASE_DIR / audit["source_report"]["path"]).read_text(encoding="utf-8")
    )
    invalid = {item["case_name"] for item in audit["invalid_cases"]}
    for side in ("original", "candidate"):
        valid_results = [
            case
            for task in blind[side]["task_results"]
            for case in task["case_results"]
            if case["case_name"] not in invalid
        ]
        assert len(valid_results) == audit["audited_valid_result"]["valid_cases"]
        assert sum(case["n_passed"] for case in valid_results) == 66
        assert sum(case["n_trials"] for case in valid_results) == 66

    expected_mutant_passes = [6, 15, 0]
    for entry, expected in zip(audit["negative_controls"], expected_mutant_passes, strict=True):
        report = json.loads(
            (PYTHON_POLICY_CASE_DIR / entry["report_path"]).read_text(encoding="utf-8")
        )
        observed = sum(
            case["n_passed"]
            for task in report["candidate"]["task_results"]
            for case in task["case_results"]
        )
        assert observed == expected


def test_python_policy_permission_causal_audit_is_bound_and_honest() -> None:
    original = (PYTHON_POLICY_CASE_DIR / "AGENTS.md").read_text(encoding="utf-8")
    candidate = (PYTHON_POLICY_CASE_DIR / "AGENTS.dense.md").read_text(encoding="utf-8")
    counterfactual = (PYTHON_POLICY_CASE_DIR / "AGENTS.permission-counterfactual.md").read_text(
        encoding="utf-8"
    )
    source_suite = load_replay_suite(
        PYTHON_POLICY_CASE_DIR / "replay.permission-causal.holdout.json"
    )
    counterfactual_suite = load_replay_suite(
        PYTHON_POLICY_CASE_DIR / "replay.permission-causal.counterfactual.json"
    )

    source_suite.validate_assets(original, candidate)
    assert source_suite.role == ReplaySuiteRole.HOLDOUT
    assert counterfactual_suite.role == ReplaySuiteRole.DEVELOPMENT
    assert source_suite.freeze is not None
    assert source_suite.authoring is not None
    assert source_suite.freeze.frozen_at_utc < source_suite.authoring.authored_at_utc

    source_cases = [case for task in source_suite.tasks for case in task.cases]
    counterfactual_cases = [case for task in counterfactual_suite.tasks for case in task.cases]
    assert len(source_cases) == len(counterfactual_cases) == 5
    for source_case, counterfactual_case in zip(source_cases, counterfactual_cases, strict=True):
        assert source_case.name == counterfactual_case.name
        assert source_case.prompt == counterfactual_case.prompt
        assert source_case.category == counterfactual_case.category
        assert source_case.expected_values != counterfactual_case.expected_values

    source_permission_block = """  - Runs a pinned Codex runtime as an unprivileged user with no command network
    access and read-only repository permissions.
  - Codex cannot edit the repository or call GitHub. A separate job with no
    OpenAI credential opens or refreshes one issue only when action is needed.
  - Never changes the Python floor or merges code automatically."""
    counterfactual_permission_block = """  - Runs an unpinned Codex runtime as a privileged user with command network
    access and write repository permissions.
  - Codex may edit the repository and call GitHub. The separate job with no
    OpenAI credential may not open or refresh issues; instead, Codex opens or
    refreshes multiple issues after every review, whether or not action is needed.
  - Whenever the review recommends a Python-floor change, the automation changes
    the floor and merges the change automatically."""
    assert (
        original.replace(source_permission_block, counterfactual_permission_block) == counterfactual
    )

    audit = json.loads(
        (PYTHON_POLICY_CASE_DIR / "permission-causal-audit.2026-08-17.json").read_text(
            encoding="utf-8"
        )
    )
    assert audit["source_fidelity_review"]["all_cases_accepted"] is True
    assert audit["source_fidelity_review"]["counterfactual_visible"] is True
    assert audit["design_checks"]["source_and_counterfactual_prompts_identical"] is True
    assert audit["results"]["stable_full_flips"] == 4
    assert audit["results"]["counterfactual"] == {"passed": 13, "trials": 15}

    reports: dict[str, dict[str, object]] = {}
    for entry in audit["reports"]:
        raw = (PYTHON_POLICY_CASE_DIR / entry["path"]).read_bytes()
        canonical = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        assert hashlib.sha256(canonical).hexdigest() == entry["repository_sha256"]
        reports[entry["path"]] = json.loads(raw)

    paired = reports["replay-report.codex-gpt-5.6-sol-medium.2026-08-17.permission-causal.json"]
    mutant = reports[
        "replay-report.codex-gpt-5.6-sol-medium.2026-08-17.permission-counterfactual.json"
    ]
    source_suite_payload = json.dumps(
        source_suite.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    counterfactual_suite_payload = json.dumps(
        counterfactual_suite.to_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    assert (
        paired["suite_sha256"] == hashlib.sha256(source_suite_payload.encode("utf-8")).hexdigest()
    )
    assert (
        mutant["suite_sha256"]
        == hashlib.sha256(counterfactual_suite_payload.encode("utf-8")).hexdigest()
    )
    assert paired["original"]["instruction_sha256"] == source_suite.freeze.original_sha256
    assert paired["candidate"]["instruction_sha256"] == source_suite.freeze.candidate_sha256
    assert (
        mutant["instruction_sha256"] == hashlib.sha256(counterfactual.encode("utf-8")).hexdigest()
    )
    for side in ("original", "candidate"):
        results = [case for task in paired[side]["task_results"] for case in task["case_results"]]
        assert sum(case["n_passed"] for case in results) == 15
        assert sum(case["n_trials"] for case in results) == 15
        assert sum(len(case["errors"]) for case in results) == 0

    mutant_results = [case for task in mutant["task_results"] for case in task["case_results"]]
    assert sum(case["n_passed"] for case in mutant_results) == 13
    assert sum(case["n_trials"] for case in mutant_results) == 15
    assert sum(len(case["errors"]) for case in mutant_results) == 0
    by_name = {case["case_name"]: case for case in mutant_results}
    assert by_name["monthly_finding_new_issue"]["outputs"] == ["LEAVE_GITHUB_UNCHANGED"] * 3
    assert by_name["monthly_finding_existing_issue"]["outputs"].count("LEAVE_ISSUE_UNCHANGED") == 1
    assert all(
        metadata["transport_fallback"] is False
        for report in (paired["original"], paired["candidate"], mutant)
        for task in report["task_results"]
        for case in task["case_results"]
        for metadata in case["backend_metadata"]
    )


def test_deepseek_v4_replay_audit_is_bound_sanitized_and_honest() -> None:
    project_instruction_dir = CASE_DIR.parent
    audit = json.loads(
        (project_instruction_dir / "deepseek-v4-replay-audit.2026-08-17.json").read_text(
            encoding="utf-8"
        )
    )
    original = (PYTHON_POLICY_CASE_DIR / "AGENTS.md").read_text(encoding="utf-8")
    counterfactual = (PYTHON_POLICY_CASE_DIR / "AGENTS.permission-counterfactual.md").read_text(
        encoding="utf-8"
    )

    def observations(side: dict[str, object]) -> tuple[int, int]:
        cases = [
            case
            for task in side["task_results"]  # type: ignore[index]
            for case in task["case_results"]
        ]
        return (
            sum(case["n_passed"] for case in cases),
            sum(case["n_trials"] for case in cases),
        )

    total_calls = 0
    reports: dict[str, dict[str, object]] = {}
    for entry in audit["reports"]:
        raw = (project_instruction_dir / entry["path"]).read_bytes()
        canonical = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        assert hashlib.sha256(canonical).hexdigest() == entry["repository_sha256"]

        text = raw.decode("utf-8")
        assert re.search(r"\bsk-[A-Za-z0-9_-]{20,}\b", text) is None
        assert re.search(r"\bgh[opusr]_[A-Za-z0-9_]{20,}\b", text) is None
        assert "C:\\Users\\" not in text
        assert "DENSER_DEEPSEEK_API_KEY" not in text

        report = json.loads(raw)
        reports[entry["path"]] = report
        assert report["runtime_config"] == {
            "backend_kind": "openai-compatible",
            "model": entry["model"],
            "thinking_mode": "disabled",
        }

        if "candidate" in report:
            original_result = observations(report["original"])
            candidate_result = observations(report["candidate"])
            assert original_result == tuple(entry["original"].values())
            expected_candidate = entry.get("candidate", entry.get("mutant"))
            assert candidate_result == tuple(expected_candidate.values())
            calls = original_result[1] + candidate_result[1]
            errors = report["original"]["n_errors"] + report["candidate"]["n_errors"]
        else:
            single_result = observations(report)
            assert single_result == tuple(
                entry["source_instruction_against_inverted_labels"].values()
            )
            calls = single_result[1]
            errors = report["n_errors"]

        assert calls == entry["calls"]
        assert errors == entry["operational_errors"] == 0
        total_calls += calls

    assert total_calls == audit["run_config"]["total_calls"] == 534
    assert audit["run_config"]["operational_errors"] == 0
    assert audit["sensitive_shape_scan"]["matches"] == 0

    invalid_case = audit["known_invalid_case"]["case_name"]
    for model in ("deepseek-v4-pro", "deepseek-v4-flash"):
        path = next(
            entry["path"]
            for entry in audit["reports"]
            if entry["model"] == model and ".blind.observed.json" in entry["path"]
        )
        report = reports[path]
        for side_name in ("original", "candidate"):
            valid_cases = [
                case
                for task in report[side_name]["task_results"]
                for case in task["case_results"]
                if case["case_name"] != invalid_case
            ]
            expected = audit["known_invalid_case"]["audited_valid_results"][model][side_name]
            assert sum(case["n_passed"] for case in valid_cases) == expected["passed"]
            assert sum(case["n_trials"] for case in valid_cases) == expected["trials"]

    original_sha256 = hashlib.sha256(original.encode("utf-8")).hexdigest()
    counterfactual_sha256 = hashlib.sha256(counterfactual.encode("utf-8")).hexdigest()
    label_reports = [
        report
        for path, report in reports.items()
        if ".permission-counterfactual.observed.json" in path
    ]
    assert len(label_reports) == 2
    assert all(report["instruction_sha256"] == original_sha256 for report in label_reports)
    assert all(report["instruction_sha256"] != counterfactual_sha256 for report in label_reports)


def test_codex_text_only_profile_audit_is_bound_and_clears_gate() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    audit = json.loads(
        (PROJECT_INSTRUCTIONS_DIR / "codex-text-only-profile-audit.2026-08-17.json").read_text(
            encoding="utf-8"
        )
    )

    assert audit["schema_version"] == "denser.codex-capability-profile-audit/v1"
    assert audit["source_hash_method"] == "utf8-lf-v1"
    assert audit["passed"] is True
    assert len(audit["scenarios"]) == 2
    for scenario in audit["scenarios"]:
        for source_name in ("asset", "suite"):
            source = scenario[source_name]
            assert _normalized_text_sha256(repo_root / source["path"]) == source["sha256"]
        baseline = scenario["baseline"]
        assert _normalized_text_sha256(repo_root / baseline["report"]) == baseline["report_sha256"]
        variant = scenario["variant"]
        assert baseline["passed_calls"] == baseline["calls"]
        assert baseline["operational_errors"] == 0
        assert variant["completed_calls"] == variant["calls"]
        assert variant["passed_calls"] == variant["calls"]
        assert variant["operational_errors"] == 0
        assert len(scenario["cases"]) == variant["calls"]
        assert all(case["passed"] for case in scenario["cases"])
        assert sum(case["input_tokens"] for case in scenario["cases"]) == variant["input_tokens"]
        baseline_per_call = baseline["input_tokens"] / baseline["calls"]
        variant_per_call = variant["input_tokens"] / variant["calls"]
        reduction = (baseline_per_call - variant_per_call) / baseline_per_call
        assert abs(baseline_per_call - baseline["input_tokens_per_call"]) < 1e-9
        assert abs(variant_per_call - variant["input_tokens_per_call"]) < 1e-9
        assert abs(reduction - scenario["input_token_reduction_fraction"]) < 1e-12
        assert reduction >= 0.10
        assert scenario["quality_delta"] == 0.0


def test_paired_codex_profile_audit_is_complete_and_clears_gate() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    audit = json.loads(
        (
            PROJECT_INSTRUCTIONS_DIR
            / "codex-text-only-profile-audit.paired-3x-final.2026-08-17.json"
        ).read_text(encoding="utf-8")
    )

    assert audit["schema_version"] == "denser.codex-capability-profile-audit/v2"
    assert audit["source_hash_method"] == "utf8-lf-v1"
    assert audit["passed"] is True
    assert audit["schedule"] == {
        "seed": 20260817,
        "trials_per_case": 3,
        "workers": 8,
        "randomized_submission_order": True,
        "total_calls": 84,
    }
    assert audit["runtime"]["text_only_profile_instruction_version"] == "text-only/v1"
    assert len(audit["scenarios"]) == 2

    total_calls = 0
    for scenario in audit["scenarios"]:
        for source_name in ("asset", "suite"):
            source = scenario[source_name]
            assert _normalized_text_sha256(repo_root / source["path"]) == source["sha256"]

        for profile_name in ("standard", "text-only"):
            calls = scenario["calls"][profile_name]
            summary = scenario["profiles"][profile_name]
            assert len(calls) == summary["calls"]
            assert summary["completed_calls"] == summary["calls"]
            assert summary["passed_calls"] == summary["calls"]
            assert summary["operational_errors"] == 0
            assert summary["transport_fallback_calls"] == 0
            assert all(call["status"] == "completed" for call in calls)
            assert all(call["passed"] is True for call in calls)
            assert all(call["transport_fallback"] is False for call in calls)
            assert sum(call["usage"]["input_tokens"] for call in calls) == summary["input_tokens"]
            total_calls += len(calls)

        assert scenario["input_token_reduction_fraction"] >= 0.10
        assert scenario["quality_delta"] == 0.0
        assert scenario["passed"] is True

    assert total_calls == audit["schedule"]["total_calls"]
