from typing_extensions import TypedDict

from vault.service.result.insert_attachment_result import InsertAttachmentResult


class InsertAttachmentResponse(TypedDict):
    note_path: str
    attachment_path: str
    attachment_link: str
    source_hash: str
    content_hash: str


def insert_attachment_response(result: InsertAttachmentResult) -> InsertAttachmentResponse:
    return {
        "note_path": result.note_path.as_posix(),
        "attachment_path": result.attachment_path.as_posix(),
        "attachment_link": result.attachment_link,
        "source_hash": result.source_hash,
        "content_hash": result.content_hash,
    }
