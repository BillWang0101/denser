"""Task-typed compression prompts.

Each task type has a purpose-built system prompt that encodes its preserve /
strip rules. The `registry` module maps `TaskType` to the appropriate prompt
builder.
"""

from denser.prompts.registry import build_system_prompt

__all__ = ["build_system_prompt"]
