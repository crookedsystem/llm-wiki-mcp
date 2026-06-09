from common.model import FrozenModel
from vault.service.command.write_note_command import WriteNoteCommand


class WriteNoteRequest(FrozenModel):
    note_path: str
    content: str
    if_hash: str | None = None

    def to_command(self) -> WriteNoteCommand:
        return WriteNoteCommand(
            note_path=self.note_path,
            content=self.content,
            if_hash=self.if_hash,
        )
