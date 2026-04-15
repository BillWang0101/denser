"""Tests for the taxonomy module."""

from __future__ import annotations

import pytest

from denser.taxonomy import SPECS, TaskSpec, TaskType, get_spec


class TestTaskType:
    def test_all_values_are_snake_case(self) -> None:
        for tt in TaskType:
            assert tt.value == tt.value.lower()
            assert " " not in tt.value

    def test_parse_canonical(self) -> None:
        assert TaskType.parse("skill") == TaskType.SKILL
        assert TaskType.parse("system_prompt") == TaskType.SYSTEM_PROMPT
        assert TaskType.parse("tool_description") == TaskType.TOOL_DESCRIPTION

    def test_parse_aliases(self) -> None:
        assert TaskType.parse("skills") == TaskType.SKILL
        assert TaskType.parse("system") == TaskType.SYSTEM_PROMPT
        assert TaskType.parse("tool") == TaskType.TOOL_DESCRIPTION
        assert TaskType.parse("memory") == TaskType.MEMORY_ENTRY
        assert TaskType.parse("doc") == TaskType.ONE_SHOT_DOC

    def test_parse_case_insensitive(self) -> None:
        assert TaskType.parse("SKILL") == TaskType.SKILL
        assert TaskType.parse("Skill") == TaskType.SKILL

    def test_parse_hyphen_and_dot(self) -> None:
        assert TaskType.parse("one-shot-doc") == TaskType.ONE_SHOT_DOC
        assert TaskType.parse("claude.md") == TaskType.CLAUDE_MD

    def test_parse_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown task type"):
            TaskType.parse("nonsense")


class TestSpecs:
    def test_all_task_types_have_spec(self) -> None:
        for tt in TaskType:
            assert tt in SPECS
            assert isinstance(SPECS[tt], TaskSpec)

    def test_specs_point_to_correct_task_type(self) -> None:
        for tt, spec in SPECS.items():
            assert spec.task_type == tt

    def test_density_ranges_are_valid(self) -> None:
        for spec in SPECS.values():
            low, high = spec.density_range
            assert 0.0 < low < high <= 1.0, f"{spec.task_type}: invalid range {spec.density_range}"

    def test_default_target_density_in_range(self) -> None:
        for spec in SPECS.values():
            low, high = spec.density_range
            assert low <= spec.default_target_density <= high

    def test_preserve_and_strip_nonempty(self) -> None:
        for spec in SPECS.values():
            assert len(spec.preserve) >= 2, f"{spec.task_type}: too few preserve rules"
            assert len(spec.strip) >= 2, f"{spec.task_type}: too few strip rules"

    def test_canonical_form_nonempty(self) -> None:
        for spec in SPECS.values():
            assert spec.canonical_form.strip(), f"{spec.task_type}: empty canonical form"

    def test_role_summary_reasonable_length(self) -> None:
        for spec in SPECS.values():
            assert 40 <= len(spec.role_summary) <= 300, (
                f"{spec.task_type}: role_summary length {len(spec.role_summary)} outside [40, 300]"
            )


class TestGetSpec:
    def test_by_enum(self) -> None:
        spec = get_spec(TaskType.SKILL)
        assert spec.task_type == TaskType.SKILL

    def test_by_string(self) -> None:
        spec = get_spec("skill")
        assert spec.task_type == TaskType.SKILL

    def test_by_alias(self) -> None:
        assert get_spec("tools").task_type == TaskType.TOOL_DESCRIPTION

    def test_unknown_raises(self) -> None:
        with pytest.raises(ValueError):
            get_spec("nonsense")
