"""Contract-first verification for candidate instruction assets.

`verify` combines deterministic preservation checks with optional,
caller-supplied behavior tasks. It never treats a model judge as proof that a
missing literal or changed metadata is safe.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from denser.backends import Backend
from denser.eval import ComparisonReport, EvalReport, GoldenTask
from denser.eval import compare as compare_fn
from denser.eval import evaluate as evaluate_fn
from denser.inspection import (
    ContractCategory,
    ContractItem,
    InspectionReport,
    PreservationContract,
)
from denser.inspection import inspect as inspect_fn
from denser.replay import ReplayComparisonReport, ReplayTask
from denser.replay import compare_replay as compare_replay_fn
from denser.taxonomy import TaskType
from denser.tokens import estimate_tokens


class VerificationStatus(str, Enum):
    """Coverage state for one source-backed contract item."""

    PASS = "pass"
    REVIEW = "review"
    FAIL = "fail"


class VerificationDecision(str, Enum):
    """Overall disposition for a candidate."""

    PASS = "pass"
    REVIEW = "review"
    REJECT = "reject"


@dataclass(frozen=True)
class ContractItemResult:
    """Evidence found for one preservation obligation."""

    item_id: str
    status: VerificationStatus
    evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return this obligation result as a serializable mapping."""
        return {
            "item_id": self.item_id,
            "status": self.status.value,
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class BehaviorTaskResult:
    """Paired outcome for one explicitly supplied behavior task."""

    task_name: str
    covers: tuple[str, ...]
    original_pass_rate: float
    candidate_pass_rate: float
    pass_threshold: float
    passed: bool
    error_count: int
    evaluation_mode: str = "judge"

    def to_dict(self) -> dict[str, object]:
        """Return paired behavior evidence as a serializable mapping."""
        return {
            "task_name": self.task_name,
            "covers": list(self.covers),
            "original_pass_rate": self.original_pass_rate,
            "candidate_pass_rate": self.candidate_pass_rate,
            "pass_threshold": self.pass_threshold,
            "passed": self.passed,
            "error_count": self.error_count,
            "evaluation_mode": self.evaluation_mode,
        }


@dataclass(frozen=True)
class VerificationReport:
    """Reviewable result of verifying one candidate against its source."""

    task_type: TaskType
    decision: VerificationDecision
    original_tokens: int
    candidate_tokens: int
    contract: PreservationContract
    item_results: tuple[ContractItemResult, ...]
    missing_literals: tuple[str, ...] = ()
    behavior_results: tuple[BehaviorTaskResult, ...] = ()
    replay_evidence: ReplayComparisonReport | None = None
    failures: tuple[str, ...] = ()
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def actual_density(self) -> float:
        """Return the candidate-to-original estimated token ratio."""
        if self.original_tokens == 0:
            return 1.0
        return self.candidate_tokens / self.original_tokens

    @property
    def passed(self) -> bool:
        """Return whether the overall verification decision is pass."""
        return self.decision == VerificationDecision.PASS

    @property
    def review_count(self) -> int:
        """Return the number of obligations requiring human review."""
        return sum(result.status == VerificationStatus.REVIEW for result in self.item_results)

    @property
    def failed_item_count(self) -> int:
        """Return the number of obligations with failed evidence."""
        return sum(result.status == VerificationStatus.FAIL for result in self.item_results)

    def to_dict(self) -> dict[str, object]:
        """Return the verification decision and evidence as serializable data."""
        return {
            "task_type": self.task_type.value,
            "decision": self.decision.value,
            "passed": self.passed,
            "original_tokens": self.original_tokens,
            "candidate_tokens": self.candidate_tokens,
            "actual_density": self.actual_density,
            "review_count": self.review_count,
            "failed_item_count": self.failed_item_count,
            "missing_literals": list(self.missing_literals),
            "failures": list(self.failures),
            "warnings": list(self.warnings),
            "contract": self.contract.to_dict(),
            "item_results": [result.to_dict() for result in self.item_results],
            "behavior_results": [result.to_dict() for result in self.behavior_results],
            "replay_evidence": (
                None if self.replay_evidence is None else self.replay_evidence.to_dict()
            ),
        }


_WHITESPACE_RE = re.compile(r"\s+")


def _normalized(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text.replace("\r\n", "\n")).strip().casefold()


def _frontmatter_text(text: str) -> str | None:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[: index + 1])
    return "\n".join(lines)


