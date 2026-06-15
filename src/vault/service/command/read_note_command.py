from pathlib import Path

from pydantic import model_validator

from common.model import FrozenModel


class ReadNoteCommand(FrozenModel):
    note_path: str | Path

    @model_validator(mode="after")
    def _validate_contract(self) -> "ReadNoteCommand":
        note_path = Path(self.note_path)
        if ".." in note_path.parts:
            raise ValueError("note_path must not contain parent directory segments")
        return self
