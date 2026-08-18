"""Package-version consistency checks."""

import re
from pathlib import Path

import denser


def test_runtime_version_matches_package_metadata() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    project = pyproject.split("[project]", 1)[1].split("\n[", 1)[0]
    match = re.search(r'^version = "([^"]+)"$', project, flags=re.MULTILINE)
    assert match is not None
    assert denser.__version__ == match.group(1)
