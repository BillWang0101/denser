"""Conservative component selection for visible LLM context bundles.

The module exposes one narrow workflow: load a versioned bundle manifest,
remove optional components one at a time, and keep a removal only when the
existing behavior audit certifies parity and catches a known-bad control.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from denser.audit import AuditDecision, ContextAuditReport, audit_context
from denser.backends import Backend
from denser.replay import ReplayProgress, ReplaySuite, ReplaySuiteRole
from denser.taxonomy import TaskType
from denser.tokens import estimate_tokens

CONTEXT_BUNDLE_SCHEMA_VERSION = "denser.context-bundle/v1"
CONTEXT_SELECTION_SCHEMA_VERSION = "denser.context-selection/v1"
SELECTION_METHOD = "greedy-largest-first/v1"
_COMPONENT_ID_RE = re.compile(r"[a-z0-9][a-z0-9._-]*")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ContextComponent:
    """One named, reviewable text component in a context bundle."""

    component_id: str
    kind: TaskType
    path: Path
    text: str
    required: bool = False

    @property
    def estimated_tokens(self) -> int:
        """Return the explicit offline token estimate for this component."""
        return estimate_tokens(self.text)


@dataclass(frozen=True)
class ContextBundle:
    """Validated component bundle loaded from a versioned manifest."""

    name: str
    task_type: TaskType
    components: tuple[ContextComponent, ...]
    negative_control_drop: tuple[str, ...]
    manifest_path: Path
    schema_version: str = CONTEXT_BUNDLE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Context bundle name cannot be empty")
        if len(self.components) < 2:
            raise ValueError("Context bundle must contain at least two components")
        component_ids = [component.component_id for component in self.components]
        if len(component_ids) != len(set(component_ids)):
            raise ValueError("Context bundle component ids must be unique")
        if not any(not component.required for component in self.components):
            raise ValueError("Context bundle must contain at least one optional component")
        if not self.negative_control_drop:
            raise ValueError("Context bundle must define negative_control_drop")
        if len(self.negative_control_drop) != len(set(self.negative_control_drop)):
            raise ValueError("negative_control_drop component ids must be unique")
        unknown = set(self.negative_control_drop) - set(component_ids)
        if unknown:
            raise ValueError(
                "negative_control_drop contains unknown component ids: "
                + ", ".join(sorted(unknown))
            )
        required_ids = {
            component.component_id for component in self.components if component.required
        }
        unprotected = set(self.negative_control_drop) - required_ids
        if unprotected:
            raise ValueError(
                "negative_control_drop components must be required: "
                + ", ".join(sorted(unprotected))
            )
        if len(self.negative_control_drop) == len(self.components):
            raise ValueError("negative_control_drop cannot remove every component")

    @property
    def component_ids(self) -> tuple[str, ...]:
        """Return component ids in manifest order."""
        return tuple(component.component_id for component in self.components)

    @property
    def required_ids(self) -> tuple[str, ...]:
        """Return required component ids in manifest order."""
        return tuple(component.component_id for component in self.components if component.required)

    @property
    def optional_components(self) -> tuple[ContextComponent, ...]:
        """Return removable components, largest estimated size first."""
        return tuple(
            sorted(
                (component for component in self.components if not component.required),
                key=lambda component: (-component.estimated_tokens, component.component_id),
            )
        )

    def render(self, included_ids: tuple[str, ...] | list[str] | set[str]) -> str:
        """Render selected components in stable manifest order."""
        selected = set(included_ids)
        unknown = selected - set(self.component_ids)
        if unknown:
            raise ValueError("Cannot render unknown component ids: " + ", ".join(sorted(unknown)))
        sections = []
        for component in self.components:
            if component.component_id not in selected:
                continue
            sections.append(
                f"## Context component: {component.component_id} ({component.kind.value})\n\n"
                f"{component.text.rstrip()}"
            )
        if not sections:
            raise ValueError("Cannot render an empty context bundle")
        return "\n\n".join(sections) + "\n"

    @property
    def baseline_text(self) -> str:
        """Return the complete rendered context bundle."""
        return self.render(self.component_ids)

    @property
    def negative_control_text(self) -> str:
        """Return the declared known-bad sensitivity control."""
        dropped = set(self.negative_control_drop)
        return self.render([item for item in self.component_ids if item not in dropped])


@dataclass(frozen=True)
class ComponentAttempt:
    """Summary evidence for one attempted component removal."""

    component_id: str
    component_estimated_tokens: int
    removed: bool
    decision: AuditDecision
    decision_reason: str
    variant_regressions: tuple[str, ...]
    variant_improvements: tuple[str, ...]
    observed_input_reduction_pct: float | None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible attempt summary."""
        return {
            "component_id": self.component_id,
            "component_estimated_tokens": self.component_estimated_tokens,
            "removed": self.removed,
            "decision": self.decision.value,
            "decision_reason": self.decision_reason,
            "variant_regressions": list(self.variant_regressions),
            "variant_improvements": list(self.variant_improvements),
            "observed_input_reduction_pct": self.observed_input_reduction_pct,
        }


