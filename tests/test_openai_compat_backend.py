"""Tests for the generic OpenAI-compatible backend."""

from __future__ import annotations

import sys
from types import SimpleNamespace

from denser.backends.openai_compat import OpenAICompatibleBackend


class _FakeCompletions:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        extra_body = kwargs.get("extra_body")
        thinking = extra_body.get("thinking") if isinstance(extra_body, dict) else None
        content = "OK" if thinking == {"type": "disabled"} else None
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class _FakeOpenAI:
    completions = _FakeCompletions()

    def __init__(self, **_kwargs: object) -> None:
        self.chat = SimpleNamespace(completions=self.completions)


def test_can_disable_provider_thinking_for_short_replay_outputs(monkeypatch) -> None:
    """Forward an explicit non-thinking mode to compatible providers."""
    fake_module = SimpleNamespace(OpenAI=_FakeOpenAI)
    monkeypatch.setitem(sys.modules, "openai", fake_module)
    _FakeOpenAI.completions.calls.clear()

    backend = OpenAICompatibleBackend(
        base_url="https://api.example.test",
        model="reasoning-model",
        api_key="not-a-real-key",
        thinking_mode="disabled",
    )

    assert backend.complete(system="rules", user="request", max_tokens=128) == "OK"
    assert _FakeOpenAI.completions.calls[0]["extra_body"] == {"thinking": {"type": "disabled"}}
    assert backend.runtime_config == {
        "backend_kind": "openai-compatible",
        "model": "reasoning-model",
        "thinking_mode": "disabled",
    }
