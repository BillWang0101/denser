"""Explicit token-counting methods for evidence and local previews.

`HeuristicTokenCounter` is offline and approximate. `AnthropicTokenCounter` is
provider-aware and fails explicitly instead of silently relabeling an estimate
as an exact count. The historical function helpers remain for compatibility.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    import anthropic

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"\S+")


class TokenCountError(RuntimeError):
    """Raised when a requested counting method cannot produce a measurement."""


@runtime_checkable
class TokenCounter(Protocol):
    """Narrow counting adapter used by optimization evidence."""

    method: str
    provider: str | None
    model: str | None
    exact: bool

    def count(self, text: str) -> int:
        """Return a token count or raise `TokenCountError`."""
        ...


class HeuristicTokenCounter:
    """Fast offline estimator, explicitly labeled as approximate."""

    method = "heuristic-v1"
    provider: str | None = None
    model: str | None = None
    exact = False

    def count(self, text: str) -> int:
        """Return an offline approximate token count."""
        return estimate_tokens(text)


class AnthropicTokenCounter:
    """Strict adapter for Anthropic's provider token-counting endpoint."""

    method = "anthropic-messages-count-tokens"
    provider = "anthropic"
    exact = True

    def __init__(
        self,
        *,
        model: str = "claude-opus-4-6",
        client: Any | None = None,
    ) -> None:
        if client is None:
            try:
                import anthropic as anthropic_sdk
            except ImportError as exc:  # pragma: no cover - install-time check
                raise TokenCountError("Anthropic SDK is not installed") from exc
            try:
                client = anthropic_sdk.Anthropic()
            except Exception as exc:
                raise TokenCountError(
                    f"Anthropic counter initialization failed: {type(exc).__name__}"
                ) from exc
        self.model = model
        self._client = client

    def count(self, text: str) -> int:
        """Return a provider token count or raise ``TokenCountError``."""
        if not text:
            return 0
        try:
            result = self._client.messages.count_tokens(
                model=self.model,
                messages=[{"role": "user", "content": text}],
            )
            return int(result.input_tokens)
        except Exception as exc:
            raise TokenCountError(f"Anthropic token count failed: {type(exc).__name__}") from exc


def estimate_tokens(text: str) -> int:
    """Fast tokenizer-free estimate.

    Uses a hybrid of character length and word count. Empirically within ~15%
    of the true Claude tokenizer on English text; less accurate on code or
    non-Latin scripts. Do not use for billing or precise reporting — use
    `count_tokens_claude` instead.
    """
    if not text:
        return 0

    # Heuristic: max of (chars/4) and (words × 1.3).
    # For text-heavy inputs the char estimate wins; for whitespace-sparse
    # inputs the word estimate prevents under-counting.
    char_est = len(text) / 4.0
    word_count = len(_WORD_RE.findall(text))
    word_est = word_count * 1.3
    return max(1, int(round(max(char_est, word_est))))


def count_tokens_claude(
    text: str,
    model: str = "claude-opus-4-6",
    client: anthropic.Anthropic | None = None,
) -> int:
    """Count tokens exactly using Anthropic's API.

    Falls back to `estimate_tokens` if the anthropic SDK is not installed or
    the API call fails (network error, missing key). Warns on fallback.

    Parameters
    ----------
    text : str
        The text to count.
    model : str
        Claude model id. The tokenizer is shared across Claude models, so this
        value is typically irrelevant but the API requires it.
    client : anthropic.Anthropic | None
        Optional pre-configured client. If None, we create one from environment.
    """
    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic SDK not installed; falling back to estimate")
        return estimate_tokens(text)

    if client is None:
        client = anthropic.Anthropic()

    try:
        # The messages.count_tokens endpoint requires messages in the request.
        result = client.messages.count_tokens(
            model=model,
            messages=[{"role": "user", "content": text}],
        )
        return int(result.input_tokens)
    except Exception as e:
        logger.warning(
            "count_tokens_claude API failed (%s); falling back to estimate",
            type(e).__name__,
        )
        return estimate_tokens(text)


def compression_ratio(original: str, compressed: str, *, exact: bool = False) -> float:
    """Return compressed_tokens / original_tokens.

    Uses the fast estimator by default. Set `exact=True` to invoke the API.
    """
    counter = count_tokens_claude if exact else estimate_tokens
    orig = counter(original)
    comp = counter(compressed)
    if orig == 0:
        return 1.0
    return comp / orig
