import asyncio
from datetime import UTC, datetime
from pathlib import Path

from starlette.testclient import TestClient

from common.config import Settings
from vault.infrastructure.api.fastapi_app import create_fastapi_app
from vault.service.command.write_note_command import WriteNoteCommand


def test_fastapi_app은_health_endpoint와_mcp_mount를_함께_노출한다(tmp_path: Path) -> None:
    # Given: 임시 vault 설정으로 FastAPI app을 생성한다.
    app = create_fastapi_app(Settings(vault_path=tmp_path / "vault"))

    # When: health endpoint와 mounted MCP endpoint를 호출한다.
    with TestClient(app, base_url="http://127.0.0.1:9999") as client:
        health_response = client.get("/health")
        mcp_response = client.get("/mcp")

    # Then: health는 정상이고 MCP mount는 protocol-level Accept 오류까지 도달한다.
    assert health_response.status_code == 200
    assert health_response.json() == {
        "status": "ok",
        "mcp_path": "/mcp",
    }
    assert mcp_response.status_code == 406
    assert "Client must accept text/event-stream" in mcp_response.text


def test_fastapi_app은_metrics_endpoint에서_vault와_graph_지표를_통합한다(
    tmp_path: Path,
) -> None:
    # Given: 두 note와 하나의 broken wikilink가 있는 vault app이 있다.
    vault_root = tmp_path / "vault"
    (vault_root / "daily").mkdir(parents=True)
    (vault_root / "daily" / "a.md").write_text("[[b]] [[missing]]\n", encoding="utf-8")
    (vault_root / "daily" / "b.md").write_text("# B\n", encoding="utf-8")
    app = create_fastapi_app(Settings(vault_path=vault_root))

    # When: REST metrics endpoint와 OpenAPI schema를 호출한다.
    with TestClient(app, base_url="http://127.0.0.1:9999") as client:
        metrics_response = client.get("/metrics")
        openapi_response = client.get("/openapi.json")

    # Then: graph health와 vault metrics가 단일 API endpoint에 통합되어 Swagger에 노출된다.
    assert metrics_response.status_code == 200
    assert metrics_response.json() == {
        "vault_notes_total": 2,
        "vault_bytes_total": 22,
        "graph_links_total": 2,
        "graph_broken_links_total": 1,
        "graph_orphans_total": 1,
    }
    openapi_schema = openapi_response.json()
    metrics_schema = openapi_schema["paths"]["/metrics"]["get"]
    assert metrics_schema["summary"] == "Vault metrics 조회"
    assert "wiki graph 지표" in metrics_schema["description"]
    metric_fields = openapi_schema["components"]["schemas"]["MetricsResponse"]["properties"]
    assert (
        metric_fields["vault_notes_total"]["description"]
        == "Vault에서 검색 가능한 Markdown note 수"
    )


def test_fastapi_app은_tools_endpoint에서_mcp_tool_schema를_문서화한다(
    tmp_path: Path,
) -> None:
    # Given: MCP tool이 등록된 FastAPI app이 있다.
    app = create_fastapi_app(Settings(vault_path=tmp_path / "vault"))

    # When: tool 문서 endpoint를 호출한다.
    with TestClient(app, base_url="http://127.0.0.1:9999") as client:
        response = client.get("/tools")

    # Then: read/write/search MCP tool 목록과 명확한 설명이 REST 문서용 JSON으로 반환된다.
    assert response.status_code == 200
    tools = response.json()
    read_note = next(tool for tool in tools if tool["name"] == "kb_read_note")
    write_note = next(tool for tool in tools if tool["name"] == "kb_write_note")
    delete_note = next(tool for tool in tools if tool["name"] == "kb_delete_note")
    search_notes = next(tool for tool in tools if tool["name"] == "kb_search_notes")
    context = next(tool for tool in tools if tool["name"] == "kb_context")
    assert "Read a complete existing Markdown wiki note" in read_note["description"]
    assert "structured fields" in write_note["description"]
    assert "REST attachment endpoint" in write_note["description"]
    assert "Actual deletion requires dry_run=false" in delete_note["description"]
    assert "Search Markdown notes" in search_notes["description"]
    assert "wiki link context map" in context["description"]
    assert read_note["inputSchema"]["required"] == ["note_path"]
    assert read_note["inputSchema"]["properties"]["note_path"]["type"] == "string"
    assert read_note["outputSchema"]["type"] == "object"
    assert write_note["inputSchema"]["type"] == "object"
    assert set(write_note["inputSchema"]["required"]) == {
        "note_path",
        "title",
        "type",
        "tags",
        "sources",
        "body",
        "created",
        "updated",
    }
    assert write_note["inputSchema"]["properties"]["note_path"]["type"] == "string"
    assert write_note["inputSchema"]["properties"]["title"]["type"] == "string"
    assert write_note["inputSchema"]["properties"]["type"]["enum"] == [
        "raw",
        "entity",
        "concept",
        "comparison",
        "query",
        "summary",
        "schema",
        "index",
        "log",
    ]
    assert write_note["inputSchema"]["properties"]["tags"]["type"] == "array"
    assert write_note["inputSchema"]["properties"]["sources"]["type"] == "array"
    assert write_note["inputSchema"]["properties"]["body"]["type"] == "string"
    assert write_note["inputSchema"]["properties"]["created"]["format"] == "date-time"
    assert write_note["inputSchema"]["properties"]["updated"]["format"] == "date-time"
    assert "attachments" not in write_note["inputSchema"]["properties"]
    assert (
        write_note["inputSchema"]["properties"]["created"]["pattern"]
        == r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
    )
    assert (
        write_note["inputSchema"]["properties"]["updated"]["pattern"]
        == r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
    )
    assert "content" not in write_note["inputSchema"]["properties"]
    assert write_note["outputSchema"]["type"] == "object"
    assert delete_note["inputSchema"]["required"] == ["note_path"]
    assert delete_note["inputSchema"]["properties"]["dry_run"]["default"] is True
    assert delete_note["outputSchema"]["type"] == "object"
    assert search_notes["inputSchema"]["required"] == ["query"]
    assert search_notes["inputSchema"]["properties"]["query"]["type"] == "string"
    assert context["inputSchema"]["required"] == ["query"]
    assert context["inputSchema"]["properties"]["query"]["type"] == "string"
    assert context["inputSchema"]["properties"]["mode"]["default"] == "prompt"
    assert context["outputSchema"]["type"] == "object"
    assert {tool["name"] for tool in tools} == {
        "kb_read_note",
        "kb_write_note",
        "kb_delete_note",
        "kb_search_notes",
        "kb_context",
    }


