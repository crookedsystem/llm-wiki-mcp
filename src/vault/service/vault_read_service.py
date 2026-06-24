from datetime import datetime
from pathlib import Path
from typing import cast

from common.model import FrozenModel
from vault.component.write_queue import VaultWriteQueue
from vault.entity.note_timestamp import (
    coerce_legacy_note_timestamp_to_utc,
    coerce_note_timestamp_to_utc,
    format_note_timestamp,
    is_note_timestamp_utc_z,
)
from vault.entity.vault_note import (
    FRONTMATTER_DELIMITER,
    PROVENANCE_PREFIX,
    ParsedNote,
    append_provenance_trailer,
    compute_sha256,
    parse_note,
    strip_provenance_trailer,
)
from vault.entity.vault_path import VaultPaths
from vault.service.command.read_note_command import ReadNoteCommand
from vault.service.command.write_note_command import ConfidenceLevel, WikiNoteType
from vault.service.result.read_note_result import ReadNoteResult

FrontmatterFields = dict[str, str | bool | tuple[str, ...]]


class VaultReadService(FrozenModel):
    paths: VaultPaths
    queue: VaultWriteQueue | None = None
    actor: str = "llm-wiki"

    async def read_note_queued(self, command: ReadNoteCommand) -> ReadNoteResult:
        if self.queue is None:
            return self.read_note(command)

        async def operation() -> ReadNoteResult:
            return self.read_note(command)

        return await self.queue.run(operation)

    def read_note(self, command: ReadNoteCommand) -> ReadNoteResult:
        resolved_path = self.paths.resolve_note_path(command.note_path)
        if not resolved_path.exists():
            raise FileNotFoundError(f"note not found: {Path(command.note_path).as_posix()}")

        raw_content, parsed, fields = self._read_normalized_content(resolved_path)
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

    def _read_normalized_content(
        self,
        resolved_path: Path,
    ) -> tuple[str, ParsedNote, FrontmatterFields]:
        for _ in range(3):
            raw_content = resolved_path.read_text(encoding="utf-8")
            parsed = parse_note(raw_content)
            if parsed.frontmatter is None:
                raise ValueError("note must include YAML frontmatter for structured read")

            fields = _parse_frontmatter(parsed.frontmatter)
            normalized_content, normalized_fields = _normalize_non_utc_timestamps(
                raw_content=raw_content,
                frontmatter=parsed.frontmatter,
                fields=fields,
                actor=self.actor,
            )
            if normalized_content == raw_content:
                return raw_content, parsed, fields

            current_content = resolved_path.read_text(encoding="utf-8")
            if current_content != raw_content:
                continue

            resolved_path.write_text(normalized_content, encoding="utf-8")
            return normalized_content, parse_note(normalized_content), normalized_fields

        raise ValueError("note changed while normalizing timestamps; retry read")


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
    if not is_note_timestamp_utc_z(value):
        raise ValueError(f"frontmatter field {key!r} must be a UTC-compatible timestamp")
    try:
        return coerce_note_timestamp_to_utc(value, field_name=f"frontmatter field {key!r}")
    except ValueError as error:
        raise ValueError(f"frontmatter field {key!r} must be a UTC-compatible timestamp") from error


def _required_or_repaired_timestamp(fields: FrontmatterFields, key: str) -> datetime:
    try:
        return _required_timestamp(fields, key)
    except ValueError as validation_error:
        value = _required_scalar(fields, key)
        try:
            return coerce_legacy_note_timestamp_to_utc(
                value,
                field_name=f"frontmatter field {key!r}",
            )
        except ValueError as repair_error:
            raise validation_error from repair_error


def _normalize_non_utc_timestamps(
    *,
    raw_content: str,
    frontmatter: str,
    fields: FrontmatterFields,
    actor: str,
) -> tuple[str, FrontmatterFields]:
    replacements: dict[str, str] = {}
    for key in ("created", "updated"):
        timestamp = _required_or_repaired_timestamp(fields, key)
        formatted = format_note_timestamp(timestamp)
        if _required_scalar(fields, key) != formatted:
            replacements[key] = formatted

    if not replacements:
        return raw_content, fields

    normalized_frontmatter = _replace_frontmatter_scalars(frontmatter, replacements)
    normalized_content = _replace_frontmatter(raw_content, normalized_frontmatter)
    normalized_content = _replace_provenance_trailer(
        original_content=raw_content,
        normalized_content=normalized_content,
        actor=actor,
    )
    normalized_fields = dict(fields)
    normalized_fields.update(replacements)
    return normalized_content, normalized_fields


def _replace_provenance_trailer(
    *,
    original_content: str,
    normalized_content: str,
    actor: str,
) -> str:
    if PROVENANCE_PREFIX not in original_content:
        return normalized_content

    source_content = strip_provenance_trailer(normalized_content)
    return append_provenance_trailer(
        source_content,
        source_hash=compute_sha256(source_content),
        operation="read_note",
        actor=actor,
    )


def _replace_frontmatter(raw_content: str, frontmatter: str) -> str:
    closing_delimiter = raw_content.find(f"\n{FRONTMATTER_DELIMITER}\n", 4)
    if closing_delimiter == -1:
        raise ValueError("note must include YAML frontmatter for structured read")
    body_start = closing_delimiter + len(f"\n{FRONTMATTER_DELIMITER}\n")
    return (
        f"{FRONTMATTER_DELIMITER}\n{frontmatter}\n"
        f"{FRONTMATTER_DELIMITER}\n{raw_content[body_start:]}"
    )


def _replace_frontmatter_scalars(frontmatter: str, replacements: dict[str, str]) -> str:
    pending = set(replacements)
    lines: list[str] = []
    for line in frontmatter.splitlines():
        key, separator, _ = line.partition(":")
        if separator and key.strip() in pending:
            key_name = key.strip()
            lines.append(f'{key_name}: "{replacements[key_name]}"')
            pending.remove(key_name)
            continue
        lines.append(line)
    if pending:
        missing = ", ".join(sorted(pending))
        raise ValueError(f"frontmatter timestamp field is missing: {missing}")
    return "\n".join(lines)


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
