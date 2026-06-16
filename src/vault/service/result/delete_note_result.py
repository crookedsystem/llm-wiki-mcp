from common.model import FrozenModel


class RelatedNoteCandidate(FrozenModel):
    path: str
    title: str | None
    content_hash: str
    relationships: list[str]
    evidence: list[str]


class DeleteNoteResult(FrozenModel):
    dry_run: bool
    deleted: bool
    target_path: str
    reference_cleanup_paths: list[str]
    deleted_paths: list[str]
    updated_paths: list[str]
    content_hashes: dict[str, str]
    related_candidates: list[RelatedNoteCandidate]
    confirmation_phrase: str
    safety_notice: str
