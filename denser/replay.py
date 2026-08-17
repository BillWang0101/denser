"""Deterministic behavior replay for versioned instruction assets.

Unlike the legacy structural-check harness in :mod:`denser.eval`, replay runs
the instruction asset in the backend's system-instruction position and sends
realistic workload prompts as user messages. Outputs are scored with explicit,
deterministic matchers; no model judge decides whether an answer passed.

The runner supports paired, reproducibly randomized original/candidate calls so
provider drift or transient service behavior is less likely to align with one
side merely because it always ran first.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from denser.backends import Backend
from denser.taxonomy import TaskType

logger = logging.getLogger(__name__)

REPLAY_REPORT_SCHEMA_VERSION = "denser.replay-report/v4"

_RUNTIME_CONFIG_STRING_KEYS = (
    "backend_kind",
    "model",
    "codex_cli_version",
    "reasoning_effort",
    "sandbox",
    "thinking_mode",
)
_RUNTIME_CONFIG_BOOL_KEYS = (
    "ephemeral",
    "ignore_user_config",
    "respect_system_proxy",
)
REPLAY_SUITE_SCHEMA_VERSION = "denser.replay-suite/v2"
LEGACY_REPLAY_SUITE_SCHEMA_VERSION = "denser.replay-suite/v1"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_UTC_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")


class ReplayCategory(str, Enum):
    """Behavior boundary exercised by a replay case."""

    POSITIVE_TRIGGER = "positive_trigger"
    NEAR_MISS = "near_miss"
    FAILURE_PATH = "failure_path"
    PERMISSION_BOUNDARY = "permission_boundary"
    ADVERSARIAL = "adversarial"


class MatchMode(str, Enum):
    """Deterministic rule used to score a model output."""

    EXACT = "exact"
    CONTAINS = "contains"
    REGEX = "regex"


class ReplaySuiteRole(str, Enum):
    """Whether cases may guide candidate writing or are frozen holdouts."""

    DEVELOPMENT = "development"
    HOLDOUT = "holdout"


@dataclass(frozen=True)
class ReplayCase:
    """One realistic request and its deterministic output contract."""

    name: str
    prompt: str
    expected: str | tuple[str, ...]
    category: ReplayCategory
    match_mode: MatchMode = MatchMode.EXACT
    forbidden: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Replay case name cannot be empty")
        if not self.prompt.strip():
            raise ValueError(f"Replay case {self.name!r} prompt cannot be empty")
        expected = self.expected_values
        if not expected or any(not item for item in expected):
            raise ValueError(f"Replay case {self.name!r} expected output cannot be empty")
        if self.match_mode == MatchMode.REGEX:
            for pattern in expected:
                try:
                    re.compile(pattern)
                except re.error as exc:
                    raise ValueError(
                        f"Replay case {self.name!r} has invalid regex: {pattern!r}"
                    ) from exc

    @property
    def expected_values(self) -> tuple[str, ...]:
        """Return the accepted values in a stable tuple form."""
        if isinstance(self.expected, str):
            return (self.expected,)
        return self.expected

    def matches(self, output: str) -> bool:
        """Return whether ``output`` satisfies the explicit case contract."""
        observed = output.strip()
        if any(value in observed for value in self.forbidden):
            return False

        if self.match_mode == MatchMode.EXACT:
            return any(observed == value.strip() for value in self.expected_values)
        if self.match_mode == MatchMode.CONTAINS:
            return any(value in observed for value in self.expected_values)
        return any(
            re.fullmatch(pattern, observed, flags=re.DOTALL) is not None
            for pattern in self.expected_values
        )

    def to_dict(self) -> dict[str, object]:
        """Return a canonical JSON-compatible case definition."""
        return {
            "name": self.name,
            "prompt": self.prompt,
            "expected": list(self.expected_values),
            "category": self.category.value,
            "match_mode": self.match_mode.value,
            "forbidden": list(self.forbidden),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReplayCase:
        """Build a replay case from a JSON-compatible mapping."""
        name = data.get("name")
        prompt = data.get("prompt")
        category = data.get("category")
        match_mode = data.get("match_mode", MatchMode.EXACT.value)
        forbidden = data.get("forbidden", [])
        if not isinstance(name, str) or not isinstance(prompt, str):
            raise ValueError("Replay case name and prompt must be strings")
        if not isinstance(category, str) or not isinstance(match_mode, str):
            raise ValueError("Replay case category and match_mode must be strings")
        if not isinstance(forbidden, list) or not all(isinstance(item, str) for item in forbidden):
            raise ValueError("Replay case forbidden must be a list of strings")
        raw_expected = data["expected"]
        expected: str | tuple[str, ...]
        if isinstance(raw_expected, str):
            expected = raw_expected
        elif isinstance(raw_expected, list) and all(isinstance(item, str) for item in raw_expected):
            expected = tuple(raw_expected)
        else:
            raise ValueError("Replay case expected must be a string or list of strings")
        return cls(
            name=name,
            prompt=prompt,
            expected=expected,
            category=ReplayCategory(category),
            match_mode=MatchMode(match_mode),
            forbidden=tuple(forbidden),
        )


@dataclass(frozen=True)
class ReplayTask:
    """A named behavior suite mapped to preservation-contract items."""

    task_type: TaskType
    name: str
    description: str
    cases: tuple[ReplayCase, ...]
    covers: tuple[str, ...] = ()
    pass_threshold: float = 1.0
    max_tokens: int = 128

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Replay task name cannot be empty")
        if not self.cases:
            raise ValueError(f"Replay task {self.name!r} must contain at least one case")
        case_names = [case.name for case in self.cases]
        if len(case_names) != len(set(case_names)):
            raise ValueError(f"Replay task {self.name!r} has duplicate case names")
        if not 0.0 <= self.pass_threshold <= 1.0:
            raise ValueError("Replay task pass_threshold must be between 0 and 1")
        if self.max_tokens < 1:
            raise ValueError("Replay task max_tokens must be >= 1")

    def to_dict(self) -> dict[str, object]:
        """Return a canonical JSON-compatible task definition."""
        return {
            "task_type": self.task_type.value,
            "name": self.name,
            "description": self.description,
            "cases": [case.to_dict() for case in self.cases],
            "covers": list(self.covers),
            "pass_threshold": self.pass_threshold,
            "max_tokens": self.max_tokens,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReplayTask:
        """Build a replay task from a JSON-compatible mapping."""
        task_type = data.get("task_type")
        name = data.get("name")
        description = data.get("description", "")
        raw_cases = data.get("cases")
        covers = data.get("covers", [])
        pass_threshold = data.get("pass_threshold", 1.0)
        max_tokens = data.get("max_tokens", 128)
        if (
            not isinstance(task_type, str)
            or not isinstance(name, str)
            or not isinstance(description, str)
        ):
            raise ValueError("Replay task type, name, and description must be strings")
        if not isinstance(raw_cases, list) or not all(isinstance(item, dict) for item in raw_cases):
            raise ValueError("Replay task cases must be a list of objects")
        if not isinstance(covers, list) or not all(isinstance(item, str) for item in covers):
            raise ValueError("Replay task covers must be a list of strings")
        if isinstance(pass_threshold, bool) or not isinstance(pass_threshold, (int, float)):
            raise ValueError("Replay task pass_threshold must be numeric")
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int):
            raise ValueError("Replay task max_tokens must be an integer")
        return cls(
            task_type=TaskType.parse(task_type),
            name=name,
            description=description,
            cases=tuple(ReplayCase.from_dict(item) for item in raw_cases),
            covers=tuple(covers),
            pass_threshold=float(pass_threshold),
            max_tokens=max_tokens,
        )


@dataclass(frozen=True)
class ReplaySuiteFreeze:
    """Cryptographic identity of assets fixed before holdout authoring."""

    original_sha256: str
    candidate_sha256: str
    candidate_commit: str
    frozen_at_utc: str

    def __post_init__(self) -> None:
        for label, value in (
            ("original_sha256", self.original_sha256),
            ("candidate_sha256", self.candidate_sha256),
        ):
            if _SHA256_RE.fullmatch(value) is None:
                raise ValueError(f"Replay suite freeze {label} must be a lowercase SHA-256")
        if _GIT_COMMIT_RE.fullmatch(self.candidate_commit) is None:
            raise ValueError(
                "Replay suite freeze candidate_commit must be a full lowercase Git SHA"
            )
        if _UTC_TIMESTAMP_RE.fullmatch(self.frozen_at_utc) is None:
            raise ValueError("Replay suite freeze frozen_at_utc must be an ISO-8601 UTC timestamp")

    def to_dict(self) -> dict[str, str]:
        """Return the frozen asset identity as a serializable mapping."""
        return {
            "original_sha256": self.original_sha256,
            "candidate_sha256": self.candidate_sha256,
            "candidate_commit": self.candidate_commit,
            "frozen_at_utc": self.frozen_at_utc,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReplaySuiteFreeze:
        """Construct validated freeze metadata from parsed JSON data."""
        keys = ("original_sha256", "candidate_sha256", "candidate_commit", "frozen_at_utc")
        values = {key: data.get(key) for key in keys}
        if not all(isinstance(value, str) for value in values.values()):
            raise ValueError("Replay suite freeze fields must be strings")
        return cls(**values)  # type: ignore[arg-type]


@dataclass(frozen=True)
class ReplaySuiteAuthoring:
    """Non-sensitive record of the process that authored holdout cases."""

    method: str
    authored_at_utc: str
    candidate_visible: bool
    backend: str
    model: str
    reasoning_effort: str
    cli_version: str | None = None

    def __post_init__(self) -> None:
        for label, value in (
            ("method", self.method),
            ("backend", self.backend),
            ("model", self.model),
            ("reasoning_effort", self.reasoning_effort),
        ):
            if not value.strip():
                raise ValueError(f"Replay suite authoring {label} cannot be empty")
        if _UTC_TIMESTAMP_RE.fullmatch(self.authored_at_utc) is None:
            raise ValueError(
                "Replay suite authoring authored_at_utc must be an ISO-8601 UTC timestamp"
            )
        if self.candidate_visible:
            raise ValueError(
                "A holdout suite cannot claim blind authoring when candidate_visible=true"
            )

    def to_dict(self) -> dict[str, object]:
        """Return holdout authoring provenance as a serializable mapping."""
        return {
            "method": self.method,
            "authored_at_utc": self.authored_at_utc,
            "candidate_visible": self.candidate_visible,
            "backend": self.backend,
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "cli_version": self.cli_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReplaySuiteAuthoring:
        """Construct validated authoring provenance from parsed JSON data."""
        candidate_visible = data.get("candidate_visible")
        cli_version = data.get("cli_version")
        string_keys = ("method", "authored_at_utc", "backend", "model", "reasoning_effort")
        if not all(isinstance(data.get(key), str) for key in string_keys):
            raise ValueError("Replay suite authoring identity fields must be strings")
        if not isinstance(candidate_visible, bool):
            raise ValueError("Replay suite authoring candidate_visible must be a boolean")
        if cli_version is not None and not isinstance(cli_version, str):
            raise ValueError("Replay suite authoring cli_version must be a string or null")
        return cls(
            method=data["method"],
            authored_at_utc=data["authored_at_utc"],
            candidate_visible=candidate_visible,
            backend=data["backend"],
            model=data["model"],
            reasoning_effort=data["reasoning_effort"],
            cli_version=cli_version,
        )


@dataclass(frozen=True)
class ReplaySuite:
    """Versioned replay tasks plus optional holdout freeze evidence."""

    tasks: tuple[ReplayTask, ...]
    role: ReplaySuiteRole = ReplaySuiteRole.DEVELOPMENT
    freeze: ReplaySuiteFreeze | None = None
    authoring: ReplaySuiteAuthoring | None = None
    schema_version: str = REPLAY_SUITE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.tasks:
            raise ValueError("Replay suite must contain at least one task")
        if self.role == ReplaySuiteRole.HOLDOUT:
            if self.freeze is None or self.authoring is None:
                raise ValueError("A holdout replay suite requires freeze and authoring metadata")
        elif self.freeze is not None or self.authoring is not None:
            raise ValueError("Freeze and authoring metadata are reserved for holdout replay suites")

    @property
    def report_metadata(self) -> dict[str, object]:
        """Return suite provenance suitable for embedding in replay reports."""
        if self.role == ReplaySuiteRole.DEVELOPMENT:
            return {"role": self.role.value}
        assert self.freeze is not None and self.authoring is not None
        return {
            "role": self.role.value,
            "freeze": self.freeze.to_dict(),
            "authoring": self.authoring.to_dict(),
        }

    def to_dict(self) -> dict[str, object]:
        """Return the complete replay suite as serializable data."""
        data: dict[str, object] = {
            "schema_version": self.schema_version,
            "suite_role": self.role.value,
            "tasks": [task.to_dict() for task in self.tasks],
        }
        if self.freeze is not None:
            data["freeze"] = self.freeze.to_dict()
        if self.authoring is not None:
            data["authoring"] = self.authoring.to_dict()
        return data

    def validate_assets(self, original: str, candidate: str | None = None) -> None:
        """Raise ``ValueError`` when supplied assets differ from frozen hashes."""
        if self.freeze is None:
            return
        observed_original = _text_sha256(original)
        if observed_original != self.freeze.original_sha256:
            raise ValueError(
                "Holdout suite original SHA-256 does not match the supplied instruction asset"
            )
        if candidate is not None:
            observed_candidate = _text_sha256(candidate)
            if observed_candidate != self.freeze.candidate_sha256:
                raise ValueError(
                    "Holdout suite candidate SHA-256 does not match the frozen candidate"
                )


@dataclass(frozen=True)
class ReplayCaseResult:
    """Observed outcome for one replay case across repeated trials."""

    case_name: str
    category: ReplayCategory
    n_trials: int
    n_passed: int
    outputs: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    backend_metadata: tuple[dict[str, object], ...] = ()

    @property
    def pass_rate(self) -> float:
        """Return the fraction of completed trials that passed."""
        if self.n_trials == 0:
            return 0.0
        return self.n_passed / self.n_trials

    @property
    def n_errors(self) -> int:
        """Return the number of recorded operational errors."""
        return len(self.errors)

    def to_dict(self) -> dict[str, object]:
        """Return this case result as a serializable mapping."""
        return {
            "case_name": self.case_name,
            "category": self.category.value,
            "n_trials": self.n_trials,
            "n_passed": self.n_passed,
            "pass_rate": self.pass_rate,
            "outputs": list(self.outputs),
            "errors": list(self.errors),
            "backend_metadata": list(self.backend_metadata),
        }


@dataclass(frozen=True)
class ReplayTaskResult:
    """Observed outcome for one replay task."""

    task_name: str
    case_results: tuple[ReplayCaseResult, ...]
    pass_threshold: float

    @property
    def overall_pass_rate(self) -> float:
        """Return the unweighted mean pass rate across this task's cases."""
        if not self.case_results:
            return 0.0
        return sum(result.pass_rate for result in self.case_results) / len(self.case_results)

    @property
    def passed(self) -> bool:
        """Return whether this task meets its configured pass threshold."""
        return self.overall_pass_rate >= self.pass_threshold

    @property
    def n_errors(self) -> int:
        """Return the total operational errors across this task's cases."""
        return sum(result.n_errors for result in self.case_results)

    def to_dict(self) -> dict[str, object]:
        """Return this task result as a serializable mapping."""
        return {
            "task_name": self.task_name,
            "pass_threshold": self.pass_threshold,
            "overall_pass_rate": self.overall_pass_rate,
            "passed": self.passed,
            "n_errors": self.n_errors,
            "case_results": [result.to_dict() for result in self.case_results],
        }


