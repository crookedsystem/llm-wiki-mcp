from mcp.server.fastmcp import FastMCP

from vault.dto.request.search_notes_request import SearchNotesRequest
from vault.dto.request.write_note_request import WriteNoteRequest
from vault.dto.response.search_notes_response import (
    SearchNotesResponse,
    search_notes_response,
)
from vault.dto.response.write_note_response import (
    WriteNoteResponse,
    write_note_response,
)
from vault.service.vault_search_service import VaultSearchService
from vault.service.vault_write_service import VaultWriteService


def register_vault_tools(
    server: FastMCP[object],
    write_service: VaultWriteService,
    search_service: VaultSearchService,
) -> None:
    @server.tool(
        description=(
            "Write a complete Markdown note inside the configured vault. "
            "Existing notes require the current content_hash as if_hash so agents do not "
            "overwrite a newer wiki revision by accident."
        )
    )
    async def kb_write_note(
        note_path: str,
        content: str,
        if_hash: str | None = None,
    ) -> WriteNoteResponse:
        request = WriteNoteRequest(note_path=note_path, content=content, if_hash=if_hash)
        result = await write_service.write_note(request.to_command())
        return write_note_response(result)

    @server.tool(
        description=(
            "Search Markdown notes in the configured LLM Wiki vault. Returns ranked note "
            "paths, titles, page types, tags, content_hash values for safe follow-up writes, "
            "and line snippets from matching wiki pages."
        )
    )
    def kb_search_notes(
        query: str,
        limit: int = 10,
        path_prefix: str | None = None,
    ) -> SearchNotesResponse:
        request = SearchNotesRequest(query=query, limit=limit, path_prefix=path_prefix)
        result = search_service.search_notes(request.to_command())
        return search_notes_response(result)
