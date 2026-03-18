from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from app.core.config import get_settings

try:  # pragma: no cover - optional import path
    from openai import OpenAI
except Exception:  # pragma: no cover - optional import path
    OpenAI = None


settings = get_settings()
T = TypeVar("T", bound=BaseModel)


class BaseLLMProvider:
    def is_live(self) -> bool:
        return False

    def generate_structured(self, *, model: str, system_prompt: str, user_prompt: str, schema: type[T]) -> T:
        raise NotImplementedError


class MockLLMProvider(BaseLLMProvider):
    def generate_structured(self, *, model: str, system_prompt: str, user_prompt: str, schema: type[T]) -> T:
        raise RuntimeError("MockLLMProvider does not synthesize content directly")


class OpenAIResponsesProvider(BaseLLMProvider):
    def __init__(self) -> None:
        if OpenAI is None:
            raise RuntimeError("openai package is not installed")
        client_kwargs: dict[str, Any] = {}
        if settings.openai_api_key:
            client_kwargs["api_key"] = settings.openai_api_key
        if settings.openai_base_url:
            client_kwargs["base_url"] = settings.openai_base_url
        self.client = OpenAI(**client_kwargs)

    def is_live(self) -> bool:
        return bool(settings.openai_enable_live and settings.openai_api_key)

    def generate_structured(self, *, model: str, system_prompt: str, user_prompt: str, schema: type[T]) -> T:
        response = self.client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            text_format=schema,
        )
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise RuntimeError("OpenAI response did not include parsed structured output")
        if not isinstance(parsed, schema):
            return schema.model_validate(parsed)
        return parsed


def get_llm_provider() -> BaseLLMProvider:
    if settings.openai_enable_live and settings.openai_api_key:
        return OpenAIResponsesProvider()
    return MockLLMProvider()