@dataclass(frozen=True)
class ContextSelectionReport:
    """Selection decisions plus a separately repeated final audit."""

    bundle_name: str
    task_type: TaskType
    baseline_sha256: str
    selected_sha256: str
    baseline_estimated_tokens: int
    selected_estimated_tokens: int
    selected_ids: tuple[str, ...]
    removed_ids: tuple[str, ...]
    required_ids: tuple[str, ...]
    negative_control_drop: tuple[str, ...]
    attempts: tuple[ComponentAttempt, ...]
    final_audit: ContextAuditReport
    selection_trials: int
    validation_trials: int
    parallelism: int
    min_input_reduction: float
    schema_version: str = CONTEXT_SELECTION_SCHEMA_VERSION
    selection_method: str = SELECTION_METHOD

    @property
    def observed_input_reduction_pct(self) -> float | None:
        """Return provider-reported end-to-end input reduction."""
        return self.final_audit.observed_input_reduction_pct

    @property
    def target_met(self) -> bool:
        """Return whether final parity and the requested saving are both proven."""
        observed = self.observed_input_reduction_pct
        return (
            self.final_audit.decision == AuditDecision.PRESERVED
            and observed is not None
            and observed >= self.min_input_reduction
        )

    @property
    def outcome_reason(self) -> str:
        """Explain why the target passed or failed without overstating evidence."""
        if self.final_audit.decision != AuditDecision.PRESERVED:
            return f"Final behavior audit was {self.final_audit.decision.value}."
        observed = self.observed_input_reduction_pct
        if observed is None:
            return "The backend did not report comparable full-input token usage."
        if observed < self.min_input_reduction:
            return (
                f"Observed full-input reduction was {observed:.2%}, below the "
                f"{self.min_input_reduction:.2%} target."
            )
        return f"Behavior was preserved and observed full-input reduction was {observed:.2%}."

    def to_dict(self) -> dict[str, object]:
        """Return a versioned, JSON-compatible evidence report."""
        return {
            "schema_version": self.schema_version,
            "selection_method": self.selection_method,
            "bundle_name": self.bundle_name,
            "task_type": self.task_type.value,
            "target_met": self.target_met,
            "outcome_reason": self.outcome_reason,
            "min_input_reduction": self.min_input_reduction,
            "selection_trials": self.selection_trials,
            "validation_trials": self.validation_trials,
            "parallelism": self.parallelism,
            "baseline_sha256": self.baseline_sha256,
            "selected_sha256": self.selected_sha256,
            "components": {
                "selected": list(self.selected_ids),
                "removed": list(self.removed_ids),
                "required": list(self.required_ids),
                "negative_control_drop": list(self.negative_control_drop),
            },
            "measurements": {
                "baseline_estimated_tokens": self.baseline_estimated_tokens,
                "selected_estimated_tokens": self.selected_estimated_tokens,
                "estimated_token_reduction": (
                    self.baseline_estimated_tokens - self.selected_estimated_tokens
                ),
                "estimated_token_reduction_pct": (
                    0.0
                    if self.baseline_estimated_tokens == 0
                    else (self.baseline_estimated_tokens - self.selected_estimated_tokens)
                    / self.baseline_estimated_tokens
                ),
                "observed_input_reduction_pct": self.observed_input_reduction_pct,
            },
            "attempts": [attempt.to_dict() for attempt in self.attempts],
            "final_audit": self.final_audit.to_dict(),
        }


def _manifest_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid context bundle JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError("Context bundle manifest must be a JSON object")
    return data


def load_context_bundle(path: str | Path) -> ContextBundle:
    """Load and strictly validate a context bundle manifest and its text files."""
    manifest_path = Path(path).expanduser().resolve()
    data = _manifest_object(manifest_path)
    if data.get("schema_version") != CONTEXT_BUNDLE_SCHEMA_VERSION:
        raise ValueError(f"Context bundle schema_version must be {CONTEXT_BUNDLE_SCHEMA_VERSION!r}")
    name = data.get("name")
    task_type = data.get("task_type")
    raw_components = data.get("components")
    raw_control = data.get("negative_control_drop")
    if not isinstance(name, str) or not isinstance(task_type, str):
        raise ValueError("Context bundle name and task_type must be strings")
    if not isinstance(raw_components, list) or not all(
        isinstance(item, dict) for item in raw_components
    ):
        raise ValueError("Context bundle components must be a list of objects")
    if not isinstance(raw_control, list) or not all(isinstance(item, str) for item in raw_control):
        raise ValueError("negative_control_drop must be a list of component ids")

    root = manifest_path.parent.resolve()
    components: list[ContextComponent] = []
    seen_paths: set[Path] = set()
    for item in raw_components:
        component_id = item.get("id")
        kind = item.get("kind")
        raw_path = item.get("path")
        required = item.get("required", False)
        if not isinstance(component_id, str) or _COMPONENT_ID_RE.fullmatch(component_id) is None:
            raise ValueError(
                "Component id must use lowercase letters, numbers, dots, underscores, or hyphens"
            )
        if not isinstance(kind, str) or not isinstance(raw_path, str):
            raise ValueError(f"Component {component_id!r} kind and path must be strings")
        if not isinstance(required, bool):
            raise ValueError(f"Component {component_id!r} required must be a boolean")
        component_path = (root / raw_path).resolve()
        if not component_path.is_relative_to(root):
            raise ValueError(
                f"Component {component_id!r} path must stay inside the bundle directory"
            )
        if component_path in seen_paths:
            raise ValueError(f"Context bundle references the same file twice: {raw_path}")
        if not component_path.is_file():
            raise ValueError(f"Component file does not exist: {raw_path}")
        text = component_path.read_text(encoding="utf-8")
        if not text.strip():
            raise ValueError(f"Component file is empty: {raw_path}")
        seen_paths.add(component_path)
        components.append(
            ContextComponent(
                component_id=component_id,
                kind=TaskType.parse(kind),
                path=component_path,
                text=text,
                required=required,
            )
        )
    return ContextBundle(
        name=name,
        task_type=TaskType.parse(task_type),
        components=tuple(components),
        negative_control_drop=tuple(raw_control),
        manifest_path=manifest_path,
    )


