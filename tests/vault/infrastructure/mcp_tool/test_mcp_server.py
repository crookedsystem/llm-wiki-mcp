import asyncio
import base64
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
    attachment_paths: list[str]


class ReadNoteToolResult(TypedDict):
    path: str
    title: str
    type: str
    tags: list[str]
    sources: list[str]
    body: str
    created: str
    updated: str
    confidence: str | None
    contested: bool | None
    content_hash: str


class SearchNoteToolResult(TypedDict):
    path: str
    content_hash: str


class SearchToolResult(TypedDict):
    count: int
    results: list[SearchNoteToolResult]


class ContextToolResult(TypedDict):
    count: int
    broken_links: list[dict[str, object]]
    link_targets: list[dict[str, object]]
    suggested_links: list[dict[str, object]]
    entity_guidance: dict[str, object]
    usage: list[str]


class RelatedCandidateToolResult(TypedDict):
    path: str
    relationships: list[str]
    evidence: list[str]


class DeleteToolResult(TypedDict):
    dry_run: bool
    deleted: bool
    target_path: str
    reference_cleanup_paths: list[str]
    deleted_paths: list[str]
    updated_paths: list[str]
    content_hashes: dict[str, str]
    related_candidates: list[RelatedCandidateToolResult]
    confirmation_phrase: str
    safety_notice: str


def test_mcp_server는_기본_http_설정을_사용한다(tmp_path: Path) -> None:
    # Given: 기본 Settings로 MCP server를 생성한다.
    app_settings = Settings(host="127.0.0.1", vault_path=tmp_path / "vault")
    runtime = create_runtime(app_settings)
    server = create_mcp_server(
        app_settings,
        runtime.read_service,
        runtime.write_service,
        runtime.search_service,
        runtime.context_service,
        runtime.delete_service,
    )

    # When: FastMCP HTTP 설정을 조회한다.
    server_settings = server.settings

    # Then: local-only host, 기본 port, streamable HTTP path가 적용된다.
    assert server_settings.host == "127.0.0.1"
    assert server_settings.port == 9999
    assert server_settings.streamable_http_path == "/mcp"


def test_mcp_server는_write_search_push_tool을_노출하고_description을_제공한다(
    tmp_path: Path,
) -> None:
    async def exercise_server() -> None:
        # Given: 임시 vault를 바라보는 MCP server가 있다.
        vault_root = tmp_path / "vault"
        settings = Settings(host="127.0.0.1", vault_path=vault_root)
        runtime = create_runtime(settings)
        server = create_mcp_server(
            settings,
            runtime.read_service,
            runtime.write_service,
            runtime.search_service,
            runtime.context_service,
            runtime.delete_service,
        )

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
                "body": (
                    "## Summary\nAgent memory keeps durable context.\n\n"
                    "Memory diagram: ![memory.png](raw/assets/memory.png)"
                ),
                "created": "2026-06-12T09:30:45Z",
                "updated": "2026-06-12T10:31:46Z",
                "confidence": "medium",
                "contested": False,
                "attachments": [
                    {
                        "path": "raw/assets/memory.png",
                        "mime_type": "image/png",
                        "data_base64": base64.b64encode(b"image bytes").decode("ascii"),
                    }
                ],
            },
        )
        structured_write_result = cast(WriteNoteToolResult, write_result)
        _, search_result = await server.call_tool("kb_search_notes", {"query": "agent memory"})
        structured_search_result = cast(SearchToolResult, search_result)
        _, read_result = await server.call_tool(
            "kb_read_note",
            {"note_path": "concepts/agent-memory.md"},
        )
        structured_read_result = cast(ReadNoteToolResult, read_result)
        _, context_result = await server.call_tool("kb_context", {"query": "agent memory"})
        structured_context_result = cast(ContextToolResult, context_result)

        # Then: MCP는 쓰기/검색/push tool을 노출하고 각 tool description은 비어 있지 않다.
        tool_by_name = {tool.name: tool for tool in tools}
        assert set(tool_by_name) == {
            "kb_read_note",
            "kb_write_note",
            "kb_delete_note",
            "kb_search_notes",
            "kb_context",
        }
        assert "Read a complete existing Markdown wiki note" in (
            tool_by_name["kb_read_note"].description or ""
        )
        assert "structured fields" in (tool_by_name["kb_write_note"].description or "")
        assert "Actual deletion requires dry_run=false" in (
            tool_by_name["kb_delete_note"].description or ""
        )
        assert "Search Markdown notes" in (tool_by_name["kb_search_notes"].description or "")
        assert "wiki link context map" in (tool_by_name["kb_context"].description or "")
        assert structured_write_result["source_hash"]
        assert structured_write_result["attachment_paths"] == [
            (vault_root / "raw" / "assets" / "memory.png").resolve().as_posix()
        ]
        assert (vault_root / "raw" / "assets" / "memory.png").read_bytes() == b"image bytes"
        assert structured_read_result["path"] == "concepts/agent-memory.md"
        assert structured_read_result["title"] == "Agent Memory"
        assert structured_read_result["type"] == "concept"
        assert structured_read_result["tags"] == ["agent-memory"]
        assert structured_read_result["sources"] == ["raw/articles/source.md"]
        assert structured_read_result["body"] == (
            "## Summary\nAgent memory keeps durable context.\n\n"
            "Memory diagram: ![memory.png](raw/assets/memory.png)"
        )
        assert structured_read_result["created"] == "2026-06-12T09:30:45Z"
        assert structured_read_result["updated"] == "2026-06-12T10:31:46Z"
        assert structured_read_result["confidence"] == "medium"
        assert structured_read_result["contested"] is False
        assert structured_read_result["content_hash"] == structured_write_result["content_hash"]
        results = structured_search_result["results"]
        assert structured_search_result["count"] == 1
        assert results[0]["path"] == "concepts/agent-memory.md"
        assert results[0]["content_hash"] == structured_write_result["content_hash"]
        assert structured_context_result["count"] >= 1
        assert structured_context_result["link_targets"]
        assert "sections" not in structured_context_result
        assert structured_context_result["broken_links"] == []
        assert structured_context_result["suggested_links"] == []
        assert structured_context_result["entity_guidance"]["criteria"]
        assert structured_context_result["usage"]

    asyncio.run(exercise_server())


