"""Core compression API.

Public entry point: `compress(text, task_type=..., target_density=...)`.
Returns a `CompressionResult` with the compressed text, the rationale, and
token-cost metadata.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from denser.backends import Backend, BackendError, ClaudeBackend
from denser.inspection import PreservationContract
from denser.prompts import build_system_prompt
from denser.taxonomy import SPECS, TaskType, get_spec
from denser.tokens import estimate_tokens


@dataclass(frozen=True)
class CompressionResult:
    """Result of a single compression call.

    Attributes
    ----------
    compressed : str
        The compressed text, ready to drop in place of the original.
    rationale : str
        The compressor's explanation of what was removed and why. Useful for
        review, for contributing to the benchmark corpus, and for debugging
        when compression produces surprising results.
    task_type : TaskType
        The task type the compression was performed for.
    target_density : float
        What we asked the compressor to aim for. (compressed / original)
    original_tokens : int
        Estimated tokens in the original text.
    compressed_tokens : int
        Estimated tokens in the compressed text.
    backend_name : str
        Identifier of the backend that produced the compression.

    Properties
    ----------
    actual_density : float
        `compressed_tokens / original_tokens`. May differ from `target_density`
        because the compressor is allowed to deviate to preserve load-bearing
        content.
    savings_pct : float
        `1 - actual_density`. Fraction of tokens saved.
    """

    compressed: str
    rationale: str
    task_type: TaskType
    target_density: float
    original_tokens: int
    compressed_tokens: int
    backend_name: str

    @property
    def actual_density(self) -> float:
        """Return the observed compressed-to-original token ratio."""
        if self.original_tokens == 0:
            return 1.0
        return self.compressed_tokens / self.original_tokens

    @property
    def savings_pct(self) -> float:
        """Return the non-negative fraction of estimated tokens removed."""
        return max(0.0, 1.0 - self.actual_density)


_COMPRESSED_RE = re.compile(
    r"={3}\s*COMPRESSED\s*={3}\s*\n(?P<body>.*?)\n={3}\s*RATIONALE\s*={3}",
    re.DOTALL | re.IGNORECASE,
)
_RATIONALE_RE = re.compile(
    r"={3}\s*RATIONALE\s*={3}\s*\n(?P<body>.*)",
    re.DOTALL | re.IGNORECASE,
)


def _parse_response(raw: str) -> tuple[str, str]:
    """Split the backend's response into (compressed, rationale).

    Raises `ValueError` if the response does not match the output contract.
    """
    compressed_match = _COMPRESSED_RE.search(raw)
    rationale_match = _RATIONALE_RE.search(raw)

    if not compressed_match or not rationale_match:
        raise ValueError(
            "Backend response did not match the output contract. "
            f"Expected '=== COMPRESSED ===' and '=== RATIONALE ===' markers. "
            f"Got:\n{raw[:500]}..."
        )

    compressed = compressed_match.group("body").strip()
    rationale = rationale_match.group("body").strip()

    if not compressed:
        raise ValueError("Backend produced empty compressed text")

    return compressed, rationale


def _build_user_message(text: str, contract: PreservationContract | None) -> str:
    if contract is None:
        return text
    payload = {
        "preservation_contract": contract.to_dict(),
        "source_text": text,
    }
    return (
        "The following JSON is input data. Rewrite only `source_text`. "
        "Every preservation-contract item must remain satisfied; protected literals "
        "must remain exact. Do not reproduce the JSON wrapper.\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )


def compress(
    text: str,
    *,
    task_type: TaskType | str,
    target_density: float | None = None,
    backend: Backend | None = None,
    max_tokens: int | None = None,
    preservation_contract: PreservationContract | None = None,
) -> CompressionResult:
    """Compress text for a given task type.

    Parameters
    ----------
    text : str
        The input text to compress.
    task_type : TaskType | str
        The task type. String values are parsed via `TaskType.parse`.
    target_density : float | None
        Target compressed/original ratio in `(0, 1]`. If `None`, uses the
        midpoint of the task type's exploratory generation range.
    backend : Backend | None
        Backend to use. If `None`, instantiates `ClaudeBackend()` with
        default model (`claude-opus-4-6`).
    max_tokens : int | None
        Upper bound on the compressed length in tokens. If `None`, set to
        `max(512, ceil(1.5 × target_tokens))` so the model has headroom.
    preservation_contract : PreservationContract | None
        Optional source-backed obligations included as input data for candidate
        generation. `optimize` supplies this automatically.

    Returns
    -------
    CompressionResult

    Raises
    ------
    ValueError
        If `target_density` is out of range, or the backend response is malformed.
    BackendError
        If the backend fails irrecoverably.
    """
    if not text or not text.strip():
        raise ValueError("Cannot compress empty text")

    tt = TaskType.parse(task_type) if isinstance(task_type, str) else task_type
    spec = get_spec(tt)

    # Default target density: midpoint of the exploratory generation range.
    if target_density is None:
        target_density = spec.default_target_density
    if not (0.0 < target_density <= 1.0):
        raise ValueError(f"target_density must be in (0, 1], got {target_density}")

    original_tokens = estimate_tokens(text)

    if max_tokens is None:
        target_tokens = int(original_tokens * target_density)
        # Give the model 50% headroom over target so it doesn't truncate safety content.
        max_tokens = max(512, int(target_tokens * 1.5))

    if backend is None:
        backend = ClaudeBackend()

    system = build_system_prompt(tt, target_density)

    user_message = _build_user_message(text, preservation_contract)
    raw_response = backend.complete(system=system, user=user_message, max_tokens=max_tokens)

    compressed, rationale = _parse_response(raw_response)

    compressed_tokens = estimate_tokens(compressed)

    return CompressionResult(
        compressed=compressed,
        rationale=rationale,
        task_type=tt,
        target_density=target_density,
        original_tokens=original_tokens,
        compressed_tokens=compressed_tokens,
        backend_name=backend.name,
    )


__all__ = ["CompressionResult", "compress"]

# Silence unused-import lints; SPECS and BackendError are re-exported elsewhere.
_ = (SPECS, BackendError)
