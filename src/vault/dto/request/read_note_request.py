from common.model import FrozenModel
from vault.service.command.read_note_command import ReadNoteCommand


class ReadNoteRequest(FrozenModel):
    note_path: str

    def to_command(self) -> ReadNoteCommand:
        return ReadNoteCommand(note_path=self.note_path)
