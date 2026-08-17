"""Tests for explicit token-counting adapters."""

from __future__ import annotations

import pytest

from denser.tokens import (
    AnthropicTokenCounter,
    HeuristicTokenCounter,
    TokenCounter,
    TokenCountError,
)


class _Result:
    input_tokens = 17


class _Messages:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    def count_tokens(self, **kwargs):
        self.calls += 1
        if self.fail:
            raise RuntimeError("secret-bearing provider detail")
        return _Result()


class _Client:
    def __init__(self, *, fail: bool = False) -> None:
        self.messages = _Messages(fail=fail)


class TestTokenCounters:
    def test_heuristic_is_explicitly_approximate(self) -> None:
        counter = HeuristicTokenCounter()
        assert isinstance(counter, TokenCounter)
        assert counter.count("some text") > 0
        assert counter.method == "heuristic-v1"
        assert not counter.exact

    def test_anthropic_counter_reports_provider_measurement(self) -> None:
        client = _Client()
        counter = AnthropicTokenCounter(model="test-model", client=client)
        assert counter.count("some text") == 17
        assert counter.provider == "anthropic"
        assert counter.model == "test-model"
        assert counter.exact
        assert client.messages.calls == 1

    def test_anthropic_counter_fails_without_silent_fallback(self) -> None:
        counter = AnthropicTokenCounter(client=_Client(fail=True))
        with pytest.raises(TokenCountError, match="RuntimeError") as exc_info:
            counter.count("some text")
        assert "secret-bearing" not in str(exc_info.value)

    def test_empty_provider_count_avoids_network_call(self) -> None:
        client = _Client()
        counter = AnthropicTokenCounter(client=client)
        assert counter.count("") == 0
        assert client.messages.calls == 0
