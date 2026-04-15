"""Backend protocol.

A backend knows how to take a system + user prompt pair and return a
completion. Backends are responsible for their own authentication, retry,
and caching logic.

The protocol is intentionally narrow: backend complexity (streaming, tool
use, etc.) stays encapsulated; the rest of denser treats backends as pure
text-in / text-out.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class BackendError(RuntimeError):
    """Raised when a backend fails after internal retries are exhausted."""


@runtime_checkable
class Backend(Protocol):
    """The interface every backend must satisfy."""

    def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 4096,
    ) -> str:
        """Given a system + user message pair, return the model's completion text.

        Raises `BackendError` on unrecoverable failure.
        """
        ...

    @property
    def name(self) -> str:
        """Stable identifier for this backend, e.g. `"claude-opus-4-6"`."""
        ...

    @property
    def supports_caching(self) -> bool:
        """Whether the backend will cache stable system prompts between calls."""
        ...