@dataclass(frozen=True)
class ReplayReport:
    """Aggregate replay result for a single instruction asset."""

    task_type: TaskType
    task_results: tuple[ReplayTaskResult, ...]
    backend_name: str
    n_trials: int
    instruction_sha256: str
    suite_sha256: str
    generated_at_utc: str
    runtime_config: dict[str, object] = field(default_factory=dict)
    suite_metadata: dict[str, object] = field(default_factory=dict)

    @property
    def overall_pass_rate(self) -> float:
        """Return the unweighted mean pass rate across replay tasks."""
        if not self.task_results:
            return 0.0
        return sum(result.overall_pass_rate for result in self.task_results) / len(
            self.task_results
        )

    @property
    def n_tasks(self) -> int:
        """Return the number of replayed tasks."""
        return len(self.task_results)

    @property
    def n_cases(self) -> int:
        """Return the total number of replayed cases."""
        return sum(len(result.case_results) for result in self.task_results)

    @property
    def n_errors(self) -> int:
        """Return the total operational errors across the report."""
        return sum(result.n_errors for result in self.task_results)

    @property
    def usage_totals(self) -> dict[str, int]:
        """Sum provider-reported token usage across calls when available."""
        totals = {
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "cache_write_input_tokens": 0,
            "output_tokens": 0,
            "reasoning_output_tokens": 0,
        }
        for task in self.task_results:
            for case in task.case_results:
                for metadata in case.backend_metadata:
                    usage = metadata.get("usage")
                    if not isinstance(usage, dict):
                        continue
                    for key in totals:
                        value = usage.get(key)
                        if isinstance(value, int) and not isinstance(value, bool):
                            totals[key] += value
        return totals

    def to_dict(self) -> dict[str, object]:
        """Return the replay report and its evidence as serializable data."""
        return {
            "schema_version": REPLAY_REPORT_SCHEMA_VERSION,
            "task_type": self.task_type.value,
            "backend_name": self.backend_name,
            "n_trials": self.n_trials,
            "instruction_sha256": self.instruction_sha256,
            "suite_sha256": self.suite_sha256,
            "generated_at_utc": self.generated_at_utc,
            "runtime_config": self.runtime_config,
            "suite_metadata": self.suite_metadata,
            "overall_pass_rate": self.overall_pass_rate,
            "n_tasks": self.n_tasks,
            "n_cases": self.n_cases,
            "n_errors": self.n_errors,
            "usage_totals": self.usage_totals,
            "task_results": [result.to_dict() for result in self.task_results],
        }


