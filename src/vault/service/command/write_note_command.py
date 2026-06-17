import base64
import binascii
from pathlib import Path
from typing import Literal, TypeAlias

from pydantic import Field, field_validator, model_validator

from common.model import FrozenModel
from vault.entity.vault_note import FRONTMATTER_DELIMITER, PROVENANCE_PREFIX
from vault.entity.vault_path import DEFAULT_DENIED_NAMES
from vault.service.note_timestamp import NoteTimestamp

WikiNoteType: TypeAlias = Literal[
    "raw",
    "entity",
    "concept",
    "comparison",
    "query",
    "summary",
    "schema",
    "index",
    "log",
]
ConfidenceLevel: TypeAlias = Literal["high", "medium", "low"]

_ROOT_TYPES: dict[str, frozenset[WikiNoteType]] = {
    "raw": frozenset({"raw"}),
    "entities": frozenset({"entity"}),
    "concepts": frozenset({"concept", "summary"}),
    "comparisons": frozenset({"comparison"}),
    "queries": frozenset({"query", "summary"}),
}
_ROOT_FILE_TYPES: dict[str, frozenset[WikiNoteType]] = {
    "SCHEMA.md": frozenset({"schema"}),
    "index.md": frozenset({"index"}),
    "log.md": frozenset({"log"}),
}


class WriteNoteAttachment(FrozenModel):
    path: str = Field(
        description="Vault-relative file path to create, for example raw/assets/chart.png"
    )
    mime_type: str = Field(description="MIME type for link rendering, for example image/png")
    data_base64: str = Field(
        description="Base64-encoded file bytes from an image or upload payload"
    )

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        if _has_line_separator(value):
            raise ValueError("attachment path must be a single line")
        normalized = value.strip()
        if not normalized:
            raise ValueError("attachment path must not be empty")
        path = Path(normalized)
        if path.is_absolute():
            raise ValueError("attachment path must be relative to the vault")
        if path.suffix == ".md":
            raise ValueError("attachment path must not be a markdown note")
        if _contains_parent_segment(path):
            raise ValueError("attachment path must not contain parent directory segments")
        denied_part = next((part for part in path.parts if part in DEFAULT_DENIED_NAMES), None)
        if denied_part is not None:
            raise ValueError(f"attachment path uses denied vault directory: {denied_part}")
        return path.as_posix()

    @field_validator("mime_type")
    @classmethod
    def _validate_mime_type(cls, value: str) -> str:
        if _has_line_separator(value):
            raise ValueError("attachment mime_type must be a single line")
        normalized = value.strip().lower()
        if "/" not in normalized or normalized.startswith("/") or normalized.endswith("/"):
            raise ValueError("attachment mime_type must be a valid MIME type")
        return normalized

    @field_validator("data_base64")
    @classmethod
    def _validate_data_base64(cls, value: str) -> str:
        normalized = "".join(value.split())
        if not normalized:
            raise ValueError("attachment data_base64 must not be empty")
        try:
            base64.b64decode(normalized, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError("attachment data_base64 must be valid base64") from error
        return normalized

    def decoded_bytes(self) -> bytes:
        return base64.b64decode(self.data_base64, validate=True)


class WriteNoteCommand(FrozenModel):
    note_path: str | Path
    title: str = Field(min_length=1)
    type: WikiNoteType
    tags: tuple[str, ...]
    sources: tuple[str, ...]
    body: str = Field(min_length=1)
    created: NoteTimestamp
    updated: NoteTimestamp
    confidence: ConfidenceLevel | None = None
    contested: bool | None = None
    if_hash: str | None = None
    attachments: tuple[WriteNoteAttachment, ...] = ()

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        if _has_line_separator(value):
            raise ValueError("title must be a single line")
        normalized = value.strip()
        if not normalized:
            raise ValueError("title must not be empty")
        return normalized

    @field_validator("tags", "sources", mode="before")
    @classmethod
    def _validate_string_list(cls, value: object) -> tuple[str, ...]:
        if not isinstance(value, list | tuple):
            raise ValueError("value must be a list of strings")
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError("value must be a list of strings")
            if _has_line_separator(item):
                raise ValueError("list values must be single-line strings")
            stripped = item.strip()
            if not stripped:
                raise ValueError("list values must not be empty")
            normalized.append(stripped)
        return tuple(normalized)

    @field_validator("body")
    @classmethod
    def _validate_body(cls, value: str) -> str:
        normalized = value.strip("\n")
        if not normalized.strip():
            raise ValueError("body must not be empty")
        if normalized.lstrip().startswith(f"{FRONTMATTER_DELIMITER}\n"):
            raise ValueError("body must not include YAML frontmatter")
        if PROVENANCE_PREFIX in normalized:
            raise ValueError("body must not include a provenance trailer")
        if _contains_top_level_heading(normalized):
            raise ValueError("body must not include a top-level heading; title is rendered by tool")
        return normalized

    @field_validator("attachments", mode="before")
    @classmethod
    def _validate_attachments(cls, value: object) -> tuple[WriteNoteAttachment, ...]:
        if value is None:
            return ()
        if not isinstance(value, list | tuple):
            raise ValueError("attachments must be a list")
        return tuple(
            item
            if isinstance(item, WriteNoteAttachment)
            else WriteNoteAttachment.model_validate(item)
            for item in value
        )

    @model_validator(mode="after")
    def _validate_contract(self) -> "WriteNoteCommand":
        note_path = Path(self.note_path)
        if _contains_parent_segment(note_path):
            raise ValueError("note_path must not contain parent directory segments")
        allowed_types = _allowed_types_for_path(note_path)
        if allowed_types is None:
            raise ValueError(
                "note_path must be SCHEMA.md, index.md, log.md, or live under "
                "raw/, entities/, concepts/, comparisons/, or queries/"
            )
        if self.type not in allowed_types:
            allowed = ", ".join(sorted(allowed_types))
            raise ValueError(f"type {self.type!r} is not allowed for note_path; expected {allowed}")
        if self.updated < self.created:
            raise ValueError("updated must be greater than or equal to created")
        attachment_paths = [attachment.path for attachment in self.attachments]
        if len(set(attachment_paths)) != len(attachment_paths):
            raise ValueError("attachment paths must be unique")
        unreferenced_paths = [
            attachment.path
            for attachment in self.attachments
            if not _body_references_attachment(self.body, attachment.path)
        ]
        if unreferenced_paths:
            raise ValueError(
                "attachment paths must be referenced in body: " + ", ".join(unreferenced_paths)
            )
        return self


def _allowed_types_for_path(note_path: Path) -> frozenset[WikiNoteType] | None:
    if note_path.name in _ROOT_FILE_TYPES and len(note_path.parts) == 1:
        return _ROOT_FILE_TYPES[note_path.name]
    if not note_path.parts:
        return None
    return _ROOT_TYPES.get(note_path.parts[0])


def _contains_parent_segment(note_path: Path) -> bool:
    return ".." in note_path.parts


def _body_references_attachment(body: str, attachment_path: str) -> bool:
    return f"({attachment_path})" in body or f"[[{attachment_path}]]" in body


def _has_line_separator(value: str) -> bool:
    return value.splitlines() != [value]


def _contains_top_level_heading(markdown: str) -> bool:
    in_fence = False
    fence_marker = ""
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            marker = stripped[:3]
            if in_fence and marker == fence_marker:
                in_fence = False
                fence_marker = ""
            elif not in_fence:
                in_fence = True
                fence_marker = marker
            continue
        if not in_fence and line.startswith("# "):
            return True
    return False
