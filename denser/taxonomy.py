"""Task type taxonomy.

Six task types, each with a canonical compression strategy and sweet-spot density
range. See `docs/TAXONOMY.md` for the operational reference, `docs/WHITEPAPER.md`
for the theoretical framing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TaskType(str, Enum):
    """The six task types denser knows how to compress.

    Values are lowercase snake_case strings suitable for use as CLI arguments
    and YAML keys.
    """

    SKILL = "skill"
    SYSTEM_PROMPT = "system_prompt"
    TOOL_DESCRIPTION = "tool_description"
    MEMORY_ENTRY = "memory_entry"
    CLAUDE_MD = "claude_md"
    ONE_SHOT_DOC = "one_shot_doc"

    @classmethod
    def parse(cls, value: str) -> TaskType:
        """Parse a user-provided string into a TaskType, raising ValueError on mismatch.

        Accepts canonical values (`"skill"`) and a handful of common aliases
        (`"skills"`, `"system"`, `"tool"`, `"memory"`, `"claude.md"`, `"doc"`).
        """
        normalized = value.strip().lower().replace("-", "_").replace(".", "_")
        aliases = {
            "skills": cls.SKILL,
            "system": cls.SYSTEM_PROMPT,
            "system_prompts": cls.SYSTEM_PROMPT,
            "prompt": cls.SYSTEM_PROMPT,
            "tool": cls.TOOL_DESCRIPTION,
            "tools": cls.TOOL_DESCRIPTION,
            "tool_desc": cls.TOOL_DESCRIPTION,
            "memory": cls.MEMORY_ENTRY,
            "memories": cls.MEMORY_ENTRY,
            "claude_md_file": cls.CLAUDE_MD,
            "claudemd": cls.CLAUDE_MD,
            "doc": cls.ONE_SHOT_DOC,
            "docs": cls.ONE_SHOT_DOC,
            "one_shot": cls.ONE_SHOT_DOC,
        }
        if normalized in aliases:
            return aliases[normalized]
        for member in cls:
            if member.value == normalized:
                return member
        valid = ", ".join(m.value for m in cls)
        raise ValueError(f"Unknown task type: {value!r}. Valid types: {valid}")


@dataclass(frozen=True)
class TaskSpec:
    """The compression spec for a single task type.

    Values populate the task-typed system prompt given to the compressor
    backend, drive the default target density, and document the taxonomy in
    one place.
    """

    task_type: TaskType
    role_summary: str
    preserve: tuple[str, ...]
    strip: tuple[str, ...]
    density_range: tuple[float, float]
    canonical_form: str

    @property
    def default_target_density(self) -> float:
        """Midpoint of the observed sweet-spot range for this type."""
        low, high = self.density_range
        return round((low + high) / 2, 3)


SPECS: dict[TaskType, TaskSpec] = {
    TaskType.SKILL: TaskSpec(
        task_type=TaskType.SKILL,
        role_summary=(
            "A triggerable capability unit. Loaded into context only when the skill's "
            "description matches the current request."
        ),
        preserve=(
            "Trigger conditions (when to activate)",
            "Anti-triggers (when NOT to activate, and which alternative to prefer)",
            "Hard constraints (MUST/NEVER/DO NOT rules)",
            "Output format contracts",
            "1-2 canonical examples (common case + most common trap)",
            "Explicit safety policies or refusal boundaries",
        ),
        strip=(
            "Motivational preamble (\"This skill helps...\", \"The purpose of...\")",
            "Redundant examples illustrating the same pattern",
            "Rationale for why the skill exists (belongs in PR/commit messages)",
            "Polite hedging (\"you might want to\", \"consider whether\")",
            "Instructions the LLM would follow from base training",
            "Restatement of constraints already implied",
        ),
        density_range=(0.30, 0.45),
        canonical_form=(
            "Trigger: <activation condition + negative condition>\n"
            "\n"
            "Do:\n"
            "  1. <step>\n"
            "  2. <step>\n"
            "\n"
            "Hard constraints:\n"
            "  - MUST <...>\n"
            "  - NEVER <...>\n"
            "\n"
            "Example: <1-2 canonical illustrations>"
        ),
    ),
    TaskType.SYSTEM_PROMPT: TaskSpec(
        task_type=TaskType.SYSTEM_PROMPT,
        role_summary=(
            "Persistent context loaded at the start of every LLM call in a session. "
            "Establishes role, capability boundaries, and output contract."
        ),
        preserve=(
            "Role definition (identity, persona)",
            "Capability boundaries (what it can / cannot do)",
            "Output format contracts (structure, tone, length norms)",
            "Non-negotiable domain constraints",
            "Explicit safety policy and refusal behavior",
        ),
        strip=(
            "Effusive framing (\"You are the world's best...\")",
            "Redundant do-and-don't pairs",
            "Instructions embedded in base training (\"be honest\", \"be helpful\")",
            "Repeated safety reminders when one suffices",
            "Backstory prose that doesn't change behavior",
        ),
        density_range=(0.40, 0.55),
        canonical_form=(
            "Role: <one-line identity>.\n"
            "\n"
            "You: <capability statements>.\n"
            "Do not: <boundary statements>.\n"
            "\n"
            "Output: <format contract>.\n"
            "\n"
            "Constraints: <domain rules>."
        ),
    ),
    TaskType.TOOL_DESCRIPTION: TaskSpec(
        task_type=TaskType.TOOL_DESCRIPTION,
        role_summary=(
            "The `description` field of a tool in a tool-use schema. Parsed whenever "
            "the LLM considers calling a tool."
        ),
        preserve=(
            "When to use (triggering conditions)",
            "When NOT to use (disqualifying conditions + which alternative tool)",
            "Non-obvious failure modes (side effects, rate limits, quirks)",
            "Tool interaction notes (prerequisites, combinations)",
        ),
        strip=(
            "Parameter explanations that duplicate the schema's type info",
            "Examples of valid parameter values",
            "Courtesy language (\"please provide\", \"thank you for\")",
            "Restatement of the tool name",
        ),
        density_range=(0.45, 0.60),
        canonical_form=(
            "<one-line purpose>. Use when: <trigger>. "
            "Do NOT use for: <anti-trigger, prefer X>.\n"
            "\n"
            "Failure modes: <surprises>"
        ),
    ),
    TaskType.MEMORY_ENTRY: TaskSpec(
        task_type=TaskType.MEMORY_ENTRY,
        role_summary=(
            "A single file in a file-based memory system. Loaded on demand when "
            "retrieval surfaces it as relevant."
        ),
        preserve=(
            "The core fact (the assertion being remembered)",
            "The \"why\" (reason or source making it load-bearing)",
            "The \"when to apply\" (relevance conditions)",
        ),
        strip=(
            "Example scenarios beyond the minimum needed for the \"when\" rule",
            "Narrative framing (\"I remember that we decided...\")",
            "Timestamps unless the fact is time-bounded",
            "Cross-references to other memories (belongs in index)",
        ),
        density_range=(0.58, 0.78),
        canonical_form=(
            "<the fact>\n"
            "\n"
            "Why: <reason>\n"
            "When to apply: <conditions>"
        ),
    ),
    TaskType.CLAUDE_MD: TaskSpec(
        task_type=TaskType.CLAUDE_MD,
        role_summary=(
            "A project-level CLAUDE.md file loaded per-session by Claude Code. "
            "Contains conventions, constraints, and local-to-project instructions."
        ),
        preserve=(
            "Non-obvious conventions (things the LLM would not infer from repo structure)",
            "Hidden constraints (e.g., \"we cannot use library X\")",
            "Project-specific policies",
            "Decision boundaries (autonomous vs. confirm-first)",
        ),
        strip=(
            "API documentation (available in code)",
            "File structure descriptions (available via `ls`)",
            "Build/run instructions already in README.md",
            "Default LLM behaviors (\"be helpful\", \"write tests\")",
            "Duplicates of the same rule phrased differently",
        ),
        density_range=(0.35, 0.50),
        canonical_form=(
            "# Conventions\n"
            "- <non-obvious rule>\n"
            "- <non-obvious rule>\n"
            "\n"
            "# Constraints\n"
            "- <hidden constraint>\n"
            "\n"
            "# Decision boundaries\n"
            "- <what requires confirmation>"
        ),
    ),
    TaskType.ONE_SHOT_DOC: TaskSpec(
        task_type=TaskType.ONE_SHOT_DOC,
        role_summary=(
            "A briefing document handed to an LLM once to accomplish a specific task. "
            "Examples: implementation spec, code review brief, research summary."
        ),
        preserve=(
            "Actionable instructions (imperative form)",
            "Decision criteria for judgment calls on ambiguity",
            "Acceptance criteria (how to know when done)",
            "Edge case handling",
            "Structural headers the LLM can navigate during execution",
        ),
        strip=(
            "Motivational preamble about why the project matters",
            "Background context the LLM can infer from the codebase",
            "Summary sections that restate detailed content",
            "Speculative \"future work\" unless it affects current decisions",
        ),
        density_range=(0.40, 0.60),
        canonical_form=(
            "# Goal\n"
            "<what success looks like>\n"
            "\n"
            "# Steps\n"
            "1. ...\n"
            "2. ...\n"
            "\n"
            "# Decision criteria\n"
            "- <judgment call> → <how to decide>\n"
            "\n"
            "# Acceptance criteria\n"
            "- <testable completion signal>"
        ),
    ),
}


def get_spec(task_type: TaskType | str) -> TaskSpec:
    """Look up the `TaskSpec` for a task type.

    Accepts either a `TaskType` enum or a string (parsed via `TaskType.parse`).
    """
    if isinstance(task_type, str):
        task_type = TaskType.parse(task_type)
    return SPECS[task_type]