@dataclass(frozen=True)
class ReplayComparisonReport:
    """Paired original/candidate replay with a reproducible call order."""

    task_type: TaskType
    original: ReplayReport
    candidate: ReplayReport
    seed: int

    @property
    def delta(self) -> float:
        """Return candidate pass rate minus original pass rate."""
        return self.candidate.overall_pass_rate - self.original.overall_pass_rate

    def to_dict(self) -> dict[str, object]:
        """Return paired replay evidence as a serializable mapping."""
        return {
            "schema_version": REPLAY_REPORT_SCHEMA_VERSION,
            "task_type": self.task_type.value,
            "seed": self.seed,
            "n_trials": self.original.n_trials,
            "suite_sha256": self.original.suite_sha256,
            "generated_at_utc": self.original.generated_at_utc,
            "runtime_config": self.original.runtime_config,
            "suite_metadata": self.original.suite_metadata,
            "delta": self.delta,
            "original": self.original.to_dict(),
            "candidate": self.candidate.to_dict(),
        }


@dataclass
class _CaseAccumulator:
    outputs: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    backend_metadata: list[dict[str, object]] = field(default_factory=list)
    n_passed: int = 0


@dataclass(frozen=True)
class _RunUnit:
    side: str
    task_index: int
    case_index: int
    trial_index: int


