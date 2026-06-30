from datetime import datetime
from pathlib import Path
from typing import cast

from common.model import FrozenModel
from vault.component.write_queue import VaultWriteQueue
from vault.entity.note_time import (
    format_note_time,
    is_utc_note_time_text,
    parse_note_time,
    parse_old_note_time,
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

        file_text, parsed, fields = self._read_fixed_content(resolved_path)
        title = _required_text(fields, "title")
        body = _strip_rendered_title_and_provenance(parsed.body, title)
        return ReadNoteResult(
            path=resolved_path.relative_to(self.paths.root.resolve()),
            title=title,
            type=_required_type(fields),
            tags=_string_tuple(fields, "tags"),
            sources=_string_tuple(fields, "sources"),
            body=body,
            created=_required_time(fields, "created"),
            updated=_required_time(fields, "updated"),
            confidence=_optional_confidence(fields),
            contested=_optional_bool(fields, "contested"),
            content_hash=compute_sha256(file_text),
        )

    def _read_fixed_content(
        self,
        resolved_path: Path,
    ) -> tuple[str, ParsedNote, FrontmatterFields]:
        for _ in range(3):
            file_text = resolved_path.read_text(encoding="utf-8")
            parsed = parse_note(file_text)
            if parsed.frontmatter is None:
                raise ValueError("note must include YAML frontmatter for structured read")

            fields = _parse_frontmatter(parsed.frontmatter)
            fixed_content, fixed_fields = _fix_note_times(
                file_text=file_text,
                frontmatter=parsed.frontmatter,
                fields=fields,
                actor=self.actor,
            )
            if fixed_content == file_text:
                return file_text, parsed, fields

            current_content = resolved_path.read_text(encoding="utf-8")
            if current_content != file_text:
                continue

            resolved_path.write_text(fixed_content, encoding="utf-8")
            return fixed_content, parse_note(fixed_content), fixed_fields

        raise ValueError("note changed while fixing times; retry read")


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
            fields[key_name] = _read_text_or_list(stripped_value)
            index += 1
            continue

        items: list[str] = []
        index += 1
        while index < len(lines):
            item_line = lines[index].strip()
            if not item_line.startswith("-"):
                break
            items.append(_clean_text(item_line[1:].strip()))
            index += 1
        fields[key_name] = tuple(item for item in items if item)
    return fields


def _read_text_or_list(value: str) -> str | bool | tuple[str, ...]:
    if value == "[]":
        return ()
    if value.startswith("[") and value.endswith("]"):
        return tuple(_clean_text(part.strip()) for part in value[1:-1].split(",") if part.strip())
    text = _clean_text(value)
    if text == "true":
        return True
    if text == "false":
        return False
    return text


def _clean_text(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value.replace('\\"', '"').replace("\\\\", "\\")


def _required_text(fields: FrontmatterFields, key: str) -> str:
    value = fields.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"frontmatter field {key!r} is required")
    return value


def _required_type(fields: FrontmatterFields) -> WikiNoteType:
    value = _required_text(fields, "type")
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


def _required_time(fields: FrontmatterFields, key: str) -> datetime:
    value = _required_text(fields, key)
    if not is_utc_note_time_text(value):
        raise ValueError(f"frontmatter field {key!r} must be a UTC time")
    try:
        return parse_note_time(value, field_name=f"frontmatter field {key!r}")
    except ValueError as error:
        raise ValueError(f"frontmatter field {key!r} must be a UTC time") from error


def _read_or_fix_time(fields: FrontmatterFields, key: str) -> datetime:
    try:
        return _required_time(fields, key)
    except ValueError as validation_error:
        value = _required_text(fields, key)
        try:
            return parse_old_note_time(
                value,
                field_name=f"frontmatter field {key!r}",
            )
        except ValueError as repair_error:
            raise validation_error from repair_error


def _fix_note_times(
    *,
    file_text: str,
    frontmatter: str,
    fields: FrontmatterFields,
    actor: str,
) -> tuple[str, FrontmatterFields]:
    fixed_times: dict[str, str] = {}
    for key in ("created", "updated"):
        note_time = _read_or_fix_time(fields, key)
        time_text = format_note_time(note_time)
        if _required_text(fields, key) != time_text:
            fixed_times[key] = time_text

    if not fixed_times:
        return file_text, fields

    fixed_frontmatter = _replace_frontmatter_values(frontmatter, fixed_times)
    fixed_content = _replace_frontmatter(file_text, fixed_frontmatter)
    fixed_content = _replace_provenance_trailer(
        original_content=file_text,
        fixed_content=fixed_content,
        actor=actor,
    )
    fixed_fields = dict(fields)
    fixed_fields.update(fixed_times)
    return fixed_content, fixed_fields


def _replace_provenance_trailer(
    *,
    original_content: str,
    fixed_content: str,
    actor: str,
) -> str:
    if PROVENANCE_PREFIX not in original_content:
        return fixed_content

    source_content = strip_provenance_trailer(fixed_content)
    return append_provenance_trailer(
        source_content,
        source_hash=compute_sha256(source_content),
        operation="read_note",
        actor=actor,
    )


def _replace_frontmatter(file_text: str, frontmatter: str) -> str:
    closing_delimiter = file_text.find(f"\n{FRONTMATTER_DELIMITER}\n", 4)
    if closing_delimiter == -1:
        raise ValueError("note must include YAML frontmatter for structured read")
    body_start = closing_delimiter + len(f"\n{FRONTMATTER_DELIMITER}\n")
    return (
        f"{FRONTMATTER_DELIMITER}\n{frontmatter}\n{FRONTMATTER_DELIMITER}\n{file_text[body_start:]}"
    )


def _replace_frontmatter_values(frontmatter: str, fixed_times: dict[str, str]) -> str:
    pending = set(fixed_times)
    lines: list[str] = []
    for line in frontmatter.splitlines():
        key, separator, _ = line.partition(":")
        if separator and key.strip() in pending:
            key_name = key.strip()
            lines.append(f'{key_name}: "{fixed_times[key_name]}"')
            pending.remove(key_name)
            continue
        lines.append(line)
    if pending:
        missing = ", ".join(sorted(pending))
        raise ValueError(f"frontmatter time field is missing: {missing}")
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