def test_mcp_delete_tool은_dry_run에서_참조_정리_후보와_confirmation을_반환한다(
    tmp_path: Path,
) -> None:
    async def exercise_server() -> None:
        # Given: target note와 서로 wikilink로 연결된 note들이 있다.
        vault_root = tmp_path / "vault"
        (vault_root / "concepts").mkdir(parents=True)
        (vault_root / "queries").mkdir()
        (vault_root / "concepts" / "agent-memory.md").write_text(
            "---\ntitle: Agent Memory\ntype: concept\ntags: [agent-memory]\n---\n\n"
            "# Agent Memory\n\nSee [[queries/memory-review]].\n",
            encoding="utf-8",
        )
        (vault_root / "queries" / "memory-review.md").write_text(
            "---\ntitle: Memory Review\ntype: query\ntags: [agent-memory]\n---\n\n"
            "# Memory Review\n\nBack to [[concepts/agent-memory]].\n",
            encoding="utf-8",
        )
        settings = Settings(host="127.0.0.1", vault_path=vault_root)
        runtime = create_runtime(settings)
        server = create_mcp_server(
            settings,
            runtime.read_service,
            runtime.write_service,
            runtime.search_service,
            runtime.context_service,
            runtime.delete_service,
        )

        # When: 삭제 tool을 기본 dry_run으로 호출한다.
        _, delete_result = await server.call_tool(
            "kb_delete_note",
            {"note_path": "concepts/agent-memory.md"},
        )
        structured_delete_result = cast(DeleteToolResult, delete_result)

        # Then: 파일은 삭제되지 않고, 관련 후보와 명시 confirmation 문구를 반환한다.
        assert structured_delete_result["dry_run"] is True
        assert structured_delete_result["deleted"] is False
        assert structured_delete_result["target_path"] == "concepts/agent-memory.md"
        assert structured_delete_result["deleted_paths"] == []
        assert structured_delete_result["confirmation_phrase"].startswith(
            "DELETE: concepts/agent-memory.md@"
        )
        assert "ask the user directly" in structured_delete_result["safety_notice"]
        assert (vault_root / "concepts" / "agent-memory.md").exists()
        candidate = structured_delete_result["related_candidates"][0]
        assert candidate["path"] == "queries/memory-review.md"
        assert candidate["relationships"] == ["backlink"]
        assert any("[[concepts/agent-memory]]" in evidence for evidence in candidate["evidence"])

    asyncio.run(exercise_server())