@dataclass(frozen=True)
class ReplayProgress:
    """One completed backend call in a replay schedule."""

    completed_calls: int
    total_calls: int
    side: str
    task_name: str
    case_name: str
    trial_index: int
    n_trials: int


def _validate_tasks(tasks: list[ReplayTask], task_type: TaskType) -> None:
    names = [task.name for task in tasks]
    if len(names) != len(set(names)):
        raise ValueError("Replay task names must be unique")
    for task in tasks:
        if task.task_type != task_type:
            raise ValueError(
                f"Replay task {task.name!r} has type {task.task_type.value!r}; "
                f"expected {task_type.value!r}"
            )


def _build_report(
    *,
    side: str,
    task_type: TaskType,
    tasks: list[ReplayTask],
    accumulators: dict[tuple[str, int, int], _CaseAccumulator],
    n_trials: int,
    backend_name: str,
    instruction_text: str,
    suite_sha256: str,
    generated_at_utc: str,
    runtime_config: dict[str, object],
    suite_metadata: dict[str, object],
) -> ReplayReport:
    task_results: list[ReplayTaskResult] = []
    for task_index, task in enumerate(tasks):
        case_results: list[ReplayCaseResult] = []
        for case_index, case in enumerate(task.cases):
            observed = accumulators[(side, task_index, case_index)]
            case_results.append(
                ReplayCaseResult(
                    case_name=case.name,
                    category=case.category,
                    n_trials=n_trials,
                    n_passed=observed.n_passed,
                    outputs=tuple(observed.outputs),
                    errors=tuple(observed.errors),
                    backend_metadata=tuple(observed.backend_metadata),
                )
            )
        task_results.append(
            ReplayTaskResult(
                task_name=task.name,
                case_results=tuple(case_results),
                pass_threshold=task.pass_threshold,
            )
        )
    return ReplayReport(
        task_type=task_type,
        task_results=tuple(task_results),
        backend_name=backend_name,
        n_trials=n_trials,
        instruction_sha256=_text_sha256(instruction_text),
        suite_sha256=suite_sha256,
        generated_at_utc=generated_at_utc,
        runtime_config=runtime_config,
        suite_metadata=suite_metadata,
    )


