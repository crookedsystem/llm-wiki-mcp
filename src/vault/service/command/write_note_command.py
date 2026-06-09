from pathlib import Path

from common.model import FrozenModel


class WriteNoteCommand(FrozenModel):
    note_path: str | Path
    content: str
    if_hash: str | None = None
