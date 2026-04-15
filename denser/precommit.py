"""Pre-commit hook helper — blocks overly-verbose LLM input files from committing.

Design
------
Fast: no API calls. Uses the token estimator + taxonomy density bounds to
decide whether a file is "probably too verbose for its task type". This is a
cheap heuristic that catches gross drift; it does not replace `denser eval`
which verifies task pass-rate.

Intended wiring: a shell script at `.git/hooks/pre-commit` or a
`pre-commit-hooks` entry that invokes:

    python -m denser.precommit <file1> <file2> ...

Exit codes:
    0  — all files under sweet-spot upper bound (or inferred as non-LLM-text)
    1  — at least one file exceeds its task type's sweet-spot upper bound by
         the configured margin; commit is blocked
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

from denser.taxonomy import SPECS, TaskType
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
    margin: float = 0.10,
    min_tokens: int = 100,
) -> tuple[str, dict]:
    """Check whether a file likely needs compression.

    Returns (verdict, info) where verdict is one of:
        "ok"       — within bounds or margin; commit OK
        "warn"     — above sweet-spot upper bound but below blocking threshold
        "block"    — exceeds sweet-spot upper bound + margin; should block commit
        "skip"     — task type could not be inferred (not our concern)
        "too_small"— under min_tokens; skip (compression value low)
        "missing"  — file does not exist

    info is a dict with keys: tokens, task_type, upper, threshold.
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

    spec = SPECS[task_type]
    # Check observed token density: we don't know the "original" for an
    # already-committed file, so we approximate by saying "a file of type X
    # with >N tokens is probably verbose".
    # Heuristic: threshold_tokens = upper_density_bound × some_reference_length.
    # But without a reference, we use a typical "good" size for each type as
    # a fallback ceiling. These come from the examples/ corpus.
    typical_ceiling = {
        TaskType.SKILL: 800,  # 2x the self-compressed SKILL.md (526)
        TaskType.SYSTEM_PROMPT: 600,
        TaskType.TOOL_DESCRIPTION: 300,
        TaskType.MEMORY_ENTRY: 250,
        TaskType.CLAUDE_MD: 1000,
        TaskType.ONE_SHOT_DOC: 1500,
    }
    upper = typical_ceiling.get(task_type, 1000)
    threshold = int(upper * (1 + margin))

    info = {
        "path": str(path),
        "tokens": tokens,
        "task_type": task_type.value,
        "upper": upper,
        "threshold": threshold,
        "density_range": spec.density_range,
    }

    if tokens >= threshold:
        return "block", info
    if tokens >= upper:
        return "warn", info
    return "ok", info


def format_result(verdict: str, info: dict) -> str:
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
            f"WARN:    {path} ({info['tokens']} tokens, type={info['task_type']}; "
            f"consider compressing, typical ceiling {info['upper']})"
        )
    # block
    return (
        f"BLOCK:   {path} ({info['tokens']} tokens, type={info['task_type']}; "
        f">= {info['threshold']} block threshold)\n"
        f"         Run: denser compress --type {info['task_type']} {path}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m denser.precommit",
        description=(
            "Block commits of LLM-input files that drift past their task type's "
            "sweet-spot token ceiling. Set SKIP_DENSER=1 to bypass."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Files to check (usually passed by git pre-commit hook).",
    )
    parser.add_argument(
        "--margin",
        type=float,
        default=0.10,
        help="Fraction over the upper ceiling that still passes with a warning (default 0.10 = 10%%).",
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

    any_block = False
    for path in args.paths:
        verdict, info = check_file(path, margin=args.margin, min_tokens=args.min_tokens)
        print(format_result(verdict, info))
        if verdict == "block":
            any_block = True

    if any_block:
        print(
            "\ndenser: one or more files exceed their task type's sweet-spot ceiling.\n"
            "        Fix with `denser compress --type <type> <path>` and re-stage,\n"
            "        or set SKIP_DENSER=1 for this commit if the size is intentional."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
