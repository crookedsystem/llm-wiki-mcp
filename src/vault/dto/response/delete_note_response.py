from common.model import FrozenModel
from vault.service.result.delete_note_result import DeleteNoteResult, RelatedNoteCandidate


class RelatedNoteCandidateResponse(FrozenModel):
    path: str
    title: str | None
    content_hash: str
    relationships: list[str]
    evidence: list[str]


class DeleteNoteResponse(FrozenModel):
    dry_run: bool
    deleted: bool
    target_path: str
    reference_cleanup_paths: list[str]
    deleted_paths: list[str]
    updated_paths: list[str]
    content_hashes: dict[str, str]
    related_candidates: list[RelatedNoteCandidateResponse]
    confirmation_phrase: str
    safety_notice: str


def delete_note_response(result: DeleteNoteResult) -> DeleteNoteResponse:
    return DeleteNoteResponse(
        dry_run=result.dry_run,
        deleted=result.deleted,
        target_path=result.target_path,
        reference_cleanup_paths=result.reference_cleanup_paths,
        deleted_paths=result.deleted_paths,
        updated_paths=result.updated_paths,
        content_hashes=result.content_hashes,
        related_candidates=[
            _related_note_candidate_response(candidate) for candidate in result.related_candidates
        ],
        confirmation_phrase=result.confirmation_phrase,
        safety_notice=result.safety_notice,
    )


def _related_note_candidate_response(
    candidate: RelatedNoteCandidate,
) -> RelatedNoteCandidateResponse:
    return RelatedNoteCandidateResponse(
        path=candidate.path,
        title=candidate.title,
        content_hash=candidate.content_hash,
        relationships=candidate.relationships,
        evidence=candidate.evidence,
    )
