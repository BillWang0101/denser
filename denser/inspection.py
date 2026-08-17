"""Conservative inspection for version-controlled LLM instruction assets.

`inspect` is the external seam. It performs no model or network calls. The
implementation extracts explicit, reviewable preservation obligations with
source locations. It deliberately does not claim semantic completeness.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from denser.taxonomy import TaskType
from denser.tokens import estimate_tokens


class ContractCategory(str, Enum):
    """Kinds of source obligations that a candidate may not silently lose."""

    METADATA = "metadata"
    TRIGGER = "trigger"
    ANTI_TRIGGER = "anti_trigger"
    HARD_CONSTRAINT = "hard_constraint"
    SAFETY = "safety"
    PERMISSION = "permission"
    OUTPUT = "output"
    FAILURE = "failure"
    PROTECTED_LITERAL = "protected_literal"


class RiskLevel(str, Enum):
    """Review priority for an extracted obligation."""

    MEDIUM = "medium"
    HIGH = "high"


class InspectionAction(str, Enum):
    """The next safe action after offline inspection."""

    KEEP = "keep"
    REVIEW_CONTRACT = "review_contract"


@dataclass(frozen=True)
class SourceSpan:
    """One-based source location retained for diff and evidence reporting."""

    start_line: int
    end_line: int
    text: str

    def to_dict(self) -> dict[str, object]:
        """Return the source span as a JSON-serializable mapping."""
        return {
            "start_line": self.start_line,
            "end_line": self.end_line,
            "text": self.text,
        }


@dataclass(frozen=True)
class ContractItem:
    """A source-backed obligation that candidate generation must account for."""

    item_id: str
    statement: str
    categories: tuple[ContractCategory, ...]
    risk: RiskLevel
    source: SourceSpan
    protected_literals: tuple[str, ...] = ()
    test_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Return the obligation and its evidence links as serializable data."""
        return {
            "id": self.item_id,
            "statement": self.statement,
            "categories": [category.value for category in self.categories],
            "risk": self.risk.value,
            "source": self.source.to_dict(),
            "protected_literals": list(self.protected_literals),
            "test_ids": list(self.test_ids),
        }