def test_mcp_delete_tool은_confirmation이_정확할_때만_명시된_참조를_정리한다(
    tmp_path: Path,
) -> None:
    async def exercise_server() -> None:
        # Given: target note와 target을 참조하는 note가 있다.
        vault_root = tmp_path / "vault"
        (vault_root / "concepts").mkdir(parents=True)
        (vault_root / "queries").mkdir()
        target_path = vault_root / "concepts" / "agent-memory.md"
        related_path = vault_root / "queries" / "memory-review.md"
        target_path.write_text(
            "# Agent Memory\n\nSee [[queries/memory-review]].\n",
            encoding="utf-8",
        )
        related_path.write_text(
            "# Memory Review\n\nBack to [[concepts/agent-memory|Agent Memory]].\n",
            encoding="utf-8",
        )
        settings = Settings(host="127.0.0.1", vault_path=vault_root)
        runtime = create_runtime(settings)
        server = create_mcp_server(
            settings,
            runtime.read_service,
            runtime.write_service,
            runtime.search_service,
            runtime.context_service,
            runtime.delete_service,
        )

        # When / Then: confirmation 없이 실제 삭제를 요청하면 차단된다.
        with pytest.raises(ToolError, match="confirm must exactly match"):
            await server.call_tool(
                "kb_delete_note",
                {
                    "note_path": "concepts/agent-memory.md",
                    "reference_cleanup_paths": ["queries/memory-review.md"],
                    "dry_run": False,
                },
            )

        # When: dry_run confirmation_phrase를 그대로 사용해 삭제와 참조 정리를 실행한다.
        _, preview_result = await server.call_tool(
            "kb_delete_note",
            {
                "note_path": "concepts/agent-memory.md",
                "reference_cleanup_paths": ["queries/memory-review.md"],
            },
        )
        confirmation_phrase = cast(DeleteToolResult, preview_result)["confirmation_phrase"]
        structured_preview_result = cast(DeleteToolResult, preview_result)
        assert confirmation_phrase == (
            "DELETE: concepts/agent-memory.md@"
            f"{structured_preview_result['content_hashes']['concepts/agent-memory.md']}"
            "; CLEAN REFERENCES: queries/memory-review.md@"
            f"{structured_preview_result['content_hashes']['queries/memory-review.md']}"
        )
        _, delete_result = await server.call_tool(
            "kb_delete_note",
            {
                "note_path": "concepts/agent-memory.md",
                "reference_cleanup_paths": ["queries/memory-review.md"],
                "dry_run": False,
                "confirm": confirmation_phrase,
            },
        )
        structured_delete_result = cast(DeleteToolResult, delete_result)

        # Then: target만 삭제되고 참조 note에서는 target wikilink만 제거된다.
        assert structured_delete_result["deleted"] is True
        assert structured_delete_result["deleted_paths"] == ["concepts/agent-memory.md"]
        assert structured_delete_result["updated_paths"] == ["queries/memory-review.md"]
        assert not target_path.exists()
        assert related_path.exists()
        assert related_path.read_text(encoding="utf-8") == (
            "# Memory Review\n\nBack to Agent Memory.\n"
        )

    asyncio.run(exercise_server())


def test_mcp_delete_tool은_dry_run_이후_내용이_바뀌면_기존_confirmation을_거부한다(
    tmp_path: Path,
) -> None:
    async def exercise_server() -> None:
        # Given: target note와 target을 참조하는 note가 있다.
        vault_root = tmp_path / "vault"
        (vault_root / "concepts").mkdir(parents=True)
        (vault_root / "queries").mkdir()
        target_path = vault_root / "concepts" / "agent-memory.md"
        related_path = vault_root / "queries" / "memory-review.md"
        target_path.write_text("# Agent Memory\n", encoding="utf-8")
        related_path.write_text(
            "# Memory Review\n\nBack to [[concepts/agent-memory]].\n",
            encoding="utf-8",
        )
        settings = Settings(host="127.0.0.1", vault_path=vault_root)
        runtime = create_runtime(settings)
        server = create_mcp_server(
            settings,
            runtime.read_service,
            runtime.write_service,
            runtime.search_service,
            runtime.context_service,
            runtime.delete_service,
        )

        # When: dry_run 이후 참조 정리 대상 note 내용이 바뀐다.
        _, preview_result = await server.call_tool(
            "kb_delete_note",
            {
                "note_path": "concepts/agent-memory.md",
                "reference_cleanup_paths": ["queries/memory-review.md"],
            },
        )
        confirmation_phrase = cast(DeleteToolResult, preview_result)["confirmation_phrase"]
        related_path.write_text(
            "# Memory Review\n\nUpdated [[concepts/agent-memory]].\n",
            encoding="utf-8",
        )

        # Then: 이전 confirmation_phrase는 현재 content_hash와 맞지 않아 거부된다.
        with pytest.raises(ToolError, match="confirm must exactly match"):
            await server.call_tool(
                "kb_delete_note",
                {
                    "note_path": "concepts/agent-memory.md",
                    "reference_cleanup_paths": ["queries/memory-review.md"],
                    "dry_run": False,
                    "confirm": confirmation_phrase,
                },
            )
        assert target_path.exists()
        assert related_path.exists()

    asyncio.run(exercise_server())


def test_mcp_server는_write_timestamp의_초단위_UTC_Z_datetime을_검증한다(
    tmp_path: Path,
) -> None:
    async def exercise_server() -> None:
        # Given: 임시 vault를 바라보는 MCP server가 있다.
        vault_root = tmp_path / "vault"
        settings = Settings(host="127.0.0.1", vault_path=vault_root)
        runtime = create_runtime(settings)
        server = create_mcp_server(
            settings,
            runtime.read_service,
            runtime.write_service,
            runtime.search_service,
            runtime.context_service,
            runtime.delete_service,
        )

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