def _text_sha256(text: str) -> str:
    """Hash decoded instruction text with platform-neutral line endings."""
    canonical = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _suite_sha256(tasks: list[ReplayTask], suite: ReplaySuite | None = None) -> str:
    canonical: object
    if suite is None or suite.schema_version == LEGACY_REPLAY_SUITE_SCHEMA_VERSION:
        canonical = [task.to_dict() for task in tasks]
    else:
        canonical = suite.to_dict()
    payload = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _backend_metadata(backend: Backend) -> dict[str, object]:
    raw = getattr(backend, "last_call_metadata", None)
    if not isinstance(raw, dict):
        return {}
    try:
        normalized = json.loads(json.dumps(raw, ensure_ascii=False))
    except (TypeError, ValueError):
        return {}
    return normalized if isinstance(normalized, dict) else {}


def _backend_runtime_config(backend: Backend) -> dict[str, object]:
    """Snapshot an optional backend config without accepting sensitive fields."""
    try:
        raw = getattr(backend, "runtime_config", None)
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}

    config: dict[str, object] = {}
    for key in _RUNTIME_CONFIG_STRING_KEYS:
        value = raw.get(key)
        if isinstance(value, str) and value:
            config[key] = value
        elif key == "codex_cli_version" and key in raw and value is None:
            config[key] = None
    for key in _RUNTIME_CONFIG_BOOL_KEYS:
        value = raw.get(key)
        if isinstance(value, bool):
            config[key] = value
    timeout = raw.get("timeout_seconds")
    if isinstance(timeout, (int, float)) and not isinstance(timeout, bool) and timeout > 0:
        config["timeout_seconds"] = timeout
    disabled_features = raw.get("disabled_features")
    if isinstance(disabled_features, (list, tuple)) and all(
        isinstance(value, str) and value for value in disabled_features
    ):
        config["disabled_features"] = list(disabled_features)
    return config