def _behavior_results(
    comparison: ComparisonReport,
    tasks: list[GoldenTask],
) -> tuple[BehaviorTaskResult, ...]:
    results: list[BehaviorTaskResult] = []
    for task, original, candidate in zip(
        tasks,
        comparison.original.task_results,
        comparison.compressed.task_results,
        strict=True,
    ):
        error_count = original.n_errors + candidate.n_errors
        passed = (
            error_count == 0
            and candidate.passed
            and candidate.overall_pass_rate >= original.overall_pass_rate
        )
        results.append(
            BehaviorTaskResult(
                task_name=task.name,
                covers=task.covers,
                original_pass_rate=original.overall_pass_rate,
                candidate_pass_rate=candidate.overall_pass_rate,
                pass_threshold=candidate.pass_threshold,
                passed=passed,
                error_count=error_count,
                evaluation_mode="judge",
            )
        )
    return tuple(results)


def _replay_results(
    comparison: ReplayComparisonReport,
    tasks: list[ReplayTask],
) -> tuple[BehaviorTaskResult, ...]:
    results: list[BehaviorTaskResult] = []
    for task, original, candidate in zip(
        tasks,
        comparison.original.task_results,
        comparison.candidate.task_results,
        strict=True,
    ):
        error_count = original.n_errors + candidate.n_errors
        passed = (
            error_count == 0
            and candidate.passed
            and candidate.overall_pass_rate >= original.overall_pass_rate
        )
        results.append(
            BehaviorTaskResult(
                task_name=task.name,
                covers=task.covers,
                original_pass_rate=original.overall_pass_rate,
                candidate_pass_rate=candidate.overall_pass_rate,
                pass_threshold=candidate.pass_threshold,
                passed=passed,
                error_count=error_count,
                evaluation_mode="replay",
            )
        )
    return tuple(results)


def _validate_tasks(tasks: list[GoldenTask], contract: PreservationContract) -> None:
    names = [task.name for task in tasks]
    if len(names) != len(set(names)):
        raise ValueError("Behavior task names must be unique")

    item_ids = {item.item_id for item in contract.items}
    for task in tasks:
        if task.task_type != contract.task_type:
            raise ValueError(
                f"Behavior task {task.name!r} has type {task.task_type.value!r}; "
                f"expected {contract.task_type.value!r}"
            )
        unknown = set(task.covers) - item_ids
        if unknown:
            formatted = ", ".join(sorted(unknown))
            raise ValueError(
                f"Behavior task {task.name!r} covers unknown contract items: {formatted}"
            )


def _validate_replay_tasks(
    tasks: list[ReplayTask],
    contract: PreservationContract,
) -> None:
    names = [task.name for task in tasks]
    if len(names) != len(set(names)):
        raise ValueError("Replay task names must be unique")

    item_ids = {item.item_id for item in contract.items}
    for task in tasks:
        if task.task_type != contract.task_type:
            raise ValueError(
                f"Replay task {task.name!r} has type {task.task_type.value!r}; "
                f"expected {contract.task_type.value!r}"
            )
        unknown = set(task.covers) - item_ids
        if unknown:
            formatted = ", ".join(sorted(unknown))
            raise ValueError(
                f"Replay task {task.name!r} covers unknown contract items: {formatted}"
            )


@dataclass(frozen=True)
class _CandidateFacts:
    normalized_text: str
    unchanged: bool
    metadata_preserved: bool
    missing_literals: tuple[str, ...]
    failures: tuple[str, ...]


def _candidate_facts(
    original: str,
    candidate: str,
    contract: PreservationContract,
) -> _CandidateFacts:
    failures: list[str] = []
    if not candidate or not candidate.strip():
        failures.append("Candidate is empty.")

    original_normalized = _normalized(original)
    candidate_normalized = _normalized(candidate)
    missing_literals = tuple(
        literal for literal in contract.protected_literals if literal not in candidate
    )
    if missing_literals:
        failures.append(f"Candidate is missing {len(missing_literals)} protected literal(s).")

    original_frontmatter = _frontmatter_text(original)
    metadata_preserved = original_frontmatter == _frontmatter_text(candidate)
    if original_frontmatter is not None and not metadata_preserved:
        failures.append("YAML front matter changed or is missing.")

    return _CandidateFacts(
        normalized_text=candidate_normalized,
        unchanged=original_normalized == candidate_normalized,
        metadata_preserved=metadata_preserved,
        missing_literals=missing_literals,
        failures=tuple(failures),
    )


