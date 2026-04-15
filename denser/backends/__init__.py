"""Compression backends.

A backend is any implementation of the `Backend` protocol in `base.py` that
takes a system + user message pair and returns a completion. v0.1 ships the
Claude Opus 4.6 backend; future versions will add OpenAI, Gemini, and local
backends.
"""

from denser.backends.base import Backend, BackendError
from denser.backends.claude import ClaudeBackend
from denser.backends.openai_compat import OpenAICompatibleBackend, SiliconFlowBackend

__all__ = [
    "Backend",
    "BackendError",
    "ClaudeBackend",
    "OpenAICompatibleBackend",
    "SiliconFlowBackend",
]
