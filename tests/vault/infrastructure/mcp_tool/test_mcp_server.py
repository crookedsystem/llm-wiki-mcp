import asyncio
from pathlib import Path
from typing import TypedDict, cast

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from common.config import Settings
from common.runtime_registry import create_runtime
from vault.infrastructure.mcp_tool.mcp_server import create_mcp_server


class WriteNoteToolResult(TypedDict):
    source_hash: str
    content_hash: str


class SearchNoteToolResult(TypedDict):
    path: str
    content_hash: str


class SearchToolResult(TypedDict):
    count: int
    results: list[SearchNoteToolResult]


def test_mcp_server는_기본_http_설정을_사용한다(tmp_path: Path) -> None:
    # Given: 기본 Settings로 MCP server를 생성한다.
    app_settings = Settings(host="127.0.0.1", vault_path=tmp_path / "vault")
    runtime = create_runtime(app_settings)
    server = create_mcp_server(app_settings, runtime.write_service, runtime.search_service)

    # When: FastMCP HTTP 설정을 조회한다.
    server_settings = server.settings

    # Then: local-only host, 기본 port, streamable HTTP path가 적용된다.
    assert server_settings.host == "127.0.0.1"
    assert server_settings.port == 9999
    assert server_settings.streamable_http_path == "/mcp"


def test_mcp_server는_write와_search_tool만_노출하고_description을_제공한다(
    tmp_path: Path,
) -> None:
    async def exercise_server() -> None:
        # Given: 임시 vault를 바라보는 MCP server가 있다.
        vault_root = tmp_path / "vault"
        settings = Settings(host="127.0.0.1", vault_path=vault_root)
        runtime = create_runtime(settings)
        server = create_mcp_server(settings, runtime.write_service, runtime.search_service)

        # When: 등록된 tool 목록을 조회하고 write/search tool을 호출한다.
        tools = await server.list_tools()
        _, write_result = await server.call_tool(
            "kb_write_note",
            {
                "note_path": "concepts/agent-memory.md",
                "title": "Agent Memory",
                "type": "concept",
                "tags": ["agent-memory"],
                "sources": ["raw/articles/source.md"],
                "body": "## Summary\nAgent memory keeps durable context.",
                "created": "2026-06-12T09:30:45Z",
                "updated": "2026-06-12T10:31:46Z",
                "confidence": "medium",
                "contested": False,
            },
        )
        structured_write_result = cast(WriteNoteToolResult, write_result)
        _, search_result = await server.call_tool("kb_search_notes", {"query": "agent memory"})
        structured_search_result = cast(SearchToolResult, search_result)

        # Then: MCP는 쓰기/검색 tool만 노출하고 각 tool description은 비어 있지 않다.
        tool_by_name = {tool.name: tool for tool in tools}
        assert set(tool_by_name) == {"kb_write_note", "kb_search_notes"}
        assert "structured fields" in (tool_by_name["kb_write_note"].description or "")
        assert "Search Markdown notes" in (tool_by_name["kb_search_notes"].description or "")
        assert structured_write_result["source_hash"]
        results = structured_search_result["results"]
        assert structured_search_result["count"] == 1
        assert results[0]["path"] == "concepts/agent-memory.md"
        assert results[0]["content_hash"] == structured_write_result["content_hash"]

    asyncio.run(exercise_server())


def test_mcp_server는_write_timestamp의_초단위_datetime을_검증한다(tmp_path: Path) -> None:
    async def exercise_server() -> None:
        # Given: 임시 vault를 바라보는 MCP server가 있다.
        vault_root = tmp_path / "vault"
        settings = Settings(host="127.0.0.1", vault_path=vault_root)
        runtime = create_runtime(settings)
        server = create_mcp_server(settings, runtime.write_service, runtime.search_service)

        # When / Then: date-only timestamp는 write tool validator에서 거부된다.
        with pytest.raises(ToolError, match="include time|ISO datetime"):
            await server.call_tool(
                "kb_write_note",
                {
                    "note_path": "concepts/agent-memory.md",
                    "title": "Agent Memory",
                    "type": "concept",
                    "tags": ["agent-memory"],
                    "sources": ["raw/articles/source.md"],
                    "body": "## Summary\nAgent memory keeps durable context.",
                    "created": "2026-06-12",
                    "updated": "2026-06-12T10:31:46Z",
                },
            )

    asyncio.run(exercise_server())