def minimize_context(
    *,
    bundle: ContextBundle,
    tasks: ReplaySuite,
    backend: Backend,
    selection_trials: int = 1,
    validation_trials: int = 3,
    seed: int = 0,
    min_input_reduction: float = 0.10,
    on_progress: Callable[[ReplayProgress], None] | None = None,
    parallelism: int = 1,
) -> tuple[str, ContextSelectionReport]:
    """Greedily remove optional components and fail closed on uncertain behavior."""
    if tasks.role != ReplaySuiteRole.DEVELOPMENT:
        raise ValueError(
            "Automatic context selection requires a development replay suite; "
            "freeze and audit the selected context separately for holdout evidence"
        )
    if selection_trials < 1 or validation_trials < 1:
        raise ValueError("selection_trials and validation_trials must be at least 1")
    if parallelism < 1:
        raise ValueError("parallelism must be at least 1")
    if not 0.0 <= min_input_reduction <= 1.0:
        raise ValueError("min_input_reduction must be between 0 and 1")

    baseline = bundle.baseline_text
    negative_control = bundle.negative_control_text
    selected = list(bundle.component_ids)
    removed: list[str] = []
    attempts: list[ComponentAttempt] = []

    for index, component in enumerate(bundle.optional_components):
        candidate_ids = [item for item in selected if item != component.component_id]
        candidate = bundle.render(candidate_ids)
        audit = audit_context(
            baseline=baseline,
            variant=candidate,
            negative_control=negative_control,
            task_type=bundle.task_type,
            tasks=tasks,
            backend=backend,
            n_trials=selection_trials,
            seed=seed + index,
            on_progress=on_progress,
            parallelism=parallelism,
        )
        accepted = audit.decision == AuditDecision.PRESERVED
        if accepted:
            selected = candidate_ids
            removed.append(component.component_id)
        attempts.append(
            ComponentAttempt(
                component_id=component.component_id,
                component_estimated_tokens=component.estimated_tokens,
                removed=accepted,
                decision=audit.decision,
                decision_reason=audit.decision_reason,
                variant_regressions=audit.variant_regressions,
                variant_improvements=audit.variant_improvements,
                observed_input_reduction_pct=audit.observed_input_reduction_pct,
            )
        )

    selected_text = bundle.render(selected)
    final_audit = audit_context(
        baseline=baseline,
        variant=selected_text,
        negative_control=negative_control,
        task_type=bundle.task_type,
        tasks=tasks,
        backend=backend,
        n_trials=validation_trials,
        seed=seed + len(bundle.optional_components),
        on_progress=on_progress,
        parallelism=parallelism,
    )
    report = ContextSelectionReport(
        bundle_name=bundle.name,
        task_type=bundle.task_type,
        baseline_sha256=_sha256(baseline),
        selected_sha256=_sha256(selected_text),
        baseline_estimated_tokens=estimate_tokens(baseline),
        selected_estimated_tokens=estimate_tokens(selected_text),
        selected_ids=tuple(selected),
        removed_ids=tuple(removed),
        required_ids=bundle.required_ids,
        negative_control_drop=bundle.negative_control_drop,
        attempts=tuple(attempts),
        final_audit=final_audit,
        selection_trials=selection_trials,
        validation_trials=validation_trials,
        parallelism=parallelism,
        min_input_reduction=min_input_reduction,
    )
    return selected_text, report


__all__ = [
    "CONTEXT_BUNDLE_SCHEMA_VERSION",
    "CONTEXT_SELECTION_SCHEMA_VERSION",
    "ComponentAttempt",
    "ContextBundle",
    "ContextComponent",
    "ContextSelectionReport",
    "load_context_bundle",
    "minimize_context",
]