def _run_behavior_tasks(
    original: str,
    candidate: str,
    task_type: TaskType,
    tasks: list[GoldenTask],
    judge_backend: Backend | None,
    n_trials: int,
    baseline_report: EvalReport | None,
) -> tuple[tuple[BehaviorTaskResult, ...], tuple[str, ...]]:
    if not tasks:
        return (), ()

    if baseline_report is None:
        comparison = compare_fn(
            original=original,
            compressed=candidate,
            task_type=task_type,
            golden_tasks=tasks,
            judge_backend=judge_backend,
            n_trials=n_trials,
        )
    else:
        candidate_report = evaluate_fn(
            candidate,
            task_type=task_type,
            golden_tasks=tasks,
            judge_backend=judge_backend,
            n_trials=n_trials,
        )
        comparison = ComparisonReport(
            task_type=task_type,
            original=baseline_report,
            compressed=candidate_report,
        )
    results = _behavior_results(comparison, tasks)
    failures: list[str] = []
    for result in results:
        if result.error_count:
            failures.append(
                f"Behavior task {result.task_name!r} had {result.error_count} operational error(s)."
            )
        elif not result.passed:
            failures.append(f"Behavior task {result.task_name!r} failed or regressed.")
    return results, tuple(failures)


def _run_replay_tasks(
    original: str,
    candidate: str,
    task_type: TaskType,
    tasks: list[ReplayTask],
    execution_backend: Backend | None,
    n_trials: int,
    seed: int,
) -> tuple[
    tuple[BehaviorTaskResult, ...],
    tuple[str, ...],
    ReplayComparisonReport | None,
]:
    if not tasks:
        return (), (), None
    if execution_backend is None:
        raise ValueError("execution_backend is required when replay_tasks are supplied")

    comparison = compare_replay_fn(
        original=original,
        candidate=candidate,
        task_type=task_type,
        tasks=tasks,
        backend=execution_backend,
        n_trials=n_trials,
        seed=seed,
    )
    results = _replay_results(comparison, tasks)
    failures: list[str] = []
    for result in results:
        if result.error_count:
            failures.append(
                f"Replay task {result.task_name!r} had {result.error_count} operational error(s)."
            )
        elif not result.passed:
            failures.append(f"Replay task {result.task_name!r} failed or regressed.")
    return results, tuple(failures), comparison


