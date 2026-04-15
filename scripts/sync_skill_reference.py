"""Regenerate denser/skills/denser-compress/REFERENCE_taxonomy.md from the
canonical taxonomy defined in `denser.taxonomy`.

This keeps the Claude Code skill's reference file in sync with the Python
source of truth. CI runs `--check` mode; contributors run without flags to
update the file after taxonomy edits.

Usage:
    python scripts/sync_skill_reference.py          # regenerate
    python scripts/sync_skill_reference.py --check  # fail if out of date
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from denser.taxonomy import SPECS, TaskType  # noqa: E402

OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent
    / "denser"
    / "skills"
    / "denser-compress"
    / "REFERENCE_taxonomy.md"
)


PREAMBLE = """# Taxonomy reference

This file is **auto-generated** from `denser/taxonomy.py`. Do not edit by
hand — run `python scripts/sync_skill_reference.py` after changing the
Python source.

The `denser-compress` skill reads this file to learn the preserve / strip
rules and sweet-spot density range for each task type.

---
"""


def render() -> str:
    parts: list[str] = [PREAMBLE]

    for tt in TaskType:
        spec = SPECS[tt]
        low, high = spec.density_range
        midpoint = spec.default_target_density

        preserve = "\n".join(f"- {item}" for item in spec.preserve)
        strip = "\n".join(f"- {item}" for item in spec.strip)
        canonical = spec.canonical_form

        parts.append(
            f"""
## `{tt.value}`

**Role**: {spec.role_summary}

**Density sweet spot**: {low:.2f} – {high:.2f} (target midpoint: {midpoint:.2f})

### Preserve

{preserve}

### Strip

{strip}

### Canonical compressed form (shape hint, not template)

```
{canonical}
```

---
""".strip()
            + "\n"
        )

    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the generated content would differ from the file on disk.",
    )
    args = parser.parse_args()

    rendered = render()
    current = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.exists() else ""

    if args.check:
        if rendered.strip() == current.strip():
            print(f"{OUTPUT_PATH.name} is in sync with denser/taxonomy.py")
            return 0
        print(
            f"{OUTPUT_PATH.name} is out of date. Run: python scripts/sync_skill_reference.py",
            file=sys.stderr,
        )
        return 1

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.relative_to(Path.cwd())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
