from mcp.server.fastmcp import FastMCP

from vault.dto.request.context_request import ContextRequest
from vault.dto.request.delete_note_request import DeleteNoteRequest
from vault.dto.request.read_note_request import ReadNoteRequest
from vault.dto.request.search_notes_request import SearchNotesRequest
from vault.dto.request.write_note_request import WriteNoteRequest
from vault.dto.response.context_response import ContextResponse, ContextResponseMapper
from vault.dto.response.delete_note_response import DeleteNoteResponse, delete_note_response
from vault.dto.response.git_push_response import GitPushResponse, git_push_response
from vault.dto.response.read_note_response import ReadNoteResponse, read_note_response
from vault.dto.response.search_notes_response import (
    SearchNotesResponse,
    search_notes_response,
)
from vault.dto.response.write_note_response import (
    WriteNoteResponse,
    write_note_response,
)
from vault.service.command.context_command import ContextMode
from vault.service.command.write_note_command import ConfidenceLevel, WikiNoteType
from vault.service.note_timestamp import NoteTimestamp
from vault.service.vault_context_service import VaultContextService
from vault.service.vault_delete_service import VaultDeleteService
from vault.service.vault_git_push_service import VaultGitPushService
from vault.service.vault_read_service import VaultReadService
from vault.service.vault_search_service import VaultSearchService
from vault.service.vault_write_service import VaultWriteService


def register_vault_tools(
    server: FastMCP[object],
    read_service: VaultReadService,
    write_service: VaultWriteService,
    search_service: VaultSearchService,
    context_service: VaultContextService,
    git_push_service: VaultGitPushService,
    delete_service: VaultDeleteService,
) -> None:
    @server.tool(
        description=(
            "Read a complete existing Markdown wiki note as structured fields for safe "
            "full-replacement updates. Returns frontmatter fields, body without YAML/title/"
            "provenance, and the current content_hash to pass as if_hash to kb_write_note."
        )
    )
    def kb_read_note(note_path: str) -> ReadNoteResponse:
        request = ReadNoteRequest(note_path=note_path)
        result = read_service.read_note(request.to_command())
        return read_note_response(result)

    @server.tool(
        description=(
            "Write a Markdown wiki note from structured fields. The tool renders YAML "
            "frontmatter, title heading, body, and provenance inside the configured vault. "
            "created and updated must be UTC ISO datetimes with seconds and trailing Z "
            "(YYYY-MM-DDTHH:MM:SSZ). "
            "Existing notes require the current content_hash as if_hash."
        )
    )
    async def kb_write_note(
        note_path: str,
        title: str,
        type: WikiNoteType,
        tags: list[str],
        sources: list[str],
        body: str,
        created: NoteTimestamp,
        updated: NoteTimestamp,
        confidence: ConfidenceLevel | None = None,
        contested: bool | None = None,
        if_hash: str | None = None,
    ) -> WriteNoteResponse:
        request = WriteNoteRequest(
            note_path=note_path,
            title=title,
            type=type,
            tags=tags,
            sources=sources,
            body=body,
            created=created,
            updated=updated,
            confidence=confidence,
            contested=contested,
            if_hash=if_hash,
        )
        result = await write_service.write_note(request.to_command())
        return write_note_response(result)

    @server.tool(
        description=(
            "Preview or delete a Markdown wiki note and clean explicitly listed backlinks. "
            "Default dry_run returns the target, directly linked reference-cleanup candidates, "
            "evidence, and an exact confirmation_phrase. Actual deletion requires dry_run=false "
            "and confirm equal to that phrase. Referencing pages are never deleted by this tool: "
            "when passed in reference_cleanup_paths, only wikilinks pointing at note_path are "
            "removed from those pages."
        )
    )
    async def kb_delete_note(
        note_path: str,
        reference_cleanup_paths: list[str] | None = None,
        dry_run: bool = True,
        confirm: str | None = None,
    ) -> DeleteNoteResponse:
        request = DeleteNoteRequest(
            note_path=note_path,
            reference_cleanup_paths=reference_cleanup_paths or [],
            dry_run=dry_run,
            confirm=confirm,
        )
        result = await delete_service.delete_note(request.to_command())
        return delete_note_response(result)

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

    @server.tool(
        description=(
            "Build a wiki link context map for prompt, prewrite, or stop-hook use. "
            "Returns orientation pages, broken wiki links, existing link targets, suggested "
            "links, usage guidance, and followup_search queries for kb_search_notes evidence."
        )
    )
    def kb_context(
        query: str,
        mode: ContextMode = "prompt",
        limit: int = 16,
        path_prefix: str | None = None,
    ) -> ContextResponse:
        request = ContextRequest(
            query=query,
            mode=mode,
            limit=limit,
            path_prefix=path_prefix,
        )
        result = context_service.context(request.to_command())
        return ContextResponseMapper.to_response(result)

    @server.tool(
        description=(
            "Commit all pending vault changes with a UTC "
            "'YYYY-MM-DD HH:MM - vault sync' message and push origin to the current branch. "
            "The server checks GitHub CLI auth first, then falls back to git push."
        )
    )
    async def kb_push_vault() -> GitPushResponse:
        result = await git_push_service.push_vault()
        return git_push_response(result)