def _execute_schedule(
    *,
    texts: dict[str, str],
    task_type: TaskType,
    tasks: list[ReplayTask],
    backend: Backend,
    n_trials: int,
    schedule: list[_RunUnit],
    suite_sha256: str,
    suite_metadata: dict[str, object],
    on_progress: Callable[[ReplayProgress], None] | None = None,
) -> dict[str, ReplayReport]:
    generated_at_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    runtime_config = _backend_runtime_config(backend)
    accumulators = {
        (side, task_index, case_index): _CaseAccumulator()
        for side in texts
        for task_index, task in enumerate(tasks)
        for case_index, _case in enumerate(task.cases)
    }

    for completed_calls, unit in enumerate(schedule, start=1):
        task = tasks[unit.task_index]
        case = task.cases[unit.case_index]
        observed = accumulators[(unit.side, unit.task_index, unit.case_index)]
        try:
            output = backend.complete(
                system=texts[unit.side],
                user=case.prompt,
                max_tokens=task.max_tokens,
            )
        except Exception as exc:
            error_type = type(exc).__name__
            logger.warning(
                "Replay failed on %s/%s (%s)",
                task.name,
                case.name,
                error_type,
            )
            observed.outputs.append("")
            observed.errors.append(error_type)
            observed.backend_metadata.append(_backend_metadata(backend))
        else:
            observed.outputs.append(output)
            observed.backend_metadata.append(_backend_metadata(backend))
            if case.matches(output):
                observed.n_passed += 1
        if on_progress is not None:
            on_progress(
                ReplayProgress(
                    completed_calls=completed_calls,
                    total_calls=len(schedule),
                    side=unit.side,
                    task_name=task.name,
                    case_name=case.name,
                    trial_index=unit.trial_index,
                    n_trials=n_trials,
                )
            )

    return {
        side: _build_report(
            side=side,
            task_type=task_type,
            tasks=tasks,
            accumulators=accumulators,
            n_trials=n_trials,
            backend_name=backend.name,
            instruction_text=texts[side],
            suite_sha256=suite_sha256,
            generated_at_utc=generated_at_utc,
            runtime_config=runtime_config,
            suite_metadata=suite_metadata,
        )
        for side in texts
    }


