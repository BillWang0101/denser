"""Tests for conservative instruction inspection and preservation contracts."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from denser import (
    ContractCategory,
    InspectionAction,
    RiskLevel,
    inspect,
)
from denser.cli import main
from denser.taxonomy import TaskType

SAMPLE_SKILL = """---
name: deployment-helper
description: Use when the user asks to deploy a release.
---

# Trigger

Use when the user asks to deploy. Do not use for local previews.

# Hard constraints

- MUST ask for approval before writing to production.
- NEVER print secrets or API tokens.
- Abort if the health check fails; keep the previous release available.

# Output format

Return exactly `release=<id> status=<state>`.
"""


class TestInspect:
    def test_empty_text_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            inspect("", task_type="skill")

    def test_short_text_recommends_keep(self) -> None:
        report = inspect("Use when asked. Never delete data.", task_type="skill")
        assert report.action == InspectionAction.KEEP
        assert report.estimated_tokens < 100

    def test_extracts_frontmatter_as_one_item(self) -> None:
        report = inspect(SAMPLE_SKILL, task_type="skill", min_tokens=1)
        metadata = [
            item for item in report.contract.items if ContractCategory.METADATA in item.categories
        ]
        assert len(metadata) == 1
        assert metadata[0].source.start_line == 1
        assert metadata[0].source.end_line == 4
        assert metadata[0].risk == RiskLevel.HIGH

    def test_extracts_role_specific_obligations(self) -> None:
        report = inspect(SAMPLE_SKILL, task_type=TaskType.SKILL, min_tokens=1)
        categories = {category for item in report.contract.items for category in item.categories}

        assert ContractCategory.TRIGGER in categories
        assert ContractCategory.ANTI_TRIGGER in categories
        assert ContractCategory.HARD_CONSTRAINT in categories
        assert ContractCategory.SAFETY in categories
        assert ContractCategory.PERMISSION in categories
        assert ContractCategory.FAILURE in categories
        assert ContractCategory.OUTPUT in categories

    def test_preserves_source_line_numbers_and_text(self) -> None:
        report = inspect(SAMPLE_SKILL, task_type="skill", min_tokens=1)
        approval = next(item for item in report.contract.items if "approval" in item.statement)
        assert approval.source.start_line == 12
        assert approval.source.end_line == 12
        assert "MUST ask for approval" in approval.source.text
        assert approval.risk == RiskLevel.HIGH

    def test_extracts_protected_literals_in_source_order(self) -> None:
        text = (
            "MUST keep `AGENTS.md` and `SKIP_DENSER=1`.\n"
            "See https://example.com/spec and retry 3 times.\n"
            "Repeat `AGENTS.md`."
        )
        report = inspect(text, task_type="claude_md", min_tokens=1)
        assert report.contract.protected_literals == (
            "AGENTS.md",
            "SKIP_DENSER=1",
            "https://example.com/spec",
            "3",
        )

    def test_reports_uncovered_high_risk_items(self) -> None:
        report = inspect(SAMPLE_SKILL, task_type="skill", min_tokens=1)
        assert report.uncovered_high_risk_count > 0
        assert all(not item.test_ids for item in report.contract.items)
        assert report.action == InspectionAction.REVIEW_CONTRACT

    def test_warns_when_skill_has_no_explicit_trigger(self) -> None:
        report = inspect("MUST return JSON.", task_type="skill", min_tokens=1)
        assert any("trigger" in warning.lower() for warning in report.warnings)

    def test_token_counting_is_not_mislabeled_as_safety(self) -> None:
        report = inspect("Count tokens before rewriting.", task_type="skill", min_tokens=1)
        categories = {category for item in report.contract.items for category in item.categories}
        assert ContractCategory.SAFETY not in categories

    def test_to_dict_is_json_serializable(self) -> None:
        report = inspect(SAMPLE_SKILL, task_type="skill", source_name="SKILL.md", min_tokens=1)
        data = report.to_dict()
        encoded = json.dumps(data)

        assert data["source_name"] == "SKILL.md"
        assert data["task_type"] == "skill"
        assert '"review_contract"' in encoded
        assert data["contract"]["items"]


class TestInspectCli:
    def test_inspect_command_is_offline_and_prints_contract(self, tmp_path) -> None:
        source = tmp_path / "SKILL.md"
        source.write_text(SAMPLE_SKILL, encoding="utf-8")

        result = CliRunner().invoke(
            main,
            ["inspect", str(source), "--type", "skill", "--min-tokens", "1"],
        )

        assert result.exit_code == 0, result.output
        assert "review_contract" in result.output
        assert "hard_constraint" in result.output
        assert "No model or network calls" in result.output

    def test_inspect_command_writes_json_report(self, tmp_path) -> None:
        source = tmp_path / "SKILL.md"
        output = tmp_path / "inspection.json"
        source.write_text(SAMPLE_SKILL, encoding="utf-8")

        result = CliRunner().invoke(
            main,
            [
                "inspect",
                str(source),
                "--type",
                "skill",
                "--min-tokens",
                "1",
                "--json-out",
                str(output),
            ],
        )

        assert result.exit_code == 0, result.output
        data = json.loads(output.read_text(encoding="utf-8"))
        assert data["source_name"] == str(source)
        assert data["contract"]["items"]

    @pytest.mark.skipif(os.name != "nt", reason="Windows code-page regression")
    def test_inspect_does_not_crash_on_unencodable_source_output(self, tmp_path) -> None:
        source = tmp_path / "source.md"
        source.write_text("Return exactly `status=ready` ✓.", encoding="utf-8")
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "gbk:strict"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "denser.cli",
                "inspect",
                str(source),
                "--type",
                "skill",
                "--min-tokens",
                "1",
            ],
            cwd=str(Path(__file__).parents[1]),
            env=env,
            capture_output=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr.decode("ascii", errors="replace")
        assert b"UnicodeEncodeError" not in result.stderr
