from common.model import FrozenModel
from vault.service.command.delete_note_command import DeleteNoteCommand


class DeleteNoteRequest(FrozenModel):
    note_path: str
    reference_cleanup_paths: list[str] = []
    dry_run: bool = True
    confirm: str | None = None

    def to_command(self) -> DeleteNoteCommand:
        return DeleteNoteCommand(
            note_path=self.note_path,
            reference_cleanup_paths=tuple(self.reference_cleanup_paths),
            dry_run=self.dry_run,
            confirm=self.confirm,
        )