def _prepare_suite(
    suite_or_tasks: ReplaySuite | list[ReplayTask],
    *,
    task_type: TaskType,
    original: str,
    candidate: str | None = None,
) -> tuple[list[ReplayTask], str, dict[str, object]]:
    if isinstance(suite_or_tasks, ReplaySuite):
        suite: ReplaySuite | None = suite_or_tasks
        tasks = list(suite_or_tasks.tasks)
    else:
        suite = None
        tasks = suite_or_tasks
    _validate_tasks(tasks, task_type)
    if suite is not None:
        suite.validate_assets(original, candidate)
    return tasks, _suite_sha256(tasks, suite), {} if suite is None else suite.report_metadata


def replay(
    text: str,
    *,
    task_type: TaskType | str,
    tasks: ReplaySuite | list[ReplayTask],
    backend: Backend,
    n_trials: int = 1,
    on_progress: Callable[[ReplayProgress], None] | None = None,
) -> ReplayReport:
    """Run deterministic behavior cases against one instruction asset."""
    if not text or not text.strip():
        raise ValueError("Cannot replay an empty instruction asset")
    if n_trials < 1:
        raise ValueError("n_trials must be >= 1")
    tt = task_type if isinstance(task_type, TaskType) else TaskType.parse(task_type)
    replay_tasks, suite_sha256, suite_metadata = _prepare_suite(
        tasks,
        task_type=tt,
        original=text,
    )
    schedule = [
        _RunUnit("single", task_index, case_index, trial_index)
        for task_index, task in enumerate(replay_tasks)
        for case_index, _case in enumerate(task.cases)
        for trial_index in range(1, n_trials + 1)
    ]
    return _execute_schedule(
        texts={"single": text},
        task_type=tt,
        tasks=replay_tasks,
        backend=backend,
        n_trials=n_trials,
        schedule=schedule,
        suite_sha256=suite_sha256,
        suite_metadata=suite_metadata,
        on_progress=on_progress,
    )["single"]


