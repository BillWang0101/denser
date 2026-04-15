"""Prompt registry.

Maps each `TaskType` to a system prompt suitable for the compression backend.

All prompts share a common scaffold — the compression contract — augmented
with task-typed preserve / strip rules derived from the taxonomy. This avoids
duplication and ensures the output format is identical across task types so
downstream parsing is uniform.
"""

from __future__ import annotations

import json
from textwrap import dedent

from denser.taxonomy import SPECS, TaskSpec, TaskType

_OUTPUT_CONTRACT = dedent(
    """
    ## Output contract

    Respond in **exactly** this format, with no other text:

    ```
    === COMPRESSED ===
    <the compressed text, verbatim, nothing else>

    === RATIONALE ===
    <3-8 bullet points describing what you removed and why. Each bullet starts with "- ".>
    ```

    Nothing before `=== COMPRESSED ===`. Nothing after the rationale bullets.
    Do not wrap `=== COMPRESSED ===` content in a code fence unless the
    original text was itself a code fence that must be preserved.
    """
).strip()


_SAFETY_CLAUSE = dedent(
    """
    ## Safety preservation (non-negotiable)

    If the input text contains any of the following, **preserve them verbatim**:

    - Explicit safety policies, content restrictions, or refusal rules
    - Authentication, authorization, or access-control instructions
    - Data-handling restrictions (PII, secrets, compliance)
    - Any rule marked with "MUST", "NEVER", "DO NOT", "CRITICAL", or "IMPORTANT"

    When in doubt about whether a constraint is safety-load-bearing, **keep it**.
    Over-compression of safety rules is a failure mode we refuse to ship.
    """
).strip()


def build_system_prompt(task_type: TaskType, target_density: float) -> str:
    """Build the system prompt for compressing a given task type.

    Parameters
    ----------
    task_type : TaskType
        Which task type we're compressing. Drives preserve / strip rules.
    target_density : float
        Compressed tokens divided by original tokens. Expressed as a fraction
        in `(0, 1]`. The compressor is asked to aim for this but is free to
        deviate if hitting the target would violate safety or preserve rules.
    """
    spec: TaskSpec = SPECS[task_type]

    preserve_list = "\n".join(f"- {item}" for item in spec.preserve)
    strip_list = "\n".join(f"- {item}" for item in spec.strip)

    target_pct = int(round(target_density * 100))

    system = dedent(
        f"""
        You are a prompt-compression engine. Your output is machine-consumed —
        follow the output contract exactly.

        ## Goal

        Rewrite the input text as **compressed text** that preserves its
        functional role while eliminating attention-diluting content. The
        compressed text should be faithful to the role, not to the surface
        form of the input.

        Input role: {spec.role_summary}

        Target compression: aim for approximately **{target_pct}% of the
        original length** (measured in LLM tokens). Hit the target as a soft
        constraint — deviate if preserving load-bearing content requires it.

        ## Preserve

        The following categories of content are load-bearing. Keep them,
        even if it means missing the density target:

        {preserve_list}

        ## Strip

        The following categories are attention-diluting. Remove them:

        {strip_list}

        ## Style guidance

        - Prefer imperative over descriptive voice.
        - Prefer decision tables / bulleted rules over prose when structure is uniform.
        - Use `MUST`, `NEVER`, `DO NOT` for hard constraints — LLMs obey these more reliably.
        - Preserve structural markers (headings, numbered lists) the LLM uses to navigate.
        - Do not add content not present in the input, except formatting scaffolds
          that make the structure LLM-readable.

        ## Canonical compressed form (target shape)

        {json.dumps(spec.canonical_form)}

        (This is a shape hint, not a template. Adapt to the input's actual structure.)

        {_SAFETY_CLAUSE}

        {_OUTPUT_CONTRACT}
        """
    ).strip()

    return system
