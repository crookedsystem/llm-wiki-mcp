from typing_extensions import TypedDict

from vault.dto.response.search_notes_response import LineMatchResponse
from vault.service.result.context_result import (
    ContextNote,
    ContextResult,
    ContextSection,
    EntityGuidance,
)


class ContextNoteResponse(TypedDict):
    path: str
    title: str | None
    page_type: str | None
    tags: list[str]
    score: float
    content_hash: str
    matches: list[LineMatchResponse]
    why_included: str


class ContextSectionResponse(TypedDict):
    name: str
    purpose: str
    notes: list[ContextNoteResponse]


class EntityGuidanceResponse(TypedDict):
    criteria: list[str]
    preferred_paths: list[str]
    prewrite_checks: list[str]


class ContextResponse(TypedDict):
    query: str
    mode: str
    count: int
    usage: list[str]
    entity_guidance: EntityGuidanceResponse
    sections: list[ContextSectionResponse]


class ContextResponseMapper:
    @staticmethod
    def to_response(result: ContextResult) -> ContextResponse:
        return {
            "query": result.query,
            "mode": result.mode,
            "count": result.count,
            "usage": result.usage,
            "entity_guidance": ContextResponseMapper._entity_guidance_response(
                result.entity_guidance
            ),
            "sections": [
                ContextResponseMapper._context_section_response(section)
                for section in result.sections
            ],
        }

    @staticmethod
    def _context_section_response(section: ContextSection) -> ContextSectionResponse:
        return {
            "name": section.name,
            "purpose": section.purpose,
            "notes": [ContextResponseMapper._context_note_response(note) for note in section.notes],
        }

    @staticmethod
    def _context_note_response(note: ContextNote) -> ContextNoteResponse:
        return {
            "path": note.path,
            "title": note.title,
            "page_type": note.page_type,
            "tags": note.tags,
            "score": note.score,
            "content_hash": note.content_hash,
            "matches": [{"line": match.line, "snippet": match.snippet} for match in note.matches],
            "why_included": note.why_included,
        }

    @staticmethod
    def _entity_guidance_response(guidance: EntityGuidance) -> EntityGuidanceResponse:
        return {
            "criteria": guidance.criteria,
            "preferred_paths": guidance.preferred_paths,
            "prewrite_checks": guidance.prewrite_checks,
        }
