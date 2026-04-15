"""OpenAI-compatible backend — supports any vendor that speaks the OpenAI API.

Concretely: OpenAI, SiliconFlow, OpenRouter, Groq, Together, Fireworks, DeepSeek
(direct), Moonshot, self-hosted vLLM / Ollama / Text Generation Inference, and
many others.

Prompt caching is NOT enabled (only Anthropic's API supports it at the protocol
level). For high-frequency use against a Claude-backed endpoint, use
`ClaudeBackend` instead.

Convenience subclasses (`SiliconFlowBackend`, etc.) preset `base_url` and a
sensible default model.
"""

from __future__ import annotations

import logging
import os
import time

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

        import openai as _openai

        self._client = _openai.OpenAI(base_url=base_url, api_key=key)
        self._model = model
        self._temperature = temperature
        self._base_url = base_url.rstrip("/")
        if name is not None:
            self._name = name
        else:
            host = self._base_url.split("://", 1)[-1].split("/", 1)[0]
            self._name = f"{host}/{model}"

    @property
    def name(self) -> str:
        return self._name

    @property
    def supports_caching(self) -> bool:
        return False

    def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 4096,
    ) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        for attempt in range(MAX_RETRIES):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    max_tokens=max_tokens,
                    temperature=self._temperature,
                    messages=messages,
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

            choices = getattr(response, "choices", None)
            if not choices:
                raise BackendError(f"{self._name} returned no choices")
            msg = choices[0].message
            content = getattr(msg, "content", None)
            if not content:
                raise BackendError(f"{self._name} returned empty content")
            return content

        raise BackendError(f"{self._name}.complete fell through retry loop")


class SiliconFlowBackend(OpenAICompatibleBackend):
    """Preconfigured backend for SiliconFlow (https://siliconflow.cn).

    Free-tier friendly; the default model (`deepseek-ai/DeepSeek-V3`) is
    available on SiliconFlow's free plan at the time of writing. Pass
    `model="Qwen/Qwen2.5-72B-Instruct"` or similar for alternatives.

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
