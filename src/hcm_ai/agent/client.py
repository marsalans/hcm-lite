from functools import lru_cache

from agents import Model, OpenAIChatCompletionsModel
from openai import AsyncOpenAI

from hcm_ai.config import Settings


@lru_cache
def _client(base_url: str, api_key: str, timeout: float) -> AsyncOpenAI:
    return AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=timeout, max_retries=0)


def build_models(
    settings: Settings,
    *,
    fast: bool = False,
    groq_client: AsyncOpenAI | None = None,
    gemini_client: AsyncOpenAI | None = None,
) -> list[Model]:
    """Primary Groq model, then Gemini (OpenAI-compatible endpoint) if a key is configured.

    Clients are injectable so tests can run the real SDK against a mock transport.
    """
    groq = groq_client or _client(
        settings.groq_base_url,
        settings.groq_api_key.get_secret_value(),
        settings.ai_timeout_seconds,
    )
    models: list[Model] = [
        OpenAIChatCompletionsModel(
            model=settings.fast_model if fast else settings.chat_model, openai_client=groq
        )
    ]
    if gemini_client is not None or settings.gemini_api_key is not None:
        gemini = gemini_client or _client(
            settings.gemini_base_url,
            settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else "",
            settings.ai_timeout_seconds,
        )
        models.append(OpenAIChatCompletionsModel(model=settings.gemini_model, openai_client=gemini))
    return models