@dataclass(frozen=True)
class PreservationContract:
    """The explicit obligations found in one instruction asset."""

    task_type: TaskType
    items: tuple[ContractItem, ...]
    protected_literals: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return the preservation contract as a serializable mapping."""
        return {
            "task_type": self.task_type.value,
            "items": [item.to_dict() for item in self.items],
            "protected_literals": list(self.protected_literals),
        }


@dataclass(frozen=True)
class InspectionReport:
    """Offline inspection result returned to callers and tests."""

    source_name: str
    task_type: TaskType
    estimated_tokens: int
    action: InspectionAction
    contract: PreservationContract
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def uncovered_high_risk_count(self) -> int:
        """Return the number of high-risk obligations without linked tests."""
        return sum(
            1 for item in self.contract.items if item.risk == RiskLevel.HIGH and not item.test_ids
        )

    def to_dict(self) -> dict[str, object]:
        """Return the inspection result and contract as serializable data."""
        return {
            "source_name": self.source_name,
            "task_type": self.task_type.value,
            "estimated_tokens": self.estimated_tokens,
            "action": self.action.value,
            "uncovered_high_risk_count": self.uncovered_high_risk_count,
            "warnings": list(self.warnings),
            "contract": self.contract.to_dict(),
        }


_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(?P<title>.+?)\s*$")
_LIST_PREFIX_RE = re.compile(r"^\s*(?:(?:[-*+])|(?:\d+[.)]))\s+")
_INLINE_LITERAL_RE = re.compile(
    r"(?<!`)`(?P<code>[^`\n]+)`(?!`)|"
    r"(?P<url>https?://[^\s<>()]+)|"
    r"(?P<number>\b\d+(?:\.\d+)?%?\b)"
)

_CATEGORY_PATTERNS: tuple[tuple[ContractCategory, re.Pattern[str]], ...] = (
    (
        ContractCategory.ANTI_TRIGGER,
        re.compile(
            r"\b(?:anti[- ]?trigger|do\s+not\s+use|don't\s+use|not\s+for|"
            r"must\s+not\s+(?:activate|trigger)|decline)\b",
            re.IGNORECASE,
        ),
    ),
    (
        ContractCategory.TRIGGER,
        re.compile(
            r"\b(?:trigger|activate|activation|use\s+when|when\s+(?:the\s+)?user|"
            r"only\s+when)\b",
            re.IGNORECASE,
        ),
    ),
    (
        ContractCategory.HARD_CONSTRAINT,
        re.compile(r"\b(?:must(?:\s+not)?|never|do\s+not|required|shall)\b", re.IGNORECASE),
    ),
    (
        ContractCategory.SAFETY,
        re.compile(
            r"\b(?:safe(?:ty)?|refus(?:e|al)|auth(?:entication|orization)?|"
            r"secrets?|credentials?|api[-_ ]?(?:keys?|tokens?)|"
            r"access[-_ ]?tokens?|bearer[-_ ]?tokens?|privacy)\b",
            re.IGNORECASE,
        ),
    ),
    (
        ContractCategory.PERMISSION,
        re.compile(
            r"\b(?:approval|approve|confirmation?|permission|authoriz(?:e|ed|ation)|"
            r"overwrite|delete|remove|write|push|publish|production)\b",
            re.IGNORECASE,
        ),
    ),
    (
        ContractCategory.OUTPUT,
        re.compile(
            r"\b(?:output|format|schema|return|respond|emit|exactly|verdict)\b",
            re.IGNORECASE,
        ),
    ),
    (
        ContractCategory.FAILURE,
        re.compile(
            r"\b(?:error|fail(?:ure|s|ed)?|abort|retry|fallback|recover(?:y)?|"
            r"rollback|stop|escalat(?:e|ion))\b",
            re.IGNORECASE,
        ),
    ),
)

_HIGH_RISK_CATEGORIES = frozenset(
    {
        ContractCategory.METADATA,
        ContractCategory.TRIGGER,
        ContractCategory.ANTI_TRIGGER,
        ContractCategory.HARD_CONSTRAINT,
        ContractCategory.SAFETY,
        ContractCategory.PERMISSION,
        ContractCategory.FAILURE,
    }
)


def _categories_for(text: str) -> tuple[ContractCategory, ...]:
    categories = [category for category, pattern in _CATEGORY_PATTERNS if pattern.search(text)]
    return tuple(categories)


def _risk_for(categories: tuple[ContractCategory, ...]) -> RiskLevel:
    if any(category in _HIGH_RISK_CATEGORIES for category in categories):
        return RiskLevel.HIGH
    return RiskLevel.MEDIUM


def _extract_protected_literals(text: str) -> tuple[str, ...]:
    found: list[str] = []
    seen: set[str] = set()
    for match in _INLINE_LITERAL_RE.finditer(text):
        literal = match.group("code") or match.group("url") or match.group("number")
        literal = literal.rstrip(".,;:!?)]}")
        if literal and literal not in seen:
            seen.add(literal)
            found.append(literal)
    return tuple(found)


def _frontmatter(lines: list[str]) -> tuple[SourceSpan | None, bool]:
    if not lines or lines[0].strip() != "---":
        return None, False
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_line = index + 1
            return SourceSpan(1, end_line, "\n".join(lines[:end_line])), False
    return SourceSpan(1, len(lines), "\n".join(lines)), True


def _item(
    item_number: int,
    statement: str,
    categories: tuple[ContractCategory, ...],
    source: SourceSpan,
) -> ContractItem:
    return ContractItem(
        item_id=f"C{item_number:03d}",
        statement=statement,
        categories=categories,
        risk=_risk_for(categories),
        source=source,
        protected_literals=_extract_protected_literals(source.text),
    )


def _extract_items(lines: list[str]) -> tuple[tuple[ContractItem, ...], bool]:
    items: list[ContractItem] = []
    frontmatter, malformed_frontmatter = _frontmatter(lines)
    skipped_until = 0
    if frontmatter is not None:
        items.append(
            _item(
                1,
                "YAML front matter",
                (ContractCategory.METADATA,),
                frontmatter,
            )
        )
        skipped_until = frontmatter.end_line

    section_categories: tuple[ContractCategory, ...] = ()
    for line_number, raw_line in enumerate(lines, start=1):
        if line_number <= skipped_until:
            continue

        heading_match = _HEADING_RE.match(raw_line)
        if heading_match:
            section_categories = _categories_for(heading_match.group("title"))
            continue

        stripped = raw_line.strip()
        if not stripped or stripped.startswith("```"):
            continue

        categories = list(_categories_for(stripped))
        for category in section_categories:
            if category not in categories:
                categories.append(category)
        if _INLINE_LITERAL_RE.search(stripped):
            categories.append(ContractCategory.PROTECTED_LITERAL)
        if not categories:
            continue

        statement = _LIST_PREFIX_RE.sub("", stripped).strip()
        source = SourceSpan(line_number, line_number, raw_line)
        items.append(_item(len(items) + 1, statement, tuple(categories), source))

    return tuple(items), malformed_frontmatter


def inspect(
    text: str,
    *,
    task_type: TaskType | str,
    source_name: str = "<inline>",
    min_tokens: int = 100,
) -> InspectionReport:
    """Inspect one instruction asset without model or network calls.

    Extraction is deliberately conservative and source-backed. The returned
    contract always requires review before it can authorize candidate rewriting.
    """
    if not text or not text.strip():
        raise ValueError("Cannot inspect empty text")
    if min_tokens < 1:
        raise ValueError("min_tokens must be >= 1")

    tt = task_type if isinstance(task_type, TaskType) else TaskType.parse(task_type)
    lines = text.splitlines()
    items, malformed_frontmatter = _extract_items(lines)
    contract = PreservationContract(
        task_type=tt,
        items=items,
        protected_literals=_extract_protected_literals(text),
    )
    estimated_tokens = estimate_tokens(text)
    action = (
        InspectionAction.KEEP if estimated_tokens < min_tokens else InspectionAction.REVIEW_CONTRACT
    )

    warnings: list[str] = [
        "Heuristic extraction may miss implicit obligations; review the contract before rewriting."
    ]
    if malformed_frontmatter:
        warnings.append(
            "YAML front matter is not closed; the entire source is protected as metadata."
        )
    if not items:
        warnings.append(
            "No explicit obligations were found; do not generate a candidate automatically."
        )
    if tt == TaskType.SKILL:
        present = {category for item in items for category in item.categories}
        if ContractCategory.TRIGGER not in present:
            warnings.append("No explicit skill trigger was found.")
        if ContractCategory.ANTI_TRIGGER not in present:
            warnings.append("No explicit skill anti-trigger was found.")
    if action == InspectionAction.KEEP:
        warnings.append(
            f"Estimated size is below {min_tokens} tokens; rewriting has low expected value."
        )

    return InspectionReport(
        source_name=source_name,
        task_type=tt,
        estimated_tokens=estimated_tokens,
        action=action,
        contract=contract,
        warnings=tuple(warnings),
    )


__all__ = [
    "ContractCategory",
    "ContractItem",
    "InspectionAction",
    "InspectionReport",
    "PreservationContract",
    "RiskLevel",
    "SourceSpan",
    "inspect",
]
