from pathlib import Path

from common.model import FrozenModel


class WriteNoteResult(FrozenModel):
    path: Path
    source_hash: str
    content_hash: str
    commit_hash: str | None = None
