from common.model import FrozenModel
from vault.service.command.context_command import ContextMode
from vault.service.result.search_notes_result import LineMatch


class ContextNote(FrozenModel):
    path: str
    title: str | None
    page_type: str | None
    tags: list[str]
    score: float
    content_hash: str
    matches: list[LineMatch]
    why_included: str


class ContextSection(FrozenModel):
    name: str
    purpose: str
    notes: list[ContextNote]


class EntityGuidance(FrozenModel):
    criteria: list[str]
    preferred_paths: list[str]
    prewrite_checks: list[str]


class ContextResult(FrozenModel):
    query: str
    mode: ContextMode
    count: int
    usage: list[str]
    entity_guidance: EntityGuidance
    sections: list[ContextSection]
