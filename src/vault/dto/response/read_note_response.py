from typing_extensions import TypedDict

from vault.entity.note_time import format_note_time
from vault.service.result.read_note_result import ReadNoteResult


class ReadNoteResponse(TypedDict):
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


def read_note_response(result: ReadNoteResult) -> ReadNoteResponse:
    return {
        "path": result.path.as_posix(),
        "title": result.title,
        "type": result.type,
        "tags": list(result.tags),
        "sources": list(result.sources),
        "body": result.body,
        "created": format_note_time(result.created),
        "updated": format_note_time(result.updated),
        "confidence": result.confidence,
        "contested": result.contested,
        "content_hash": result.content_hash,
    }
