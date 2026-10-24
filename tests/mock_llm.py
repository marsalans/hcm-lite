"""Scripted Chat Completions server behind a real AsyncOpenAI client (no network)."""

import asyncio
import json
from collections.abc import Callable
from typing import Any

import httpx
from openai import AsyncOpenAI


def completion(
    content: str | None = None,
    tool_calls: list[tuple[str, dict[str, Any]]] | None = None,
    tokens: tuple[int, int] = (10, 5),
) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = [
            {
                "id": f"call_{i}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
            for i, (name, args) in enumerate(tool_calls)
        ]
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": "mock",
        "choices": [
            {
                "index": 0,
                "finish_reason": "tool_calls" if tool_calls else "stop",
                "message": message,
            }
        ],
        "usage": {
            "prompt_tokens": tokens[0],
            "completion_tokens": tokens[1],
            "total_tokens": sum(tokens),
        },
    }


class MockLLM:
    """Pops one scripted reply per request. A reply is a dict (200), an int (HTTP status), a
    (status, headers) tuple, or a float (sleep that many seconds, then 200 with a plain answer)."""

    def __init__(self, *replies: dict[str, Any] | int | float | tuple[int, dict[str, str]]) -> None:
        self._replies = list(replies)
        self.requests: list[dict[str, Any]] = []

    async def _handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(json.loads(request.content))
        reply = self._replies.pop(0)
        if isinstance(reply, bool):
            raise TypeError
        if isinstance(reply, tuple):
            status, headers = reply
            return httpx.Response(status, headers=headers, json={"error": {"message": "boom"}})
        if isinstance(reply, int):
            return httpx.Response(reply, json={"error": {"message": "boom"}})
        if isinstance(reply, float):
            await asyncio.sleep(reply)
            return httpx.Response(200, json=completion("too late"))
        return httpx.Response(200, json=reply)

    def client(self) -> AsyncOpenAI:
        return AsyncOpenAI(
            api_key="test",
            base_url="http://mock.invalid/v1",
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(self._handler)),
            max_retries=0,
        )


def last_tool_message(llm: MockLLM) -> str:
    for msg in reversed(llm.requests[-1]["messages"]):
        if msg["role"] == "tool":
            return str(msg["content"])
    raise AssertionError("no tool message sent")


Reply = Callable[[], dict[str, Any]]
