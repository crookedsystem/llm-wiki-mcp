from pathlib import Path

from pydantic import Field, field_validator, model_validator

from common.model import FrozenModel
from vault.entity.vault_path import DEFAULT_DENIED_NAMES


class InsertAttachmentCommand(FrozenModel):
    note_path: str | Path
    filename: str = Field(min_length=1)
    mime_type: str = Field(min_length=1)
    content: bytes = Field(min_length=1)
    if_hash: str = Field(min_length=1)
    alt_text: str | None = None

    @field_validator("filename")
    @classmethod
    def _validate_filename(cls, value: str) -> str:
        normalized = value.strip()
        if _has_line_separator(normalized):
            raise ValueError("filename must be a single line")
        if not normalized:
            raise ValueError("filename must not be empty")
        path = Path(normalized)
        if path.is_absolute() or path.name != normalized or _contains_parent_segment(path):
            raise ValueError("filename must be a single safe file name")
        if path.suffix == ".md":
            raise ValueError("filename must not be a markdown note")
        denied_part = next((part for part in path.parts if part in DEFAULT_DENIED_NAMES), None)
        if denied_part is not None:
            raise ValueError(f"filename uses denied vault directory: {denied_part}")
        return normalized

    @field_validator("mime_type")
    @classmethod
    def _validate_mime_type(cls, value: str) -> str:
        if _has_line_separator(value):
            raise ValueError("mime_type must be a single line")
        normalized = value.strip().lower()
        if not normalized.startswith("image/"):
            raise ValueError("mime_type must be an image MIME type")
        return normalized

    @field_validator("alt_text")
    @classmethod
    def _validate_alt_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if _has_line_separator(value):
            raise ValueError("alt_text must be a single line")
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def _validate_note_path(self) -> "InsertAttachmentCommand":
        note_path = Path(self.note_path)
        if note_path.suffix != ".md":
            raise ValueError("note_path must be a markdown note path")
        if note_path.is_absolute() or _contains_parent_segment(note_path):
            raise ValueError("note_path must be relative to the vault")
        return self


def _contains_parent_segment(path: Path) -> bool:
    return ".." in path.parts


def _has_line_separator(value: str) -> bool:
    return value.splitlines() != [value]
