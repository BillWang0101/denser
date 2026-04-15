"""Ensure the Claude Code skill's reference file stays in sync with taxonomy.

If this test fails, run:

    python scripts/sync_skill_reference.py

to regenerate `denser/skills/denser-compress/REFERENCE_taxonomy.md` from
`denser.taxonomy`, then commit the change.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_reference_taxonomy_is_in_sync() -> None:
    """Skill's REFERENCE_taxonomy.md must match what `sync_skill_reference.py` renders."""
    result = subprocess.run(
        [sys.executable, "scripts/sync_skill_reference.py", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"skill reference is out of date.\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}\n"
        f"Fix: python scripts/sync_skill_reference.py"
    )


def test_skill_md_exists_and_has_frontmatter() -> None:
    skill_path = REPO_ROOT / "denser" / "skills" / "denser-compress" / "SKILL.md"
    assert skill_path.is_file()
    text = skill_path.read_text(encoding="utf-8")
    # Must start with YAML frontmatter
    assert text.startswith("---\n"), "SKILL.md must start with YAML frontmatter"
    # Must declare name and description
    assert "\nname: denser-compress" in text
    assert "\ndescription:" in text


def test_install_scripts_exist() -> None:
    skills_dir = REPO_ROOT / "denser" / "skills"
    assert (skills_dir / "install.sh").is_file()
    assert (skills_dir / "install.ps1").is_file()
    assert (skills_dir / "README.md").is_file()


def test_reference_mentions_all_task_types() -> None:
    from denser.taxonomy import TaskType

    ref_path = REPO_ROOT / "denser" / "skills" / "denser-compress" / "REFERENCE_taxonomy.md"
    ref = ref_path.read_text(encoding="utf-8")
    for tt in TaskType:
        assert f"`{tt.value}`" in ref, f"{tt.value} missing from reference"
