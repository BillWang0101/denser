"""OpenAI Codex CLI backend for local, authenticated behavior replay.

The adapter invokes ``codex exec`` with an ephemeral session and a read-only
sandbox.  It injects the caller's system text through Codex's documented
``developer_instructions`` configuration key and sends the user prompt over
stdin, so neither prompt needs a temporary file.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from denser.backends.base import Backend, BackendError

DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_TIMEOUT_SECONDS = 180.0
VERSION_QUERY_TIMEOUT_SECONDS = 10.0
WINDOWS_COMMAND_LINE_LIMIT = 30_000


@dataclass(frozen=True)
class CodexCliUsage:
    """Token usage reported by one completed ``codex exec`` turn."""

    input_tokens: int = 0
    cached_input_tokens: int = 0
    cache_write_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0

    def to_dict(self) -> dict[str, int]:
        """Return the usage counters as a JSON-serializable mapping."""
        return {
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "cache_write_input_tokens": self.cache_write_input_tokens,
            "output_tokens": self.output_tokens,
            "reasoning_output_tokens": self.reasoning_output_tokens,
        }


@dataclass(frozen=True)
class CodexCliCallMetadata:
    """Non-sensitive execution evidence for one CLI invocation."""

    status: str
    exit_code: int | None
    duration_ms: int
    usage: CodexCliUsage | None = None
    transport_fallback: bool = False

    def to_dict(self) -> dict[str, object]:
        """Return non-sensitive call metadata as a serializable mapping."""
        return {
            "status": self.status,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "usage": None if self.usage is None else self.usage.to_dict(),
            "transport_fallback": self.transport_fallback,
        }


@dataclass(frozen=True)
class _ParsedEvents:
    final_message: str | None
    usage: CodexCliUsage | None
    turn_failed: bool
    transport_fallback: bool


def _is_desktop_bundled_codex(path: Path) -> bool:
    normalized = str(path).replace("/", "\\").casefold()
    return "\\program files\\windowsapps\\openai.codex_" in normalized


def _discover_codex_cli() -> Path:
    configured = os.environ.get("DENSER_CODEX_CLI")
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured).expanduser())

    if os.name == "nt":
        app_data = os.environ.get("APPDATA")
        if app_data:
            candidates.append(Path(app_data) / "npm" / "codex.cmd")
        for command in ("codex.cmd", "codex.exe", "codex"):
            resolved = shutil.which(command)
            if resolved:
                candidates.append(Path(resolved))
    else:
        resolved = shutil.which("codex")
        if resolved:
            candidates.append(Path(resolved))

    for candidate in candidates:
        path = candidate.resolve()
        if path.is_file() and not _is_desktop_bundled_codex(path):
            return path
    raise BackendError(
        "Independent Codex CLI not found. Install @openai/codex or pass --codex-cli-path; "
        "the desktop app's WindowsApps binary is not a supported execution path."
    )


def _codex_launch_prefix(executable: Path, *, windows: bool | None = None) -> list[str]:
    """Avoid Windows npm shim re-parsing of developer-instruction characters."""
    if windows is None:
        windows = os.name == "nt"
    if not windows or executable.suffix.casefold() not in {".cmd", ".ps1"}:
        return [str(executable)]

    package_entry = executable.parent / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
    if not package_entry.is_file():
        return [str(executable)]

    bundled_node = executable.parent / "node.exe"
    node = str(bundled_node) if bundled_node.is_file() else shutil.which("node.exe")
    if node is None:
        node = shutil.which("node")
    if node is None:
        raise BackendError("Node.js was not found for the independent npm Codex CLI")
    return [node, str(package_entry)]


def _parse_codex_cli_version(output: str) -> str | None:
    """Extract only the non-sensitive version number from ``codex --version``."""
    match = re.search(
        r"(?im)^\s*codex(?:-cli)?\s+v?"
        r"([0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?)\s*$",
        output,
    )
    return None if match is None else match.group(1)


def _positive_int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _parse_events(stdout: str, stderr: str) -> _ParsedEvents:
    final_message: str | None = None
    usage: CodexCliUsage | None = None
    turn_failed = False
    transport_fallback = "falling back to http" in stderr.casefold()
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        event_type = event.get("type")
        if event_type == "turn.failed":
            turn_failed = True
        if event_type == "item.completed":
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") == "agent_message":
                text = item.get("text")
                if isinstance(text, str):
                    final_message = text
            message = item.get("message") if isinstance(item, dict) else None
            if isinstance(message, str) and "falling back" in message.casefold():
                transport_fallback = True
        if event_type == "turn.completed":
            raw_usage = event.get("usage")
            if isinstance(raw_usage, dict):
                usage = CodexCliUsage(
                    input_tokens=_positive_int(raw_usage.get("input_tokens")),
                    cached_input_tokens=_positive_int(raw_usage.get("cached_input_tokens")),
                    cache_write_input_tokens=_positive_int(
                        raw_usage.get("cache_write_input_tokens")
                    ),
                    output_tokens=_positive_int(raw_usage.get("output_tokens")),
                    reasoning_output_tokens=_positive_int(raw_usage.get("reasoning_output_tokens")),
                )
    return _ParsedEvents(
        final_message=final_message,
        usage=usage,
        turn_failed=turn_failed,
        transport_fallback=transport_fallback,
    )


class CodexCliBackend(Backend):
    """Run completions through an independently installed OpenAI Codex CLI."""

    def __init__(
        self,
        *,
        executable: str | Path | None = None,
        model: str = DEFAULT_MODEL,
        reasoning_effort: str = "medium",
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        respect_system_proxy: bool = False,
    ) -> None:
        path = Path(executable).expanduser().resolve() if executable is not None else None
        if path is None:
            path = _discover_codex_cli()
        if not path.is_file():
            raise BackendError(f"Codex CLI executable not found: {path}")
        if _is_desktop_bundled_codex(path):
            raise BackendError(
                "Refusing the desktop app's WindowsApps binary; install the independent Codex CLI."
            )
        if not model.strip():
            raise BackendError("Codex CLI model cannot be empty")
        if reasoning_effort not in {"none", "low", "medium", "high", "xhigh", "max"}:
            raise BackendError(f"Unsupported Codex reasoning effort: {reasoning_effort}")
        if timeout_seconds <= 0:
            raise BackendError("Codex CLI timeout must be greater than zero")

        self._executable = path
        self._model = model
        self._reasoning_effort = reasoning_effort
        self._timeout_seconds = timeout_seconds
        self._respect_system_proxy = respect_system_proxy
        self._cli_version: str | None = None
        self._cli_version_checked = False
        self._last_call_metadata: CodexCliCallMetadata | None = None

    @property
    def name(self) -> str:
        """Return the backend name with its configured model identifier."""
        return f"codex-cli/{self._model}"

    @property
    def supports_caching(self) -> bool:
        """Report that this adapter does not expose explicit prompt caching."""
        return False

    @property
    def runtime_config(self) -> dict[str, object]:
        """Return the reproducibility settings safe to include in reports."""
        return {
            "backend_kind": "codex-cli",
            "model": self._model,
            "codex_cli_version": self._get_cli_version(),
            "reasoning_effort": self._reasoning_effort,
            "timeout_seconds": self._timeout_seconds,
            "ephemeral": True,
            "sandbox": "read-only",
            "ignore_user_config": True,
            "respect_system_proxy": self._respect_system_proxy,
            "disabled_features": ["apps", "memories", "multi_agent"],
        }

    @property
    def last_call_metadata(self) -> dict[str, object] | None:
        """Return sanitized evidence for the most recent invocation."""
        if self._last_call_metadata is None:
            return None
        return self._last_call_metadata.to_dict()

    def _get_cli_version(self) -> str | None:
        if self._cli_version_checked:
            return self._cli_version
        self._cli_version_checked = True
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        try:
            command = [*_codex_launch_prefix(self._executable), "--version"]
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=VERSION_QUERY_TIMEOUT_SECONDS,
                check=False,
                creationflags=creationflags,
            )
        except (BackendError, OSError, subprocess.TimeoutExpired):
            return None
        if completed.returncode != 0:
            return None
        self._cli_version = _parse_codex_cli_version(f"{completed.stdout}\n{completed.stderr}")
        return self._cli_version

    def _build_command(self, system: str) -> list[str]:
        developer_value = json.dumps(system, ensure_ascii=False)
        config_argument = f"developer_instructions={developer_value}"
        if os.name == "nt" and len(config_argument) >= WINDOWS_COMMAND_LINE_LIMIT:
            raise BackendError(
                "Instruction asset is too large for safe Windows command-line injection"
            )

        command = [
            *_codex_launch_prefix(self._executable),
            "exec",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--ignore-user-config",
        ]
        if self._respect_system_proxy:
            command.extend(("--enable", "respect_system_proxy"))
        command.extend(
            (
                "--disable",
                "apps",
                "--disable",
                "memories",
                "--disable",
                "multi_agent",
                "--model",
                self._model,
                "--color",
                "never",
                "--json",
                "-c",
                config_argument,
                "-c",
                f'model_reasoning_effort="{self._reasoning_effort}"',
                "-c",
                'model_reasoning_summary="none"',
                "-",
            )
        )
        return command

    def _run(self, command: list[str], user: str) -> subprocess.CompletedProcess[str]:
        started = time.monotonic()
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        try:
            return subprocess.run(
                command,
                input=user,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._timeout_seconds,
                check=False,
                creationflags=creationflags,
            )
        except subprocess.TimeoutExpired as exc:
            duration_ms = round((time.monotonic() - started) * 1000)
            self._last_call_metadata = CodexCliCallMetadata(
                status="timeout",
                exit_code=None,
                duration_ms=duration_ms,
            )
            raise BackendError(
                f"Codex CLI timed out after {self._timeout_seconds:g} seconds"
            ) from exc
        except OSError as exc:
            duration_ms = round((time.monotonic() - started) * 1000)
            self._last_call_metadata = CodexCliCallMetadata(
                status="launch_error",
                exit_code=None,
                duration_ms=duration_ms,
            )
            raise BackendError(f"Codex CLI could not be launched: {type(exc).__name__}") from exc

    def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 4096,
    ) -> str:
        """Return the final Codex agent message from a read-only ephemeral turn.

        Codex CLI does not currently expose a hard maximum-output-token flag;
        ``max_tokens`` remains part of the shared backend protocol but is not
        forwarded.  Replay matchers still enforce the expected final output.
        """
        del max_tokens
        if not system.strip():
            raise BackendError("Codex CLI developer instructions cannot be empty")
        if not user.strip():
            raise BackendError("Codex CLI user prompt cannot be empty")

        command = self._build_command(system)
        started = time.monotonic()
        self._last_call_metadata = None
        completed = self._run(command, user)
        duration_ms = round((time.monotonic() - started) * 1000)
        parsed = _parse_events(completed.stdout, completed.stderr)
        status = (
            "completed"
            if completed.returncode == 0
            and not parsed.turn_failed
            and parsed.final_message is not None
            else "failed"
        )
        self._last_call_metadata = CodexCliCallMetadata(
            status=status,
            exit_code=completed.returncode,
            duration_ms=duration_ms,
            usage=parsed.usage,
            transport_fallback=parsed.transport_fallback,
        )
        if status != "completed":
            raise BackendError(
                f"Codex CLI failed with exit status {completed.returncode}; "
                "inspect local CLI diagnostics for details"
            )
        if parsed.final_message is None or not parsed.final_message.strip():
            raise BackendError("Codex CLI returned an empty final message")
        return parsed.final_message


__all__ = [
    "CodexCliBackend",
    "CodexCliCallMetadata",
    "CodexCliUsage",
]
