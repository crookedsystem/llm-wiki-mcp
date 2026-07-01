from pydantic import Field

from common.model import FrozenModel
from vault.service.command.context_command import ContextMode


class ContextReference(FrozenModel):
    path: str
    title: str | None
    page_type: str | None
    tags: list[str]
    content_hash: str
    relation: str
    followup_search: str


class BrokenWikiLink(FrozenModel):
    source_path: str
    source_content_hash: str
    target: str
    normalized_target: str
    occurrences: int
    suggested_path: str
    followup_search: str


class SuggestedLink(FrozenModel):
    source_path: str
    source_content_hash: str
    target_path: str
    target_title: str | None
    relation: str
    reason: str
    followup_search: str


class PromptCue(FrozenModel):
    path: str
    title: str | None
    content_hash: str
    memory_kind: str = "semantic_fact"
    evidence_status: str = "verified"
    updated: str | None = None
    review_after: str | None = None
    confidence: str | None = None
    scope: str | None = None
    applies_when: str | None = None
    do: str | None = None
    avoid: str | None = None
    check_before_acting: str | None = None
    prevention_cue: str | None = None
    evidence: str | None = None


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
    orientation: list[ContextReference]
    broken_links: list[BrokenWikiLink]
    link_targets: list[ContextReference]
    suggested_links: list[SuggestedLink]
    prompt_cues: list[PromptCue] = Field(default_factory=list)
