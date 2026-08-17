"""Tests for the independent Codex CLI backend."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from denser.backends.base import BackendError
from denser.backends.codex_cli import (
    CodexCliBackend,
    _codex_launch_prefix,
    _is_desktop_bundled_codex,
    _parse_codex_cli_version,
)


def _cli_file(tmp_path: Path) -> Path:
    path = tmp_path / "codex.cmd"
    path.write_text("@echo off\n", encoding="utf-8")
    return path


def test_codex_cli_parses_final_message_and_sanitized_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = _cli_file(tmp_path)
    captured: dict[str, object] = {}
    events = [
        {"type": "thread.started", "thread_id": "do-not-record"},
        {
            "type": "item.completed",
            "item": {"type": "agent_message", "text": "ACTION=PREVIEW"},
        },
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 120,
                "cached_input_tokens": 20,
                "cache_write_input_tokens": 0,
                "output_tokens": 8,
                "reasoning_output_tokens": 2,
            },
        },
    ]

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured.update(kwargs)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="\n".join(json.dumps(event) for event in events),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    backend = CodexCliBackend(
        executable=cli,
        model="gpt-test",
        reasoning_effort="low",
        respect_system_proxy=True,
        capability_profile="text-only",
    )

    output = backend.complete(system="SYSTEM RULE", user="Preview it", max_tokens=16)

    assert output == "ACTION=PREVIEW"
    command = captured["command"]
    assert isinstance(command, list)
    assert command[:6] == [
        str(cli.resolve()),
        "exec",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--ignore-user-config",
    ]
    assert "respect_system_proxy" in command
    for feature in ("plugins", "skill_search", "shell_tool", "hooks"):
        feature_index = command.index(feature)
        assert command[feature_index - 1] == "--disable"
    assert captured["input"] == "Preview it"
    config = command[command.index("-c") + 1]
    assert isinstance(config, str)
    injected = json.loads(config.removeprefix("developer_instructions="))
    assert injected.endswith("\n\nSYSTEM RULE")
    assert "all required input is already present" in injected
    assert "Do not request files, tools, network access" in injected
    metadata = backend.last_call_metadata
    assert metadata is not None
    assert metadata["status"] == "completed"
    assert metadata["exit_code"] == 0
    assert metadata["usage"] == {
        "input_tokens": 120,
        "cached_input_tokens": 20,
        "cache_write_input_tokens": 0,
        "output_tokens": 8,
        "reasoning_output_tokens": 2,
    }
    assert "thread_id" not in metadata


def test_codex_cli_failure_does_not_expose_diagnostic_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = _cli_file(tmp_path)

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        event = {"type": "turn.failed", "error": {"message": "secret-bearing detail"}}
        return subprocess.CompletedProcess(
            command, 1, stdout=json.dumps(event), stderr="token=secret"
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    backend = CodexCliBackend(executable=cli)

    with pytest.raises(BackendError) as exc_info:
        backend.complete(system="system", user="user")

    assert "secret" not in str(exc_info.value)
    assert backend.last_call_metadata is not None
    assert backend.last_call_metadata["status"] == "failed"
    assert backend.last_call_metadata["exit_code"] == 1


def test_codex_cli_timeout_records_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cli = _cli_file(tmp_path)

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(command, timeout=2)

    monkeypatch.setattr(subprocess, "run", fake_run)
    backend = CodexCliBackend(executable=cli, timeout_seconds=2)

    with pytest.raises(BackendError, match="timed out"):
        backend.complete(system="system", user="user")

    assert backend.last_call_metadata is not None
    assert backend.last_call_metadata["status"] == "timeout"
    assert backend.last_call_metadata["exit_code"] is None


def test_rejects_desktop_bundled_windowsapps_path() -> None:
    path = Path(r"C:\Program Files\WindowsApps\OpenAI.Codex_1.0_x64__id\app\resources\codex.exe")
    assert _is_desktop_bundled_codex(path)


def test_windows_npm_shim_launches_package_entry_through_node(tmp_path: Path) -> None:
    cli = _cli_file(tmp_path)
    node = tmp_path / "node.exe"
    node.write_text("", encoding="utf-8")
    package_entry = tmp_path / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
    package_entry.parent.mkdir(parents=True)
    package_entry.write_text("", encoding="utf-8")

    assert _codex_launch_prefix(cli, windows=True) == [str(node), str(package_entry)]


def test_codex_cli_runtime_config_is_reproducible_and_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = _cli_file(tmp_path)
    calls = 0

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="codex-cli 0.147.0\n",
            stderr="token=do-not-record",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    backend = CodexCliBackend(
        executable=cli,
        model="gpt-test",
        reasoning_effort="high",
        timeout_seconds=42,
        respect_system_proxy=True,
    )

    assert backend.runtime_config == {
        "backend_kind": "codex-cli",
        "model": "gpt-test",
        "codex_cli_version": "0.147.0",
        "reasoning_effort": "high",
        "timeout_seconds": 42,
        "ephemeral": True,
        "sandbox": "read-only",
        "ignore_user_config": True,
        "respect_system_proxy": True,
        "capability_profile": "standard",
        "profile_instruction_version": None,
        "disabled_features": ["apps", "memories", "multi_agent"],
    }
    assert backend.runtime_config["codex_cli_version"] == "0.147.0"
    assert calls == 1
    assert str(cli) not in json.dumps(backend.runtime_config)
    assert "do-not-record" not in json.dumps(backend.runtime_config)


def test_codex_cli_rejects_unknown_capability_profile(tmp_path: Path) -> None:
    cli = _cli_file(tmp_path)

    with pytest.raises(BackendError, match="Unsupported Codex capability profile"):
        CodexCliBackend(executable=cli, capability_profile="everything")


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("codex-cli 0.147.0", "0.147.0"),
        ("codex v1.2.3-beta.1", "1.2.3-beta.1"),
        ("untrusted diagnostic 1.2.3 token=secret", None),
    ],
)
def test_parse_codex_cli_version(output: str, expected: str | None) -> None:
    assert _parse_codex_cli_version(output) == expected
