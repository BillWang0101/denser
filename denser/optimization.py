"""Multi-candidate optimization with contract-first selection.

The original is always candidate zero. Generated candidates compete on length
only after they pass every verification gate.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from denser.backends import Backend, BackendError, ClaudeBackend
from denser.compress import compress
from denser.eval import DEFAULT_JUDGE_MODEL, EvalReport, GoldenTask
from denser.eval import evaluate as evaluate_fn
from denser.inspection import InspectionAction, InspectionReport
from denser.inspection import inspect as inspect_fn
from denser.taxonomy import TaskType, get_spec
from denser.tokens import HeuristicTokenCounter, TokenCounter, TokenCountError
from denser.verification import VerificationReport, _validate_tasks, verify

EVIDENCE_SCHEMA_VERSION = "denser.optimization-report/v1"


class CandidateKind(str, Enum):
    """Origin of an optimization candidate."""

    ORIGINAL = "original"
    GENERATED = "generated"


@dataclass(frozen=True)
class OptimizationCandidate:
    """One original or generated candidate and its evidence."""

    candidate_id: str
    kind: CandidateKind
    text: str | None
    requested_density: float | None
    token_count: int | None
    actual_density: float | None
    backend_name: str | None
    rationale: str
    verification: VerificationReport | None
    generation_error: str | None = None
    measurement_error: str | None = None
    generation_latency_ms: float = 0.0
    verification_latency_ms: float = 0.0

    @property
    def eligible(self) -> bool:
        """Return whether verification permits this candidate to be selected."""
        return self.verification is not None and self.verification.passed

    def to_dict(self, *, include_text: bool = True) -> dict[str, object]:
        """Return candidate evidence, optionally including the candidate text."""
        data: dict[str, object] = {
            "candidate_id": self.candidate_id,
            "kind": self.kind.value,
            "requested_density": self.requested_density,
            "token_count": self.token_count,
            "actual_density": self.actual_density,
            "backend_name": self.backend_name,
            "rationale": self.rationale,
            "eligible": self.eligible,
            "generation_error": self.generation_error,
            "measurement_error": self.measurement_error,
            "generation_latency_ms": self.generation_latency_ms,
            "verification_latency_ms": self.verification_latency_ms,
            "verification": self.verification.to_dict() if self.verification else None,
        }
        if include_text:
            data["text"] = self.text
        return data


@dataclass(frozen=True)
class OptimizationReport:
    """Versioned, serializable evidence for one optimization run."""

    task_type: TaskType
    source_name: str
    source_sha256: str
    created_at: str
    duration_ms: float
    inspection: InspectionReport
    candidates: tuple[OptimizationCandidate, ...]
    recommended_candidate_id: str
    recommendation_reason: str
    generation_backend: str | None
    judge_backend: str | None
    token_count_method: str
    token_count_provider: str | None
    token_count_model: str | None
    token_count_exact: bool
    logical_generation_calls: int
    logical_judge_calls: int
    logical_token_count_calls: int
    warnings: tuple[str, ...] = field(default_factory=tuple)
    schema_version: str = EVIDENCE_SCHEMA_VERSION

    @property
    def recommended(self) -> OptimizationCandidate:
        """Return the candidate selected by the optimization report."""
        return next(
            candidate
            for candidate in self.candidates
            if candidate.candidate_id == self.recommended_candidate_id
        )

    @property
    def changed(self) -> bool:
        """Return whether the recommendation differs from the original text."""
        return self.recommended.kind == CandidateKind.GENERATED

    def to_dict(self, *, include_text: bool = True) -> dict[str, object]:
        """Return the complete optimization evidence as serializable data."""
        return {
            "schema_version": self.schema_version,
            "task_type": self.task_type.value,
            "source_name": self.source_name,
            "source_sha256": self.source_sha256,
            "created_at": self.created_at,
            "duration_ms": self.duration_ms,
            "recommended_candidate_id": self.recommended_candidate_id,
            "recommendation_reason": self.recommendation_reason,
            "changed": self.changed,
            "generation_backend": self.generation_backend,
            "judge_backend": self.judge_backend,
            "token_count_method": self.token_count_method,
            "token_count_provider": self.token_count_provider,
            "token_count_model": self.token_count_model,
            "token_count_exact": self.token_count_exact,
            "logical_generation_calls": self.logical_generation_calls,
            "logical_judge_calls": self.logical_judge_calls,
            "logical_token_count_calls": self.logical_token_count_calls,
            "warnings": list(self.warnings),
            "inspection": self.inspection.to_dict(),
            "candidates": [
                candidate.to_dict(include_text=include_text) for candidate in self.candidates
            ],
        }


def _densities(task_type: TaskType, requested: tuple[float, ...] | None) -> tuple[float, ...]:
    if requested is None:
        low, high = get_spec(task_type).density_range
        requested = (low, round((low + high) / 2, 3), high)
    if not requested:
        raise ValueError("target_densities must not be empty")
    if any(not 0.0 < density <= 1.0 for density in requested):
        raise ValueError("target_densities must all be in (0, 1]")
    return tuple(dict.fromkeys(requested))


def _logical_eval_calls(tasks: list[GoldenTask], n_trials: int) -> int:
    return sum(len(task.test_cases) for task in tasks) * n_trials


def _counter_for(
    inspection: InspectionReport,
    requested: TokenCounter | None,
) -> TokenCounter:
    if inspection.action == InspectionAction.KEEP:
        return HeuristicTokenCounter()
    return requested or HeuristicTokenCounter()


def _original_candidate(
    text: str,
    task_type: TaskType,
    inspection: InspectionReport,
    token_count: int,
) -> OptimizationCandidate:
    verification = verify(
        text,
        text,
        task_type=task_type,
        inspection=inspection,
    )
    return OptimizationCandidate(
        candidate_id="original",
        kind=CandidateKind.ORIGINAL,
        text=text,
        requested_density=None,
        token_count=token_count,
        actual_density=1.0,
        backend_name=None,
        rationale="Original source retained as the safe baseline.",
        verification=verification,
    )


def _report(
    *,
    started_at: float,
    task_type: TaskType,
    source_name: str,
    text: str,
    inspection: InspectionReport,
    candidates: list[OptimizationCandidate],
    reason: str,
    generation_backend: str | None,
    judge_backend: str | None,
    token_counter: TokenCounter,
    generation_calls: int,
    judge_calls: int,
    token_count_calls: int,
    warnings: list[str],
) -> OptimizationReport:
    eligible = [candidate for candidate in candidates if candidate.eligible]
    recommended = min(
        eligible,
        key=lambda candidate: (
            candidate.token_count if candidate.token_count is not None else float("inf"),
            candidate.kind != CandidateKind.ORIGINAL,
            candidate.candidate_id,
        ),
    )
    return OptimizationReport(
        task_type=task_type,
        source_name=source_name,
        source_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        created_at=datetime.now(timezone.utc).isoformat(),
        duration_ms=(time.perf_counter() - started_at) * 1000,
        inspection=inspection,
        candidates=tuple(candidates),
        recommended_candidate_id=recommended.candidate_id,
        recommendation_reason=reason,
        generation_backend=generation_backend,
        judge_backend=judge_backend,
        token_count_method=token_counter.method,
        token_count_provider=token_counter.provider,
        token_count_model=token_counter.model,
        token_count_exact=token_counter.exact,
        logical_generation_calls=generation_calls,
        logical_judge_calls=judge_calls,
        logical_token_count_calls=token_count_calls,
        warnings=tuple(warnings),
    )


def _recommendation_reason(candidates: list[OptimizationCandidate]) -> str:
    original = candidates[0]
    passing_generated = [
        candidate
        for candidate in candidates[1:]
        if candidate.eligible and candidate.text is not None
    ]
    shorter = [
        candidate
        for candidate in passing_generated
        if candidate.token_count is not None
        and original.token_count is not None
        and candidate.token_count < original.token_count
    ]
    if shorter:
        return "Recommended the shortest candidate that passed every verification gate."
    if passing_generated:
        return "Generated candidates passed, but none was shorter than the original."
    return "No generated candidate passed every verification gate; kept the original."


def optimize(
    text: str,
    *,
    task_type: TaskType | str,
    backend: Backend | None = None,
    target_densities: tuple[float, ...] | None = None,
    behavior_tasks: list[GoldenTask] | None = None,
    judge_backend: Backend | None = None,
    n_trials: int = 1,
    min_tokens: int = 100,
    max_tokens: int | None = None,
    source_name: str = "<inline>",
    token_counter: TokenCounter | None = None,
) -> OptimizationReport:
    """Generate, verify, and select candidates without overwriting the source.

    The original always remains eligible. Length is considered only after a
    candidate passes deterministic contract checks and any supplied behavior
    tasks. A short source or failed behavior baseline causes a safe early stop.
    """
    started_at = time.perf_counter()
    if not text or not text.strip():
        raise ValueError("Cannot optimize empty text")
    if n_trials < 1:
        raise ValueError("n_trials must be >= 1")

    tt = task_type if isinstance(task_type, TaskType) else TaskType.parse(task_type)
    densities = _densities(tt, target_densities)
    inspection = inspect_fn(
        text,
        task_type=tt,
        source_name=source_name,
        min_tokens=min_tokens,
    )
    active_counter = _counter_for(inspection, token_counter)
    original_count, token_count_calls = active_counter.count(text), 1
    candidates = [_original_candidate(text, tt, inspection, original_count)]
    warnings: list[str] = []

    if inspection.action == InspectionAction.KEEP:
        warnings.append("Source is below the rewrite threshold; no model calls were made.")
        return _report(
            started_at=started_at,
            task_type=tt,
            source_name=source_name,
            text=text,
            inspection=inspection,
            candidates=candidates,
            reason="Source is below the rewrite threshold; kept the original.",
            generation_backend=None,
            judge_backend=None,
            token_counter=active_counter,
            generation_calls=0,
            judge_calls=0,
            token_count_calls=token_count_calls,
            warnings=warnings,
        )

    tasks = list(behavior_tasks or [])
    _validate_tasks(tasks, inspection.contract)
    active_judge = judge_backend
    baseline: EvalReport | None = None
    judge_calls = 0
    if tasks:
        active_judge = active_judge or ClaudeBackend(model=DEFAULT_JUDGE_MODEL, temperature=0.0)
        baseline = evaluate_fn(
            text,
            task_type=tt,
            golden_tasks=tasks,
            judge_backend=active_judge,
            n_trials=n_trials,
        )
        judge_calls = _logical_eval_calls(tasks, n_trials)
        if baseline.n_errors:
            warnings.append("The behavior baseline had operational errors; generation was skipped.")
            return _report(
                started_at=started_at,
                task_type=tt,
                source_name=source_name,
                text=text,
                inspection=inspection,
                candidates=candidates,
                reason="Behavior baseline was unreliable; kept the original.",
                generation_backend=None,
                judge_backend=active_judge.name,
                token_counter=active_counter,
                generation_calls=0,
                judge_calls=judge_calls,
                token_count_calls=token_count_calls,
                warnings=warnings,
            )

    active_backend = backend or ClaudeBackend()
    generation_calls = 0
    candidate_eval_calls = _logical_eval_calls(tasks, n_trials)
    for index, density in enumerate(densities, start=1):
        generation_started = time.perf_counter()
        generation_calls += 1
        try:
            result = compress(
                text,
                task_type=tt,
                target_density=density,
                backend=active_backend,
                max_tokens=max_tokens,
                preservation_contract=inspection.contract,
            )
        except (BackendError, ValueError) as error:
            candidates.append(
                OptimizationCandidate(
                    candidate_id=f"candidate-{index:03d}",
                    kind=CandidateKind.GENERATED,
                    text=None,
                    requested_density=density,
                    token_count=None,
                    actual_density=None,
                    backend_name=active_backend.name,
                    rationale="",
                    verification=None,
                    generation_error=type(error).__name__,
                    generation_latency_ms=(time.perf_counter() - generation_started) * 1000,
                )
            )
            continue

        generation_latency_ms = (time.perf_counter() - generation_started) * 1000
        try:
            candidate_count = active_counter.count(result.compressed)
            token_count_calls += 1
        except TokenCountError as error:
            token_count_calls += 1
            candidates.append(
                OptimizationCandidate(
                    candidate_id=f"candidate-{index:03d}",
                    kind=CandidateKind.GENERATED,
                    text=result.compressed,
                    requested_density=density,
                    token_count=None,
                    actual_density=None,
                    backend_name=result.backend_name,
                    rationale=result.rationale,
                    verification=None,
                    measurement_error=type(error).__name__,
                    generation_latency_ms=generation_latency_ms,
                )
            )
            continue

        verification_started = time.perf_counter()
        verification = verify(
            text,
            result.compressed,
            task_type=tt,
            inspection=inspection,
            behavior_tasks=tasks,
            judge_backend=active_judge,
            n_trials=n_trials,
            baseline_report=baseline,
        )
        verification_latency_ms = (time.perf_counter() - verification_started) * 1000
        judge_calls += candidate_eval_calls
        candidates.append(
            OptimizationCandidate(
                candidate_id=f"candidate-{index:03d}",
                kind=CandidateKind.GENERATED,
                text=result.compressed,
                requested_density=density,
                token_count=candidate_count,
                actual_density=candidate_count / original_count if original_count else 1.0,
                backend_name=result.backend_name,
                rationale=result.rationale,
                verification=verification,
                generation_latency_ms=generation_latency_ms,
                verification_latency_ms=verification_latency_ms,
            )
        )

    reason = _recommendation_reason(candidates)
    return _report(
        started_at=started_at,
        task_type=tt,
        source_name=source_name,
        text=text,
        inspection=inspection,
        candidates=candidates,
        reason=reason,
        generation_backend=active_backend.name,
        judge_backend=active_judge.name if active_judge else None,
        token_counter=active_counter,
        generation_calls=generation_calls,
        judge_calls=judge_calls,
        token_count_calls=token_count_calls,
        warnings=warnings,
    )


__all__ = [
    "CandidateKind",
    "EVIDENCE_SCHEMA_VERSION",
    "OptimizationCandidate",
    "OptimizationReport",
    "optimize",
]
