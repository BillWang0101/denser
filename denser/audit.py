"""Behavior-fidelity audits for instruction and context variants.

The audit module answers two separate questions:

1. Did the proposed variant change any behavior covered by the replay suite?
2. Can that suite detect a known-bad negative control?

The second question prevents a weak suite from certifying every variant merely
because none of its cases are sensitive to the changed instruction.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from denser.backends import Backend
from denser.replay import (
    ReplayComparisonReport,
    ReplayProgress,
    ReplayReport,
    ReplaySuite,
    ReplayTask,
    _replay_comparison_sides,
)
from denser.taxonomy import TaskType
from denser.tokens import estimate_tokens

AUDIT_REPORT_SCHEMA_VERSION = "denser.context-audit/v1"


class AuditDecision(str, Enum):
    """Conservative outcome of a context-variant audit."""

    PRESERVED = "preserved"
    REGRESSED = "regressed"
    REVIEW = "review"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class ContextAuditReport:
    """Replay evidence, sensitivity control, and end-to-end token measurements."""

    task_type: TaskType
    comparison: ReplayComparisonReport
    baseline_estimated_tokens: int
    variant_estimated_tokens: int
    decision: AuditDecision
    decision_reason: str
    variant_regressions: tuple[str, ...] = ()
    variant_improvements: tuple[str, ...] = ()
    negative_control: ReplayReport | None = None
    negative_control_regressions: tuple[str, ...] = ()

    @property
    def estimated_token_reduction(self) -> int:
        """Return positive estimated tokens removed from the asset itself."""
        return self.baseline_estimated_tokens - self.variant_estimated_tokens

    @property
    def estimated_token_reduction_pct(self) -> float:
        """Return estimated asset-only reduction relative to the baseline."""
        if self.baseline_estimated_tokens == 0:
            return 0.0
        return self.estimated_token_reduction / self.baseline_estimated_tokens

    @property
    def baseline_input_tokens(self) -> int | None:
        """Return provider-reported full input tokens, when both sides expose them."""
        baseline = self.comparison.original.usage_totals["input_tokens"]
        variant = self.comparison.candidate.usage_totals["input_tokens"]
        return baseline if baseline > 0 and variant > 0 else None

    @property
    def variant_input_tokens(self) -> int | None:
        """Return provider-reported full input tokens, when both sides expose them."""
        baseline = self.comparison.original.usage_totals["input_tokens"]
        variant = self.comparison.candidate.usage_totals["input_tokens"]
        return variant if baseline > 0 and variant > 0 else None

    @property
    def observed_input_reduction(self) -> int | None:
        """Return positive provider-reported input tokens removed end to end."""
        if self.baseline_input_tokens is None or self.variant_input_tokens is None:
            return None
        return self.baseline_input_tokens - self.variant_input_tokens

    @property
    def observed_input_reduction_pct(self) -> float | None:
        """Return end-to-end input reduction relative to the baseline."""
        if self.baseline_input_tokens is None or self.observed_input_reduction is None:
            return None
        return self.observed_input_reduction / self.baseline_input_tokens

    @property
    def negative_control_detected(self) -> bool | None:
        """Return whether a supplied known-bad control degraded a covered case."""
        if self.negative_control is None:
            return None
        return bool(self.negative_control_regressions)

    def to_dict(self) -> dict[str, object]:
        """Return a versioned, JSON-compatible evidence report."""
        return {
            "schema_version": AUDIT_REPORT_SCHEMA_VERSION,
            "task_type": self.task_type.value,
            "decision": self.decision.value,
            "decision_reason": self.decision_reason,
            "variant_regressions": list(self.variant_regressions),
            "variant_improvements": list(self.variant_improvements),
            "negative_control_detected": self.negative_control_detected,
            "negative_control_regressions": list(self.negative_control_regressions),
            "measurements": {
                "baseline_estimated_tokens": self.baseline_estimated_tokens,
                "variant_estimated_tokens": self.variant_estimated_tokens,
                "estimated_token_reduction": self.estimated_token_reduction,
                "estimated_token_reduction_pct": self.estimated_token_reduction_pct,
                "baseline_input_tokens": self.baseline_input_tokens,
                "variant_input_tokens": self.variant_input_tokens,
                "observed_input_reduction": self.observed_input_reduction,
                "observed_input_reduction_pct": self.observed_input_reduction_pct,
            },
            "comparison": self.comparison.to_dict(),
            "negative_control": (
                None if self.negative_control is None else self.negative_control.to_dict()
            ),
        }


def _case_pass_counts(report: ReplayReport) -> dict[tuple[str, str], int]:
    return {
        (task.task_name, case.case_name): case.n_passed
        for task in report.task_results
        for case in task.case_results
    }


def _case_deltas(
    baseline: ReplayReport,
    observed: ReplayReport,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    baseline_counts = _case_pass_counts(baseline)
    observed_counts = _case_pass_counts(observed)
    if baseline_counts.keys() != observed_counts.keys():
        raise ValueError("Replay reports do not contain the same task and case identities")

    regressions: list[str] = []
    improvements: list[str] = []
    for identity, baseline_passes in baseline_counts.items():
        observed_passes = observed_counts[identity]
        label = f"{identity[0]}/{identity[1]}"
        if observed_passes < baseline_passes:
            regressions.append(label)
        elif observed_passes > baseline_passes:
            improvements.append(label)
    return tuple(regressions), tuple(improvements)


def _decision(  # noqa: PLR0911 - verdict branches are clearer as separate returns
    comparison: ReplayComparisonReport,
    negative_control: ReplayReport | None,
    variant_regressions: tuple[str, ...],
    variant_improvements: tuple[str, ...],
    negative_control_regressions: tuple[str, ...],
) -> tuple[AuditDecision, str]:
    if comparison.original.n_errors or comparison.candidate.n_errors:
        return (
            AuditDecision.INCONCLUSIVE,
            "Operational errors occurred during the baseline or variant replay.",
        )
    if variant_regressions:
        return (
            AuditDecision.REGRESSED,
            "The variant passed fewer trials than the baseline in one or more covered cases.",
        )
    if variant_improvements:
        return (
            AuditDecision.REVIEW,
            "The variant changed covered behavior by passing cases the baseline did not.",
        )
    if negative_control is None:
        return (
            AuditDecision.INCONCLUSIVE,
            "Observed parity is not certified because no known-bad negative control was run.",
        )
    if negative_control.n_errors:
        return (
            AuditDecision.INCONCLUSIVE,
            "Operational errors occurred during the negative-control replay.",
        )
    if not negative_control_regressions:
        return (
            AuditDecision.INCONCLUSIVE,
            "The replay suite did not detect the known-bad negative control.",
        )
    return (
        AuditDecision.PRESERVED,
        "The variant matched the baseline on every covered case and the suite caught the "
        "known-bad negative control.",
    )


def audit_context(
    *,
    baseline: str,
    variant: str,
    task_type: TaskType | str,
    tasks: ReplaySuite | list[ReplayTask],
    backend: Backend,
    negative_control: str | None = None,
    n_trials: int = 1,
    seed: int = 0,
    on_progress: Callable[[ReplayProgress], None] | None = None,
) -> ContextAuditReport:
    """Audit a context variant and require a sensitive suite for a positive verdict.

    A ``preserved`` decision requires exact covered-case parity between baseline
    and variant plus at least one detected regression in a caller-supplied,
    known-bad negative control. Without that control, parity is reported as
    ``inconclusive`` rather than treated as proof.
    """
    additional_texts = {} if negative_control is None else {"negative_control": negative_control}
    tt, reports = _replay_comparison_sides(
        original=baseline,
        candidate=variant,
        additional_texts=additional_texts,
        task_type=task_type,
        tasks=tasks,
        backend=backend,
        n_trials=n_trials,
        seed=seed,
        on_progress=on_progress,
    )
    comparison = ReplayComparisonReport(
        task_type=tt,
        original=reports["original"],
        candidate=reports["candidate"],
        seed=seed,
    )
    variant_regressions, variant_improvements = _case_deltas(
        comparison.original,
        comparison.candidate,
    )

    control_report: ReplayReport | None = None
    control_regressions: tuple[str, ...] = ()
    if negative_control is not None:
        control_report = reports["negative_control"]
        control_regressions, _control_improvements = _case_deltas(
            comparison.original,
            control_report,
        )

    decision, reason = _decision(
        comparison,
        control_report,
        variant_regressions,
        variant_improvements,
        control_regressions,
    )
    return ContextAuditReport(
        task_type=tt,
        comparison=comparison,
        baseline_estimated_tokens=estimate_tokens(baseline),
        variant_estimated_tokens=estimate_tokens(variant),
        decision=decision,
        decision_reason=reason,
        variant_regressions=variant_regressions,
        variant_improvements=variant_improvements,
        negative_control=control_report,
        negative_control_regressions=control_regressions,
    )


__all__ = [
    "AUDIT_REPORT_SCHEMA_VERSION",
    "AuditDecision",
    "ContextAuditReport",
    "audit_context",
]
