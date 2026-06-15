from datetime import datetime
from pathlib import Path

from common.model import FrozenModel
from vault.service.command.write_note_command import ConfidenceLevel, WikiNoteType


class ReadNoteResult(FrozenModel):
    path: Path
    title: str
    type: WikiNoteType
    tags: tuple[str, ...]
    sources: tuple[str, ...]
    body: str
    created: datetime
    updated: datetime
    confidence: ConfidenceLevel | None = None
    contested: bool | None = None
    content_hash: str
