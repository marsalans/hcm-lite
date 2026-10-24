import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from agents import (
    Agent,
    ModelSettings,
    RunConfig,
    RunContextWrapper,
    RunHooks,
    Runner,
    Tool,
)
from agents import Model as AgentModel
from openai import APIError, RateLimitError
from openai.types.shared import Reasoning

from hcm_ai.agent.client import build_models
from hcm_ai.agent.prompts import chat_instructions
from hcm_ai.config import Settings, get_settings
from hcm_ai.services.ai_tools import ALL_TOOLS
from hcm_ai.services.interfaces import AgentDeps

log = logging.getLogger(__name__)

FALLBACK_MESSAGE = "Sorry, the AI assistant couldn't answer in time. Please try again in a moment."

AgentFactory = Callable[[AgentModel], Agent[AgentDeps]]

# Free provider tiers cap tokens per minute (e.g. 8,000 on Groq's gpt-oss-120b). On a short
# Retry-After we wait once, inside the request deadline, instead of failing the user's question.
_MAX_RATE_LIMIT_WAIT = 6.0


def _retry_after_seconds(exc: RateLimitError) -> float | None:
    try:
        return float(exc.response.headers.get("retry-after", ""))
    except ValueError:
        return None


@dataclass(frozen=True)
class AgentOutcome:
    text: str
    status: str  # ok | timeout | error
    tools_used: tuple[str, ...] = ()
    tokens_in: int = 0
    tokens_out: int = 0
    elapsed_ms: int = 0


class _Collector(RunHooks[AgentDeps]):
    """Records tool names and keeps a live reference to usage (so timeouts still log tokens)."""

    def __init__(self) -> None:
        self.tools: list[str] = []
        self.ctx: RunContextWrapper[AgentDeps] | None = None

    async def on_llm_end(self, context: RunContextWrapper[AgentDeps], *_: object) -> None:
        self.ctx = context

    async def on_tool_start(
        self, context: RunContextWrapper[AgentDeps], agent: Agent[AgentDeps], tool: Tool
    ) -> None:
        self.ctx = context
        self.tools.append(tool.name)

    def usage(self) -> tuple[int, int]:
        if self.ctx is None:
            return 0, 0
        return self.ctx.usage.input_tokens, self.ctx.usage.output_tokens


def chat_agent(model: AgentModel) -> Agent[AgentDeps]:
    return Agent[AgentDeps](
        name="hcm-assistant",
        instructions=chat_instructions,
        tools=list(ALL_TOOLS),
        model=model,
    )


async def run_agent(
    make_agent: AgentFactory,
    user_input: str,
    deps: AgentDeps,
    endpoint: str,
    *,
    settings: Settings | None = None,
    models: list[AgentModel] | None = None,
    timeout_seconds: float | None = None,
    extra_body: dict[str, Any] | None = None,
) -> AgentOutcome:
    """Run an agent under one hard deadline, falling back across models. Never raises."""
    settings = settings or get_settings()
    models = models if models is not None else build_models(settings)
    collector = _Collector()
    run_config = RunConfig(
        workflow_name=f"hcm-ai/{endpoint}",
        trace_include_sensitive_data=False,
        trace_metadata={"user_id": str(deps.user.user_id), "role": deps.user.role.value},
        model_settings=ModelSettings(
            temperature=0,
            max_tokens=settings.chat_max_tokens,
            extra_body=extra_body,
            reasoning=Reasoning(effort=settings.reasoning_effort)
            if settings.reasoning_effort
            else None,
        ),
    )
    started = time.monotonic()
    text, status = FALLBACK_MESSAGE, "error"
    try:
        async with asyncio.timeout(timeout_seconds or settings.ai_timeout_seconds):
            for index, model in enumerate(models):
                result = None
                for attempt in range(2):
                    try:
                        result = await Runner.run(
                            make_agent(model),
                            user_input,
                            context=deps,
                            max_turns=settings.agent_max_turns,
                            hooks=collector,
                            run_config=run_config,
                        )
                        break
                    except RateLimitError as exc:
                        # Provider per-minute token limit: a short wait usually clears it.
                        wait = _retry_after_seconds(exc)
                        if attempt == 0 and wait is not None and wait <= _MAX_RATE_LIMIT_WAIT:
                            log.warning("model %d rate limited; retrying in %.1fs", index, wait)
                            await asyncio.sleep(wait + 0.25)
                            continue
                        log.warning("model %d failed: RateLimitError", index)
                        break
                    except APIError as exc:
                        log.warning("model %d failed: %s", index, type(exc).__name__)
                        break
                if result is None:
                    continue
                answer = str(result.final_output or "").strip()
                if answer:
                    text, status = answer, "ok"
                break
    except TimeoutError:
        status = "timeout"
    except Exception as exc:
        # Includes MaxTurnsExceeded. Log the type only: messages may echo prompts or keys.
        log.error("agent run failed: %s", type(exc).__name__)

    tokens_in, tokens_out = collector.usage()
    return AgentOutcome(
        text=text,
        status=status,
        tools_used=tuple(collector.tools),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        elapsed_ms=int((time.monotonic() - started) * 1000),
    )


def plain_agent(name: str, instructions: str) -> AgentFactory:
    """Tool-less agent (summaries, structured output)."""

    def make(model: AgentModel) -> Agent[AgentDeps]:
        return Agent[AgentDeps](name=name, instructions=instructions, model=model)

    return make


def merge_outcomes(first: AgentOutcome | None, second: AgentOutcome) -> AgentOutcome:
    """Combine two attempts into one log entry: summed cost, latest status and text."""
    if first is None:
        return second
    return AgentOutcome(
        text=second.text,
        status=second.status,
        tools_used=first.tools_used + second.tools_used,
        tokens_in=first.tokens_in + second.tokens_in,
        tokens_out=first.tokens_out + second.tokens_out,
        elapsed_ms=first.elapsed_ms + second.elapsed_ms,
    )


async def execute_agent_chat(
    deps: AgentDeps,
    message: str,
    *,
    settings: Settings | None = None,
    models: list[AgentModel] | None = None,
) -> AgentOutcome:
    return await run_agent(chat_agent, message, deps, "chat", settings=settings, models=models)
