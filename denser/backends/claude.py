"""Claude backend.

Default model: `claude-opus-4-6`. The system prompt is always sent with
`cache_control: ephemeral` so repeated calls with the same task-typed prompt
hit the 5-minute prompt cache, reducing cost by approximately 50% after the
first call.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from denser.backends.base import Backend, BackendError

logger = logging.getLogger(__name__)


DEFAULT_MODEL = "claude-opus-4-6"
# How many transient failures to swallow before giving up.
MAX_RETRIES = 3
# Base sleep (seconds) between retries; actual sleep is base × 2**attempt.
RETRY_BASE_SLEEP = 1.5


class ClaudeBackend(Backend):
    """Anthropic Claude backend with prompt caching enabled on the system prompt.

    Parameters
    ----------
    model : str
        Claude model id. Defaults to `claude-opus-4-6`.
    api_key : str | None
        API key. If `None`, read from the `ANTHROPIC_API_KEY` environment variable.
    temperature : float
        Sampling temperature. Default 0.3; compression benefits from low variance.
    """

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        temperature: float = 0.3,
    ) -> None:
        try:
            import anthropic  # noqa: F401 — imported for its side effect only
        except ImportError as exc:  # pragma: no cover — install-time check
            raise BackendError(
                "anthropic SDK not installed. Run `pip install anthropic>=0.40.0`."
            ) from exc

        import anthropic as _anthropic

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise BackendError(
                "ANTHROPIC_API_KEY is not set. Export it or pass api_key=... explicitly."
            )

        self._client = _anthropic.Anthropic(api_key=key)
        self._model = model
        self._temperature = temperature

    @property
    def name(self) -> str:
        return self._model

    @property
    def supports_caching(self) -> bool:
        return True

    def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 4096,
    ) -> str:
        system_blocks: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        messages = [{"role": "user", "content": user}]

        for attempt in range(MAX_RETRIES):
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=max_tokens,
                    temperature=self._temperature,
                    system=system_blocks,
                    messages=messages,
                )
            except Exception as e:  # network / rate limit / transient
                if attempt == MAX_RETRIES - 1:
                    raise BackendError(
                        f"Claude API failed after {MAX_RETRIES} attempts: {e}"
                    ) from e
                sleep_s = RETRY_BASE_SLEEP * (2**attempt)
                logger.warning(
                    "Claude API attempt %d failed (%s); retrying in %.1fs",
                    attempt + 1,
                    e,
                    sleep_s,
                )
                time.sleep(sleep_s)
                continue

            parts: list[str] = []
            for block in response.content:
                text = getattr(block, "text", None)
                if text:
                    parts.append(text)
            if not parts:
                raise BackendError("Claude response contained no text blocks")
            return "".join(parts)

        # Unreachable — the loop either returns or raises.
        raise BackendError("ClaudeBackend.complete fell through retry loop")
