"""OpenAI-compatible backend — supports any vendor that speaks the OpenAI API.

Concretely: OpenAI, SiliconFlow, OpenRouter, Groq, Together, Fireworks, DeepSeek
(direct), Moonshot, self-hosted vLLM / Ollama / Text Generation Inference, and
many others.

This adapter does not configure provider-specific cache controls. A compatible
provider may still perform automatic prefix caching; inspect its usage data
rather than inferring cache behavior from this adapter.

Convenience subclasses (`SiliconFlowBackend`, etc.) preset `base_url` and a
sensible default model.
"""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessageParam

from denser.backends.base import Backend, BackendError

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_SLEEP = 1.5


class OpenAICompatibleBackend(Backend):
    """Generic backend for any OpenAI-compatible Chat Completions endpoint.

    Parameters
    ----------
    base_url : str
        The API base URL, e.g. `"https://api.siliconflow.cn/v1"`. Do NOT
        include a trailing `/chat/completions`; the SDK appends endpoints.
    model : str
        Model identifier in that vendor's namespace. e.g.
        `"deepseek-ai/DeepSeek-V3"` on SiliconFlow, `"gpt-4o"` on OpenAI.
    api_key : str | None
        Explicit key, or read from `api_key_env` environment variable if
        None. The key is never stored on `self` — it's passed to the SDK
        client which manages it in-memory.
    api_key_env : str
        Environment variable name to read if `api_key` is None. Defaults
        to `"OPENAI_API_KEY"`; SiliconFlow preset uses
        `"SILICONFLOW_API_KEY"`.
    temperature : float
        Sampling temperature. Default 0.3 — compression benefits from
        low variance.
    name : str | None
        Override the backend's reported name. If None, derived from
        `<host>/<model>` of `base_url` + `model`.
    thinking_mode : str
        Provider reasoning mode: ``"provider-default"``, ``"enabled"``, or
        ``"disabled"``. Explicit modes are forwarded through the compatible
        API's ``extra_body.thinking`` field.
    """

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        api_key_env: str = "OPENAI_API_KEY",
        temperature: float = 0.3,
        name: str | None = None,
        thinking_mode: str = "provider-default",
    ) -> None:
        try:
            import openai  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise BackendError(
                "openai SDK not installed. Run `pip install openai>=1.40.0` "
                "or install the extra: `pip install denser[openai]`."
            ) from exc

        key = api_key or os.environ.get(api_key_env)
        if not key:
            raise BackendError(
                f"API key not found. Set {api_key_env} or pass api_key=... explicitly."
            )
        if thinking_mode not in {"provider-default", "enabled", "disabled"}:
            raise BackendError("thinking_mode must be provider-default, enabled, or disabled")

        import openai as _openai

        self._client = _openai.OpenAI(base_url=base_url, api_key=key)
        self._model = model
        self._temperature = temperature
        self._base_url = base_url.rstrip("/")
        self._thinking_mode = thinking_mode
        if name is not None:
            self._name = name
        else:
            host = self._base_url.split("://", 1)[-1].split("/", 1)[0]
            self._name = f"{host}/{model}"

    @property
    def name(self) -> str:
        """Return the configured provider and model label."""
        return self._name

    @property
    def supports_caching(self) -> bool:
        """Report that this adapter does not configure provider cache controls."""
        return False

    @property
    def runtime_config(self) -> dict[str, object]:
        """Return a reproducible configuration without credentials or paths."""
        return {
            "backend_kind": "openai-compatible",
            "model": self._model,
            "thinking_mode": self._thinking_mode,
        }

    def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 4096,
    ) -> str:
        """Return a chat completion for one system and user message pair."""
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        for attempt in range(MAX_RETRIES):
            try:
                if self._thinking_mode == "provider-default":
                    response = self._client.chat.completions.create(
                        model=self._model,
                        max_tokens=max_tokens,
                        temperature=self._temperature,
                        messages=messages,
                    )
                else:
                    response = self._client.chat.completions.create(
                        model=self._model,
                        max_tokens=max_tokens,
                        temperature=self._temperature,
                        messages=messages,
                        extra_body={"thinking": {"type": self._thinking_mode}},
                    )
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    raise BackendError(
                        f"OpenAI-compatible API ({self._name}) failed after "
                        f"{MAX_RETRIES} attempts: {e}"
                    ) from e
                sleep_s = RETRY_BASE_SLEEP * (2**attempt)
                logger.warning(
                    "%s attempt %d failed (%s); retrying in %.1fs",
                    self._name,
                    attempt + 1,
                    e,
                    sleep_s,
                )
                time.sleep(sleep_s)
                continue

            if not response.choices:
                raise BackendError(f"{self._name} returned no choices")
            content = response.choices[0].message.content
            if not content:
                raise BackendError(f"{self._name} returned empty content")
            return content

        raise BackendError(f"{self._name}.complete fell through retry loop")


class SiliconFlowBackend(OpenAICompatibleBackend):
    """Preconfigured backend for SiliconFlow (https://siliconflow.cn).

    Model availability and pricing change independently of denser. Pass a model
    identifier available to your SiliconFlow account.

    Set `SILICONFLOW_API_KEY` in the environment, or pass `api_key=...`.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "deepseek-ai/DeepSeek-V3",
        temperature: float = 0.3,
    ) -> None:
        super().__init__(
            base_url="https://api.siliconflow.cn/v1",
            model=model,
            api_key=api_key,
            api_key_env="SILICONFLOW_API_KEY",
            temperature=temperature,
            name=f"siliconflow/{model.rsplit('/', maxsplit=1)[-1]}",
        )
