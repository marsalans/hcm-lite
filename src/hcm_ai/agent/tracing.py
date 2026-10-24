from agents import set_trace_processors, set_tracing_export_api_key

from hcm_ai.config import Settings


def configure_tracing(settings: Settings) -> bool:
    """Export Agents SDK traces to the OpenAI dashboard only with a dedicated tracing key.

    The Groq/Gemini keys are never used here. Without a key, exporting is switched off so the SDK
    does not try (and fail) to upload. Returns True when export is enabled. Idempotent.
    """
    key = settings.openai_tracing_key
    if key is None:
        set_trace_processors([])
        return False
    set_tracing_export_api_key(key.get_secret_value())
    return True