def compare_replay(
    *,
    original: str,
    candidate: str,
    task_type: TaskType | str,
    tasks: ReplaySuite | list[ReplayTask],
    backend: Backend,
    n_trials: int = 1,
    seed: int = 0,
    on_progress: Callable[[ReplayProgress], None] | None = None,
) -> ReplayComparisonReport:
    """Replay original and candidate with a paired, randomized call order."""
    if not original or not original.strip():
        raise ValueError("Cannot replay an empty original instruction asset")
    if not candidate or not candidate.strip():
        raise ValueError("Cannot replay an empty candidate instruction asset")
    if n_trials < 1:
        raise ValueError("n_trials must be >= 1")
    tt = task_type if isinstance(task_type, TaskType) else TaskType.parse(task_type)
    replay_tasks, suite_sha256, suite_metadata = _prepare_suite(
        tasks,
        task_type=tt,
        original=original,
        candidate=candidate,
    )

    schedule = [
        _RunUnit(side, task_index, case_index, trial_index)
        for task_index, task in enumerate(replay_tasks)
        for case_index, _case in enumerate(task.cases)
        for trial_index in range(1, n_trials + 1)
        for side in ("original", "candidate")
    ]
    random.Random(seed).shuffle(schedule)
    reports = _execute_schedule(
        texts={"original": original, "candidate": candidate},
        task_type=tt,
        tasks=replay_tasks,
        backend=backend,
        n_trials=n_trials,
        schedule=schedule,
        suite_sha256=suite_sha256,
        suite_metadata=suite_metadata,
        on_progress=on_progress,
    )
    return ReplayComparisonReport(
        task_type=tt,
        original=reports["original"],
        candidate=reports["candidate"],
        seed=seed,
    )


def load_replay_suite(path: str | Path) -> ReplaySuite:
    """Load a versioned replay suite, retaining holdout freeze evidence."""
    source = Path(path)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not load replay suite {source}: {type(exc).__name__}") from exc

    if isinstance(data, dict) and "tasks" in data:
        schema_version = data.get("schema_version")
        if schema_version not in {
            LEGACY_REPLAY_SUITE_SCHEMA_VERSION,
            REPLAY_SUITE_SCHEMA_VERSION,
        }:
            raise ValueError(
                f"Unsupported replay suite schema {schema_version!r}; "
                f"expected {LEGACY_REPLAY_SUITE_SCHEMA_VERSION!r} or "
                f"{REPLAY_SUITE_SCHEMA_VERSION!r}"
            )
        raw_tasks = data["tasks"]
    else:
        schema_version = LEGACY_REPLAY_SUITE_SCHEMA_VERSION
        raw_tasks = data if isinstance(data, list) else [data]
    if not raw_tasks or not all(isinstance(item, dict) for item in raw_tasks):
        raise ValueError("Replay suite must contain one task object or a list of task objects")
    try:
        parsed_tasks = tuple(ReplayTask.from_dict(item) for item in raw_tasks)
        if schema_version == REPLAY_SUITE_SCHEMA_VERSION:
            if not isinstance(data, dict):
                raise ValueError("Replay suite v2 must be a JSON object")
            raw_role = data.get("suite_role")
            if not isinstance(raw_role, str):
                raise ValueError("Replay suite v2 suite_role must be a string")
            role = ReplaySuiteRole(raw_role)
            raw_freeze = data.get("freeze")
            raw_authoring = data.get("authoring")
            freeze = (
                ReplaySuiteFreeze.from_dict(raw_freeze) if isinstance(raw_freeze, dict) else None
            )
            authoring = (
                ReplaySuiteAuthoring.from_dict(raw_authoring)
                if isinstance(raw_authoring, dict)
                else None
            )
            return ReplaySuite(
                tasks=parsed_tasks,
                role=role,
                freeze=freeze,
                authoring=authoring,
                schema_version=schema_version,
            )
        return ReplaySuite(
            tasks=parsed_tasks,
            schema_version=LEGACY_REPLAY_SUITE_SCHEMA_VERSION,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid replay suite {source}: {exc}") from exc


def load_replay_tasks(path: str | Path) -> list[ReplayTask]:
    """Load tasks from any supported replay suite without metadata."""
    return list(load_replay_suite(path).tasks)


__all__ = [
    "MatchMode",
    "LEGACY_REPLAY_SUITE_SCHEMA_VERSION",
    "REPLAY_REPORT_SCHEMA_VERSION",
    "REPLAY_SUITE_SCHEMA_VERSION",
    "ReplayCase",
    "ReplayCaseResult",
    "ReplayCategory",
    "ReplayComparisonReport",
    "ReplayReport",
    "ReplaySuite",
    "ReplaySuiteAuthoring",
    "ReplaySuiteFreeze",
    "ReplaySuiteRole",
    "ReplayTask",
    "ReplayTaskResult",
    "compare_replay",
    "load_replay_suite",
    "load_replay_tasks",
    "replay",
]
