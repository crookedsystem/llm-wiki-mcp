from datetime import datetime
from pathlib import Path
from typing import cast

from pydantic import TypeAdapter, ValidationError

from common.model import FrozenModel
from vault.entity.vault_note import PROVENANCE_PREFIX, compute_sha256, parse_note
from vault.entity.vault_path import VaultPaths
from vault.service.command.read_note_command import ReadNoteCommand
from vault.service.command.write_note_command import ConfidenceLevel, WikiNoteType
from vault.service.note_timestamp import NoteTimestamp
from vault.service.result.read_note_result import ReadNoteResult


class VaultReadService(FrozenModel):
    paths: VaultPaths

    def read_note(self, command: ReadNoteCommand) -> ReadNoteResult:
        resolved_path = self.paths.resolve_note_path(command.note_path)
        if not resolved_path.exists():
            raise FileNotFoundError(f"note not found: {Path(command.note_path).as_posix()}")

        raw_content = resolved_path.read_text(encoding="utf-8")
        parsed = parse_note(raw_content)
        if parsed.frontmatter is None:
            raise ValueError("note must include YAML frontmatter for structured read")

        fields = _parse_frontmatter(parsed.frontmatter)
        title = _required_scalar(fields, "title")
        body = _strip_rendered_title_and_provenance(parsed.body, title)
        return ReadNoteResult(
            path=resolved_path.relative_to(self.paths.root.resolve()),
            title=title,
            type=_required_type(fields),
            tags=_string_tuple(fields, "tags"),
            sources=_string_tuple(fields, "sources"),
            body=body,
            created=_required_timestamp(fields, "created"),
            updated=_required_timestamp(fields, "updated"),
            confidence=_optional_confidence(fields),
            contested=_optional_bool(fields, "contested"),
            content_hash=compute_sha256(raw_content),
        )


FrontmatterFields = dict[str, str | bool | tuple[str, ...]]


def _parse_frontmatter(frontmatter: str) -> FrontmatterFields:
    fields: FrontmatterFields = {}
    lines = frontmatter.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        key, separator, raw_value = line.partition(":")
        if not separator:
            index += 1
            continue

        key_name = key.strip()
        stripped_value = raw_value.strip()
        if stripped_value:
            fields[key_name] = _parse_scalar_or_inline_list(stripped_value)
            index += 1
            continue

        items: list[str] = []
        index += 1
        while index < len(lines):
            item_line = lines[index].strip()
            if not item_line.startswith("-"):
                break
            items.append(_normalize_scalar(item_line[1:].strip()))
            index += 1
        fields[key_name] = tuple(item for item in items if item)
    return fields


def _parse_scalar_or_inline_list(value: str) -> str | bool | tuple[str, ...]:
    if value == "[]":
        return ()
    if value.startswith("[") and value.endswith("]"):
        return tuple(
            _normalize_scalar(part.strip()) for part in value[1:-1].split(",") if part.strip()
        )
    normalized = _normalize_scalar(value)
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return normalized


def _normalize_scalar(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value.replace('\\"', '"').replace("\\\\", "\\")


def _required_scalar(fields: FrontmatterFields, key: str) -> str:
    value = fields.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"frontmatter field {key!r} is required")
    return value


def _required_type(fields: FrontmatterFields) -> WikiNoteType:
    value = _required_scalar(fields, "type")
    if value not in {
        "raw",
        "entity",
        "concept",
        "comparison",
        "query",
        "summary",
        "schema",
        "index",
        "log",
    }:
        raise ValueError(f"unsupported note type: {value}")
    return cast(WikiNoteType, value)


def _string_tuple(fields: FrontmatterFields, key: str) -> tuple[str, ...]:
    value = fields.get(key)
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    raise ValueError(f"frontmatter field {key!r} must be a list")


def _required_timestamp(fields: FrontmatterFields, key: str) -> datetime:
    value = _required_scalar(fields, key)
    try:
        return TypeAdapter(NoteTimestamp).validate_python(value)
    except ValidationError as error:
        raise ValueError(f"frontmatter field {key!r} must be a UTC Z timestamp") from error


def _optional_confidence(fields: FrontmatterFields) -> ConfidenceLevel | None:
    value = fields.get("confidence")
    if value is None:
        return None
    if value not in {"high", "medium", "low"}:
        raise ValueError(f"unsupported confidence: {value}")
    return cast(ConfidenceLevel, value)


def _optional_bool(fields: FrontmatterFields, key: str) -> bool | None:
    value = fields.get(key)
    if value is None or isinstance(value, bool):
        return value
    raise ValueError(f"frontmatter field {key!r} must be a boolean")


def _strip_rendered_title_and_provenance(body: str, title: str) -> str:
    without_provenance = _strip_provenance_trailer(body)
    lines = without_provenance.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines and lines[0] == f"# {title}":
        lines.pop(0)
        if lines and not lines[0].strip():
            lines.pop(0)
    return "\n".join(lines).strip("\n")


def _strip_provenance_trailer(body: str) -> str:
    lines = body.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and lines[-1].startswith(PROVENANCE_PREFIX):
        lines.pop()
    return "\n".join(lines)
