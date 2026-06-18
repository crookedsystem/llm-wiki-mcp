from pathlib import Path

from common.model import FrozenModel


class InsertAttachmentResult(FrozenModel):
    note_path: Path
    attachment_path: Path
    attachment_link: str
    source_hash: str
    content_hash: str
