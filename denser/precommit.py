"""Advisory pre-commit helper for reviewing large LLM instruction files.

Design
------
Fast: no API calls. Uses a local token estimate to identify files that may be
worth reviewing. Length alone is not a quality signal, so this helper never
blocks a commit and does not claim that a reference size is an optimum.

Intended wiring: a shell script at `.git/hooks/pre-commit` or a
`pre-commit-hooks` entry that invokes:

    python -m denser.precommit <file1> <file2> ...

Exit codes:
    0  — advisory scan completed (including when review suggestions are found)
    2  — invocation error (bad args, dep missing)

Skip: set `SKIP_DENSER=1` in the environment to bypass the check.

Infer task type from file path (cheap, best-effort):
    path contains 'skills/', ends .md         → skill
    path contains 'memory/', ends .md         → memory_entry
    basename == 'CLAUDE.md'                   → claude_md
    basename contains 'system_prompt'         → system_prompt
    path contains 'tools/' and ends .json/.md → tool_description
    otherwise                                 → skipped (task type unclear)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from denser.taxonomy import TaskType
from denser.tokens import estimate_tokens


def infer_task_type(path: Path) -> TaskType | None:
    """Best-effort path-based task type inference. None if not clearly an LLM input."""
    parts = {p.lower() for p in path.parts}
    name = path.name.lower()

    if name == "claude.md":
        return TaskType.CLAUDE_MD
    if "skills" in parts and path.suffix == ".md":
        return TaskType.SKILL
    if "memory" in parts and path.suffix == ".md":
        return TaskType.MEMORY_ENTRY
    if "system_prompt" in name or "system-prompt" in name:
        return TaskType.SYSTEM_PROMPT
    if "tools" in parts and path.suffix in {".json", ".md"}:
        return TaskType.TOOL_DESCRIPTION
    return None


def check_file(  # noqa: PLR0911 — verdict branches are clearer as separate returns
    path: Path,
    *,
    min_tokens: int = 100,
) -> tuple[str, dict[str, Any]]:
    """Estimate whether a file may be worth a human size review.

    Returns (verdict, info) where verdict is one of:
        "ok"       — below the advisory reference size
        "warn"     — at or above the advisory reference size; commit still OK
        "skip"     — task type could not be inferred (not our concern)
        "too_small"— under min_tokens; skip (compression value low)
        "missing"  — file does not exist

    The reference sizes are conservative alpha heuristics, not measured quality
    thresholds. `info` includes tokens, task_type, and reference_size.
    """
    if not path.exists():
        return "missing", {"path": str(path)}

    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return "skip", {"path": str(path), "reason": "empty"}

    task_type = infer_task_type(path)
    if task_type is None:
        return "skip", {"path": str(path), "reason": "task type could not be inferred"}

    tokens = estimate_tokens(text)
    if tokens < min_tokens:
        return "too_small", {"path": str(path), "tokens": tokens, "task_type": task_type.value}

    # These values only decide when to print a review suggestion. They are not
    # derived quality thresholds: the bundled corpus is too small for that.
    advisory_reference = {
        TaskType.SKILL: 800,
        TaskType.SYSTEM_PROMPT: 600,
        TaskType.TOOL_DESCRIPTION: 300,
        TaskType.MEMORY_ENTRY: 250,
        TaskType.CLAUDE_MD: 1000,
        TaskType.ONE_SHOT_DOC: 1500,
    }
    reference_size = advisory_reference.get(task_type, 1000)

    info = {
        "path": str(path),
        "tokens": tokens,
        "task_type": task_type.value,
        "reference_size": reference_size,
    }

    if tokens >= reference_size:
        return "warn", info
    return "ok", info


def format_result(verdict: str, info: dict[str, Any]) -> str:
    """Format one advisory file-check result for terminal output."""
    path = info.get("path", "?")
    if verdict == "missing":
        return f"MISSING: {path}"
    if verdict in {"skip", "too_small"}:
        reason = info.get("reason") or f"{info.get('tokens', 0)} tokens < min"
        return f"SKIP:    {path} ({reason})"
    if verdict == "ok":
        return f"OK:      {path} ({info['tokens']} tokens, type={info['task_type']})"
    if verdict == "warn":
        return (
            f"REVIEW:  {path} ({info['tokens']} estimated tokens, "
            f"type={info['task_type']}; advisory reference "
            f"{info['reference_size']}, commit allowed)"
        )
    raise ValueError(f"Unknown pre-commit verdict: {verdict}")


def main(argv: list[str] | None = None) -> int:
    """Run the advisory pre-commit scanner and return its process exit code."""
    parser = argparse.ArgumentParser(
        prog="python -m denser.precommit",
        description=(
            "Advisory size review for recognized LLM instruction files. "
            "Length suggestions never block a commit."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Files to check (usually passed by git pre-commit hook).",
    )
    parser.add_argument(
        "--min-tokens",
        type=int,
        default=100,
        help="Files under this many tokens are not checked (default 100).",
    )
    args = parser.parse_args(argv)

    if os.environ.get("SKIP_DENSER"):
        print("denser pre-commit check skipped (SKIP_DENSER set).")
        return 0

    if not args.paths:
        print("no files given; nothing to check")
        return 0

    for path in args.paths:
        verdict, info = check_file(path, min_tokens=args.min_tokens)
        print(format_result(verdict, info))
    return 0


if __name__ == "__main__":
    sys.exit(main())
