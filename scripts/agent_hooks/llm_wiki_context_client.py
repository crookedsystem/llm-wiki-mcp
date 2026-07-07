from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from agent_hooks.llm_wiki_context_payload import is_link_context_payload


async def load_context(
    *,
    server_url: str,
    query: str,
    mode: str,
    limit: int,
    path_prefix: str | None,
    timeout_seconds: float,
) -> dict[str, Any]:
    # `timeout_seconds` is the whole-operation budget, not a per-call one. The
    # kb_context attempt and its kb_search_notes fallback must SHARE it: against an
    # unreachable server each call hangs for the full timeout, so a naive fallback
    # doubles the wall-clock (~2x) and lets the UserPromptSubmit hook overrun Claude
    # Code's outer timeout, which then SIGKILLs it and injects no context at all.
    # A shared deadline plus asyncio.wait_for keeps the total bounded so the hook
    # always fails open with a fallback block inside the budget.
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    try:
        payload = await asyncio.wait_for(
            context_notes(
                server_url=server_url,
                query=query,
                mode=mode,
                limit=limit,
                path_prefix=path_prefix,
                timeout_seconds=timeout_seconds,
            ),
            timeout=timeout_seconds,
        )
        if is_link_context_payload(payload):
            return payload
    except Exception:
        pass
    remaining = deadline - loop.time()
    if remaining <= 0:
        raise TimeoutError("LLM Wiki context budget exhausted before fallback search")
    return await asyncio.wait_for(
        search_notes(
            server_url=server_url,
            query=query,
            limit=limit,
            path_prefix=path_prefix,
            timeout_seconds=remaining,
        ),
        timeout=remaining,
    )


async def context_notes(
    *,
    server_url: str,
    query: str,
    mode: str,
    limit: int,
    path_prefix: str | None,
    timeout_seconds: float,
) -> dict[str, Any]:
    arguments: dict[str, Any] = {
        "query": normalize_query(query),
        "mode": mode,
        "limit": limit,
    }
    if path_prefix:
        arguments["path_prefix"] = path_prefix
    return await call_mcp_tool(
        server_url=server_url,
        tool_name="kb_context",
        arguments=arguments,
        timeout_seconds=timeout_seconds,
    )


async def search_notes(
    *,
    server_url: str,
    query: str,
    limit: int,
    path_prefix: str | None,
    timeout_seconds: float,
) -> dict[str, Any]:
    arguments: dict[str, Any] = {"query": normalize_query(query), "limit": limit}
    if path_prefix:
        arguments["path_prefix"] = path_prefix
    return await call_mcp_tool(
        server_url=server_url,
        tool_name="kb_search_notes",
        arguments=arguments,
        timeout_seconds=timeout_seconds,
    )


async def call_mcp_tool(
    *,
    server_url: str,
    tool_name: str,
    arguments: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    from mcp.client.streamable_http import streamablehttp_client

    from mcp import ClientSession

    timeout = timedelta(seconds=timeout_seconds)
    async with (
        streamablehttp_client(server_url, timeout=timeout, sse_read_timeout=timeout) as (
            read_stream,
            write_stream,
            _get_session_id,
        ),
        ClientSession(read_stream, write_stream, read_timeout_seconds=timeout) as session,
    ):
        await session.initialize()
        result = await session.call_tool(tool_name, arguments, read_timeout_seconds=timeout)
    return call_tool_result_to_dict(result)


def normalize_query(query: str) -> str:
    collapsed = re.sub(r"\s+", " ", query).strip()
    return collapsed[:800]


def call_tool_result_to_dict(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, Mapping):
        return dict(structured)

    content_items = getattr(result, "content", None) or []
    for item in content_items:
        text = getattr(item, "text", None)
        if not isinstance(text, str):
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, Mapping):
            return dict(parsed)
    return {"query": "", "count": 0, "results": []}
