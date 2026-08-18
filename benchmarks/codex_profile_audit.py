"""Reproduce the paired Codex standard-vs-text-only profile audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from denser.backends.codex_cli import (
    CODEX_CAPABILITY_PROFILES,
    TEXT_ONLY_PROFILE_INSTRUCTION_VERSION,
    CodexCliBackend,
)
from denser.replay import ReplayCase, load_replay_suite

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "build" / "codex-profile-audit.json"
SCHEMA_VERSION = "denser.codex-capability-profile-audit/v2"


@dataclass(frozen=True)
class Scenario:
    name: str
    asset: Path
    suite: Path


@dataclass(frozen=True)
class CallUnit:
    scenario: str
    profile: str
    task_name: str
    case: ReplayCase
    max_tokens: int
    trial: int


DEFAULT_SCENARIOS = (
    Scenario(
        name="release_operations",
        asset=ROOT / "examples" / "project_instructions" / "01_codex_release_ops" / "AGENTS.md",
        suite=ROOT / "examples" / "project_instructions" / "01_codex_release_ops" / "replay.json",
    ),
    Scenario(
        name="automation_permission_routing",
        asset=(
            ROOT
            / "examples"
            / "project_instructions"
            / "02_openai_python_version_policy"
            / "AGENTS.md"
        ),
        suite=(
            ROOT
            / "examples"
            / "project_instructions"
            / "02_openai_python_version_policy"
            / "replay.permission-causal.holdout.json"
        ),
    ),
)

UV_PUBLIC_PILOT_SCENARIOS = (
    Scenario(
        name="uv_issue_triage_snapshot",
        asset=(
            ROOT
            / "examples"
            / "project_instructions"
            / "03_uv_public_pilot"
            / "issue-triage-rules.md"
        ),
        suite=(
            ROOT
            / "examples"
            / "project_instructions"
            / "03_uv_public_pilot"
            / "issue-triage.replay.json"
        ),
    ),
    Scenario(
        name="uv_workflow_failure_snapshot",
        asset=(
            ROOT
            / "examples"
            / "project_instructions"
            / "03_uv_public_pilot"
            / "workflow-failure-rules.md"
        ),
        suite=(
            ROOT
            / "examples"
            / "project_instructions"
            / "03_uv_public_pilot"
            / "workflow-failure.replay.json"
        ),
    ),
)

SCENARIO_SETS = {
    "built-in": DEFAULT_SCENARIOS,
    "uv-public-pilot": UV_PUBLIC_PILOT_SCENARIOS,
}


def _sha256(path: Path) -> str:
    """Hash the UTF-8 text exactly as Python passes it to the backend.

    ``read_text`` applies universal-newline normalization, so the digest is
    stable across LF and CRLF checkouts and binds the actual model input.
    """
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _execute(
    unit: CallUnit,
    *,
    assets: dict[str, str],
    executable: Path | None,
    model: str,
    reasoning_effort: str,
    timeout_seconds: float,
    respect_system_proxy: bool,
) -> dict[str, Any]:
    backend = CodexCliBackend(
        executable=executable,
        model=model,
        reasoning_effort=reasoning_effort,
        timeout_seconds=timeout_seconds,
        respect_system_proxy=respect_system_proxy,
        capability_profile=unit.profile,
    )
    try:
        output = backend.complete(
            system=assets[unit.scenario],
            user=unit.case.prompt,
            max_tokens=unit.max_tokens,
        )
    except Exception as exc:
        return {
            "scenario": unit.scenario,
            "profile": unit.profile,
            "task": unit.task_name,
            "case": unit.case.name,
            "trial": unit.trial,
            "status": "error",
            "passed": False,
            "error_type": type(exc).__name__,
        }

    metadata = backend.last_call_metadata or {}
    usage = metadata.get("usage")
    if not isinstance(usage, dict):
        usage = {}
    return {
        "scenario": unit.scenario,
        "profile": unit.profile,
        "task": unit.task_name,
        "case": unit.case.name,
        "trial": unit.trial,
        "status": metadata.get("status"),
        "passed": unit.case.matches(output),
        "output": output.strip(),
        "duration_ms": metadata.get("duration_ms"),
        "transport_fallback": metadata.get("transport_fallback"),
        "usage": {
            "input_tokens": usage.get("input_tokens"),
            "cached_input_tokens": usage.get("cached_input_tokens"),
            "cache_write_input_tokens": usage.get("cache_write_input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "reasoning_output_tokens": usage.get("reasoning_output_tokens"),
        },
    }


def _sum_usage(calls: list[dict[str, Any]], key: str) -> int:
    total = 0
    for call in calls:
        usage = call.get("usage")
        if isinstance(usage, dict):
            value = usage.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                total += value
    return total


def _summarize(calls: list[dict[str, Any]]) -> dict[str, Any]:
    completed = sum(call.get("status") == "completed" for call in calls)
    passed = sum(call.get("passed") is True for call in calls)
    input_tokens = _sum_usage(calls, "input_tokens")
    return {
        "calls": len(calls),
        "completed_calls": completed,
        "passed_calls": passed,
        "pass_rate": passed / len(calls),
        "operational_errors": len(calls) - completed,
        "input_tokens": input_tokens,
        "input_tokens_per_call": input_tokens / len(calls),
        "cached_input_tokens": _sum_usage(calls, "cached_input_tokens"),
        "cache_write_input_tokens": _sum_usage(calls, "cache_write_input_tokens"),
        "output_tokens": _sum_usage(calls, "output_tokens"),
        "reasoning_output_tokens": _sum_usage(calls, "reasoning_output_tokens"),
        "transport_fallback_calls": sum(call.get("transport_fallback") is True for call in calls),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--scenario-set", choices=tuple(SCENARIO_SETS), default="built-in")
    parser.add_argument(
        "--reasoning-effort",
        choices=("none", "low", "medium", "high", "xhigh", "max"),
        default="medium",
    )
    parser.add_argument("--baseline-profile", choices=CODEX_CAPABILITY_PROFILES, default="standard")
    parser.add_argument("--variant-profile", choices=CODEX_CAPABILITY_PROFILES, default="text-only")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260817)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--minimum-reduction", type=float, default=0.10)
    parser.add_argument("--codex-cli-path", type=Path, default=None)
    parser.add_argument("--respect-system-proxy", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.trials < 1 or args.workers < 1 or args.timeout <= 0:
        parser.error("trials, workers, and timeout must be greater than zero")
    if not 0 <= args.minimum_reduction < 1:
        parser.error("minimum-reduction must be between zero and one")
    if args.baseline_profile == args.variant_profile:
        parser.error("baseline-profile and variant-profile must differ")
    if args.output.exists():
        parser.error(f"refusing to overwrite existing report: {args.output}")
    return args


def main() -> int:
    """Run the paired audit and return a process exit status."""
    args = _parse_args()
    selected_scenarios = SCENARIO_SETS[args.scenario_set]
    profiles = (args.baseline_profile, args.variant_profile)
    assets: dict[str, str] = {}
    units: list[CallUnit] = []
    scenario_sources: dict[str, dict[str, Any]] = {}
    for scenario in selected_scenarios:
        asset = scenario.asset.read_text(encoding="utf-8")
        suite = load_replay_suite(scenario.suite)
        if suite.freeze is not None:
            suite.validate_assets(asset)
        assets[scenario.name] = asset
        scenario_sources[scenario.name] = {
            "asset": {"path": _relative(scenario.asset), "sha256": _sha256(scenario.asset)},
            "suite": {"path": _relative(scenario.suite), "sha256": _sha256(scenario.suite)},
        }
        for task in suite.tasks:
            for case in task.cases:
                for trial in range(1, args.trials + 1):
                    for profile in profiles:
                        units.append(
                            CallUnit(
                                scenario=scenario.name,
                                profile=profile,
                                task_name=task.name,
                                case=case,
                                max_tokens=task.max_tokens,
                                trial=trial,
                            )
                        )

    random.Random(args.seed).shuffle(units)
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [
            pool.submit(
                _execute,
                unit,
                assets=assets,
                executable=args.codex_cli_path,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                timeout_seconds=args.timeout,
                respect_system_proxy=args.respect_system_proxy,
            )
            for unit in units
        ]
        total = len(futures)
        for completed, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            results.append(result)
            print(
                f"{completed}/{total} | {result['profile']} | "
                f"{result['scenario']}/{result['case']} | trial {result['trial']} | "
                f"{'pass' if result['passed'] else 'fail'}",
                flush=True,
            )

    scenarios: list[dict[str, Any]] = []
    for scenario in selected_scenarios:
        calls_by_profile = {
            profile: sorted(
                (
                    call
                    for call in results
                    if call["scenario"] == scenario.name and call["profile"] == profile
                ),
                key=lambda call: (call["task"], call["case"], call["trial"]),
            )
            for profile in profiles
        }
        summaries = {profile: _summarize(calls) for profile, calls in calls_by_profile.items()}
        baseline = summaries[args.baseline_profile]
        variant = summaries[args.variant_profile]
        saved = baseline["input_tokens_per_call"] - variant["input_tokens_per_call"]
        reduction = saved / baseline["input_tokens_per_call"]
        quality_delta = variant["pass_rate"] - baseline["pass_rate"]
        scenarios.append(
            {
                "name": scenario.name,
                **scenario_sources[scenario.name],
                "profiles": summaries,
                "input_tokens_saved_per_call": saved,
                "input_token_reduction_fraction": reduction,
                "quality_delta": quality_delta,
                "passed": (
                    baseline["operational_errors"] == 0
                    and variant["operational_errors"] == 0
                    and quality_delta >= 0
                    and reduction >= args.minimum_reduction
                ),
                "calls": calls_by_profile,
            }
        )

    probe = CodexCliBackend(
        executable=args.codex_cli_path,
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        timeout_seconds=args.timeout,
        respect_system_proxy=args.respect_system_proxy,
        capability_profile=args.baseline_profile,
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "source_hash_method": "utf8-lf-v1",
        "scenario_set": args.scenario_set,
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "runtime": {
            "backend_kind": "codex-cli",
            "model": args.model,
            "codex_cli_version": probe.runtime_config["codex_cli_version"],
            "reasoning_effort": args.reasoning_effort,
            "timeout_seconds": args.timeout,
            "ephemeral": True,
            "sandbox": "read-only",
            "ignore_user_config": True,
            "respect_system_proxy": args.respect_system_proxy,
            "baseline_profile": args.baseline_profile,
            "variant_profile": args.variant_profile,
            "text_only_profile_instruction_version": TEXT_ONLY_PROFILE_INSTRUCTION_VERSION,
        },
        "schedule": {
            "seed": args.seed,
            "trials_per_case": args.trials,
            "workers": args.workers,
            "randomized_submission_order": True,
            "total_calls": len(units),
        },
        "success_rule": {
            "minimum_scenarios": 2,
            "minimum_input_token_reduction_fraction_per_scenario": args.minimum_reduction,
            "quality_must_not_decrease": True,
            "operational_errors_allowed": 0,
        },
        "scenarios": scenarios,
        "passed": len(scenarios) >= 2 and all(scenario["passed"] for scenario in scenarios),
        "limitations": [
            "Results apply only to the exact assets, workloads, model, CLI version, and runtime settings recorded here.",
            "Concurrent randomized submission balances call order but does not guarantee completion order.",
            "Text-only removes capabilities required for coding and agentic work; standard remains the default profile.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output": str(args.output), "passed": report["passed"]}, indent=2))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