def _task_coverage(
    results: tuple[BehaviorTaskResult, ...],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    passing: dict[str, list[str]] = {}
    failing: dict[str, list[str]] = {}
    for result in results:
        target = passing if result.passed else failing
        for item_id in result.covers:
            target.setdefault(item_id, []).append(result.task_name)
    return passing, failing


def _verify_item(
    item: ContractItem,
    candidate: str,
    facts: _CandidateFacts,
    passing_tasks: dict[str, list[str]],
    failing_tasks: dict[str, list[str]],
) -> ContractItemResult:
    missing_literals = tuple(
        literal for literal in item.protected_literals if literal not in candidate
    )
    status = VerificationStatus.REVIEW
    evidence = "changed obligation has no deterministic or behavior evidence"

    if facts.unchanged:
        status, evidence = VerificationStatus.PASS, "source unchanged"
    elif ContractCategory.METADATA in item.categories and not facts.metadata_preserved:
        status, evidence = VerificationStatus.FAIL, "metadata changed or missing"
    elif missing_literals:
        status = VerificationStatus.FAIL
        evidence = "missing protected literals: " + ", ".join(missing_literals)
    elif _normalized(item.statement) in facts.normalized_text:
        status, evidence = VerificationStatus.PASS, "obligation retained verbatim"
    elif ContractCategory.METADATA in item.categories and facts.metadata_preserved:
        status, evidence = VerificationStatus.PASS, "metadata retained verbatim"
    elif set(item.categories) == {ContractCategory.PROTECTED_LITERAL}:
        status, evidence = VerificationStatus.PASS, "all literals from this item are present"
    elif item.item_id in passing_tasks:
        status = VerificationStatus.PASS
        evidence = "covered by passing behavior task(s): " + ", ".join(passing_tasks[item.item_id])
    elif item.item_id in failing_tasks:
        status = VerificationStatus.FAIL
        evidence = "covered only by failing behavior task(s): " + ", ".join(
            failing_tasks[item.item_id]
        )

    return ContractItemResult(item_id=item.item_id, status=status, evidence=(evidence,))


def _verify_items(
    contract: PreservationContract,
    candidate: str,
    facts: _CandidateFacts,
    behavior_results: tuple[BehaviorTaskResult, ...],
) -> tuple[ContractItemResult, ...]:
    passing_tasks, failing_tasks = _task_coverage(behavior_results)
    return tuple(
        _verify_item(item, candidate, facts, passing_tasks, failing_tasks)
        for item in contract.items
    )


def _decision(
    failures: tuple[str, ...],
    item_results: tuple[ContractItemResult, ...],
) -> VerificationDecision:
    statuses = {result.status for result in item_results}
    if failures or VerificationStatus.FAIL in statuses:
        return VerificationDecision.REJECT
    if VerificationStatus.REVIEW in statuses:
        return VerificationDecision.REVIEW
    return VerificationDecision.PASS


def _validate_baseline(
    baseline_report: EvalReport | None,
    tasks: list[GoldenTask],
    task_type: TaskType,
    n_trials: int,
) -> None:
    if baseline_report is None:
        return
    if not tasks:
        raise ValueError("baseline_report requires behavior_tasks")
    if baseline_report.task_type != task_type:
        raise ValueError("baseline_report task type does not match verification task type")
    expected_names = [task.name for task in tasks]
    actual_names = [result.task_name for result in baseline_report.task_results]
    if actual_names != expected_names:
        raise ValueError("baseline_report tasks do not match behavior_tasks")
    if any(
        case.n_trials != n_trials
        for task_result in baseline_report.task_results
        for case in task_result.case_results
    ):
        raise ValueError("baseline_report trial count does not match n_trials")


def verify(
    original: str,
    candidate: str,
    *,
    task_type: TaskType | str,
    inspection: InspectionReport | None = None,
    behavior_tasks: list[GoldenTask] | None = None,
    judge_backend: Backend | None = None,
    replay_tasks: list[ReplayTask] | None = None,
    execution_backend: Backend | None = None,
    n_trials: int = 1,
    baseline_report: EvalReport | None = None,
    replay_seed: int = 0,
) -> VerificationReport:
    """Verify a candidate against a source-backed preservation contract.

    Without behavior tasks, changed obligations that cannot be checked
    deterministically remain in `review` rather than being guessed as safe.
    Judge-based behavior tasks can cover specific contract item IDs through
    `GoldenTask.covers`. Deterministic `replay_tasks` run the asset as system
    instructions against realistic user prompts through `execution_backend`.
    `baseline_report` lets multi-candidate callers reuse a single judged
    evaluation of the original.
    """
    if not original or not original.strip():
        raise ValueError("Cannot verify an empty original")
    if n_trials < 1:
        raise ValueError("n_trials must be >= 1")

    tt = task_type if isinstance(task_type, TaskType) else TaskType.parse(task_type)
    inspection_report = inspection or inspect_fn(original, task_type=tt, min_tokens=1)
    contract = inspection_report.contract
    if contract.task_type != tt:
        raise ValueError(
            f"Inspection contract type {contract.task_type.value!r} does not match {tt.value!r}"
        )

    tasks = list(behavior_tasks or [])
    replay_suite = list(replay_tasks or [])
    _validate_tasks(tasks, contract)
    _validate_replay_tasks(replay_suite, contract)
    duplicate_names = {task.name for task in tasks} & {task.name for task in replay_suite}
    if duplicate_names:
        formatted = ", ".join(sorted(duplicate_names))
        raise ValueError(f"Behavior and replay task names must be distinct: {formatted}")
    _validate_baseline(baseline_report, tasks, tt, n_trials)
    facts = _candidate_facts(original, candidate, contract)
    behavior_results, behavior_failures = _run_behavior_tasks(
        original,
        candidate,
        tt,
        tasks,
        judge_backend,
        n_trials,
        baseline_report,
    )
    replay_results, replay_failures, replay_evidence = _run_replay_tasks(
        original,
        candidate,
        tt,
        replay_suite,
        execution_backend,
        n_trials,
        replay_seed,
    )
    behavior_results = behavior_results + replay_results
    failures = facts.failures + behavior_failures + replay_failures
    item_results = _verify_items(contract, candidate, facts, behavior_results)
    decision = _decision(failures, item_results)

    warnings = list(inspection_report.warnings)
    if not tasks and not replay_suite and not facts.unchanged:
        warnings.append(
            "No behavior tasks were supplied; semantic rewrites cannot pass automatically."
        )

    return VerificationReport(
        task_type=tt,
        decision=decision,
        original_tokens=estimate_tokens(original),
        candidate_tokens=estimate_tokens(candidate),
        contract=contract,
        item_results=item_results,
        missing_literals=facts.missing_literals,
        behavior_results=behavior_results,
        replay_evidence=replay_evidence,
        failures=failures,
        warnings=tuple(warnings),
    )


__all__ = [
    "BehaviorTaskResult",
    "ContractItemResult",
    "VerificationDecision",
    "VerificationReport",
    "VerificationStatus",
    "verify",
]
