"""Tests for the pre-commit hook helper."""

from __future__ import annotations

from denser.precommit import check_file, infer_task_type, main
from denser.taxonomy import TaskType


class TestInferTaskType:
    def test_skill_in_skills_dir(self, tmp_path) -> None:
        p = tmp_path / ".claude" / "skills" / "pr-review" / "SKILL.md"
        p.parent.mkdir(parents=True)
        p.write_text("x")
        assert infer_task_type(p) == TaskType.SKILL

    def test_claude_md(self, tmp_path) -> None:
        p = tmp_path / "CLAUDE.md"
        p.write_text("x")
        assert infer_task_type(p) == TaskType.CLAUDE_MD

    def test_claude_md_nested(self, tmp_path) -> None:
        p = tmp_path / "packages" / "foo" / "CLAUDE.md"
        p.parent.mkdir(parents=True)
        p.write_text("x")
        assert infer_task_type(p) == TaskType.CLAUDE_MD

    def test_memory(self, tmp_path) -> None:
        p = tmp_path / "memory" / "fact.md"
        p.parent.mkdir(parents=True)
        p.write_text("x")
        assert infer_task_type(p) == TaskType.MEMORY_ENTRY

    def test_system_prompt(self, tmp_path) -> None:
        p = tmp_path / "my_system_prompt.md"
        p.write_text("x")
        assert infer_task_type(p) == TaskType.SYSTEM_PROMPT

    def test_tool_description(self, tmp_path) -> None:
        p = tmp_path / "tools" / "search.md"
        p.parent.mkdir(parents=True)
        p.write_text("x")
        assert infer_task_type(p) == TaskType.TOOL_DESCRIPTION

    def test_unrecognized(self, tmp_path) -> None:
        p = tmp_path / "some" / "random" / "file.txt"
        p.parent.mkdir(parents=True)
        p.write_text("x")
        assert infer_task_type(p) is None

    def test_random_md_not_inferred(self, tmp_path) -> None:
        p = tmp_path / "notes.md"
        p.write_text("x")
        assert infer_task_type(p) is None


class TestCheckFile:
    # denser.tokens.estimate_tokens = max(chars/4, words*1.3). "word " patterns
    # are dominated by words*1.3, so use those for precise target sizes.

    def _make_skill(self, tmp_path, n_words: int):
        p = tmp_path / "skills" / "test.md"
        p.parent.mkdir(parents=True)
        p.write_text("word " * n_words, encoding="utf-8")
        return p

    def test_missing(self, tmp_path) -> None:
        verdict, _ = check_file(tmp_path / "nonexistent.md")
        assert verdict == "missing"

    def test_skip_unrecognized(self, tmp_path) -> None:
        p = tmp_path / "random.md"
        p.write_text("hello world " * 100)
        verdict, info = check_file(p)
        assert verdict == "skip"
        assert "inferred" in info["reason"]

    def test_too_small(self, tmp_path) -> None:
        # ~50 words × 1.3 = 65 tokens < min_tokens (100)
        p = self._make_skill(tmp_path, 50)
        verdict, _ = check_file(p)
        assert verdict == "too_small"

    def test_ok(self, tmp_path) -> None:
        # 400 words × 1.3 = 520 tokens, well below skill ceiling (800)
        p = self._make_skill(tmp_path, 400)
        verdict, info = check_file(p)
        assert verdict == "ok"
        assert info["task_type"] == "skill"

    def test_warn(self, tmp_path) -> None:
        # 650 words × 1.3 = 845 tokens (in [800, 880) → WARN)
        p = self._make_skill(tmp_path, 650)
        verdict, info = check_file(p)
        assert verdict == "warn"
        assert 800 <= info["tokens"] < 880

    def test_block(self, tmp_path) -> None:
        # 1500 words × 1.3 = 1950 tokens (well above 880 block threshold)
        p = self._make_skill(tmp_path, 1500)
        verdict, info = check_file(p)
        assert verdict == "block"
        assert info["tokens"] >= 880

    def test_empty(self, tmp_path) -> None:
        p = tmp_path / "skills" / "empty.md"
        p.parent.mkdir(parents=True)
        p.write_text("", encoding="utf-8")
        verdict, _ = check_file(p)
        assert verdict == "skip"


class TestMain:
    def test_no_paths(self, capsys) -> None:
        rc = main([])
        assert rc == 0
        out = capsys.readouterr().out
        assert "nothing to check" in out.lower()

    def test_skip_via_env(self, tmp_path, monkeypatch, capsys) -> None:
        p = tmp_path / "skills" / "huge.md"
        p.parent.mkdir(parents=True)
        p.write_text("word " * 1500, encoding="utf-8")
        monkeypatch.setenv("SKIP_DENSER", "1")
        rc = main([str(p)])
        assert rc == 0
        assert "skipped" in capsys.readouterr().out.lower()

    def test_block_returns_1(self, tmp_path) -> None:
        p = tmp_path / "skills" / "huge.md"
        p.parent.mkdir(parents=True)
        p.write_text("word " * 1500, encoding="utf-8")  # ~1950 tokens
        rc = main([str(p)])
        assert rc == 1

    def test_ok_returns_0(self, tmp_path) -> None:
        p = tmp_path / "skills" / "small.md"
        p.parent.mkdir(parents=True)
        p.write_text("word " * 300, encoding="utf-8")  # ~390 tokens
        rc = main([str(p)])
        assert rc == 0

    def test_non_llm_files_skipped(self, tmp_path) -> None:
        # A big unrelated .md file is skipped without blocking.
        p = tmp_path / "just_notes.md"
        p.write_text("word " * 1500, encoding="utf-8")
        rc = main([str(p)])
        assert rc == 0
