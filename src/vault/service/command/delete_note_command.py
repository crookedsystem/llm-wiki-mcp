from pathlib import Path

from pydantic import field_validator, model_validator

from common.model import FrozenModel


class DeleteNoteCommand(FrozenModel):
    note_path: str | Path
    reference_cleanup_paths: tuple[str | Path, ...] = ()
    dry_run: bool = True
    confirm: str | None = None

    @field_validator("reference_cleanup_paths", mode="before")
    @classmethod
    def _validate_reference_cleanup_paths(cls, value: object) -> tuple[str | Path, ...]:
        if value is None:
            return ()
        if not isinstance(value, list | tuple):
            raise ValueError("reference_cleanup_paths must be a list of note paths")
        return tuple(value)

    @model_validator(mode="after")
    def _validate_contract(self) -> "DeleteNoteCommand":
        paths = [Path(self.note_path), *(Path(path) for path in self.reference_cleanup_paths)]
        if any(".." in path.parts for path in paths):
            raise ValueError("note paths must not contain parent directory segments")
        normalized = [path.as_posix() for path in paths]
        if len(set(normalized)) != len(normalized):
            raise ValueError("note paths must not contain duplicates")
        return self