def test_fastapi_app은_note_attachment_partial_insert_endpoint를_노출한다(
    tmp_path: Path,
) -> None:
    # Given: 먼저 생성된 note와 현재 content_hash가 있다.
    vault_root = tmp_path / "vault"
    app = create_fastapi_app(Settings(vault_path=vault_root))
    write_result = asyncio.run(
        app.state.runtime.write_service.write_note(
            WriteNoteCommand(
                note_path="concepts/today.md",
                title="Today",
                type="concept",
                tags=("agent-memory",),
                sources=("raw/articles/source.md",),
                body="## Summary\nBody text",
                created=datetime(2026, 6, 12, 9, 30, 45, tzinfo=UTC),
                updated=datetime(2026, 6, 12, 10, 31, 46, tzinfo=UTC),
            )
        )
    )

    # When: REST endpoint로 이미지 bytes를 업로드한다.
    with TestClient(app, base_url="http://127.0.0.1:9999") as client:
        response = client.post(
            "/notes/concepts/today.md/attachments",
            params={
                "filename": "chart.png",
                "if_hash": write_result.content_hash,
                "alt_text": "chart",
            },
            content=b"image bytes",
            headers={"content-type": "image/png"},
        )

    # Then: assets 경로에 파일이 저장되고 note에 link가 부분 삽입된다.
    assert response.status_code == 200
    payload = response.json()
    attachment_path = vault_root / "raw" / "assets" / "concepts" / "today" / "chart.png"
    note_content = (vault_root / "concepts" / "today.md").read_text(encoding="utf-8")
    assert attachment_path.read_bytes() == b"image bytes"
    assert payload["attachment_link"] == "![chart](raw/assets/concepts/today/chart.png)"
    assert "## Attachments\n![chart](raw/assets/concepts/today/chart.png)" in note_content
    assert "operation=insert_attachment" in note_content


def test_fastapi_app은_없는_route를_공통_error_envelope로_응답한다(tmp_path: Path) -> None:
    # Given: 공통 error handler가 붙은 FastAPI app이 있다.
    app = create_fastapi_app(Settings(vault_path=tmp_path / "vault"))

    # When: 존재하지 않는 route를 호출한다.
    with TestClient(app, base_url="http://127.0.0.1:9999") as client:
        response = client.get("/missing")

    # Then: 404도 {code,message,timestamp} envelope로 반환된다.
    assert response.status_code == 404
    assert response.json().keys() == {"code", "message", "timestamp"}
    assert response.json()["code"] == "NOT_FOUND"
    assert response.json()["message"] == "Not Found"
    assert datetime.fromisoformat(response.json()["timestamp"]).tzinfo is not None


def test_fastapi_app은_예상하지_못한_예외를_공통_error_envelope로_숨긴다(
    tmp_path: Path,
) -> None:
    # Given: 내부 예외 메시지를 발생시키는 route가 app에 등록되어 있다.
    app = create_fastapi_app(Settings(vault_path=tmp_path / "vault"))

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret internals")

    # When: route가 처리되지 않은 예외를 발생시킨다.
    with TestClient(
        app,
        base_url="http://127.0.0.1:9999",
        raise_server_exceptions=False,
    ) as client:
        response = client.get("/boom")

    # Then: 응답은 500 envelope이고 내부 예외 메시지는 노출되지 않는다.
    assert response.status_code == 500
    assert response.json().keys() == {"code", "message", "timestamp"}
    assert response.json()["code"] == "INTERNAL_SERVER_ERROR"
    assert response.json()["message"] == "Internal Server Error"
    assert "secret internals" not in response.text
    assert datetime.fromisoformat(response.json()["timestamp"]).tzinfo is not None
