from typing import Literal

from common.model import FrozenModel
from vault.service.vault_operational_note import (
    OperationalNote,
    join_body,
    strip_leading_blank_lines,
    strip_trailing_blank_lines,
)

WriteAction = Literal["create", "update", "delete"]

_LOG_TITLE = "Wiki Log"
_LOG_INTRO = "> Append-only changelog of wiki writes. Newest entries at top."
_ENTRY_HEADING_PREFIX = "## ["
_ACTION_LABELS: dict[WriteAction, str] = {
    "create": "Created",
    "update": "Updated",
    "delete": "Deleted",
}


class LogEntry(FrozenModel):
    """One changelog entry describing a single durable note write."""

    date: str  # YYYY-MM-DD
    action: WriteAction
    slug: str  # e.g. concepts/foo
    path: str  # e.g. concepts/foo.md
    description: str  # summary, or the note title as a fallback
    updated: str  # full timestamp used to seed/refresh frontmatter


class VaultLogService(FrozenModel):
    """Append a write to ``log.md`` as a newest-at-top changelog entry."""

    def append_entry(self, existing: str | None, entry: LogEntry) -> str:
        note = self._parse_or_seed(existing, entry.updated)
        new_body = self._prepend(note.body, entry)
        return note.with_body(new_body).with_updated(entry.updated).render()

    def _parse_or_seed(self, existing: str | None, timestamp: str) -> OperationalNote:
        if existing is None:
            return _seed_log(timestamp)
        return OperationalNote.parse(existing)

    def _prepend(self, body: str, entry: LogEntry) -> str:
        block = _render_block(entry)
        lines = body.split("\n")
        first_entry = _first_entry_index(lines)
        head = strip_trailing_blank_lines(lines[:first_entry])
        tail = strip_leading_blank_lines(lines[first_entry:])
        result = [*head, "", *block]
        if tail:
            result += ["", *tail]
        return join_body(result)


def _render_block(entry: LogEntry) -> list[str]:
    label = _ACTION_LABELS[entry.action]
    return [
        f"## [{entry.date}] {entry.action} | {entry.slug}",
        f"- {label}: `{entry.path}` — {entry.description}",
    ]


def _first_entry_index(lines: list[str]) -> int:
    for index, line in enumerate(lines):
        if line.startswith(_ENTRY_HEADING_PREFIX):
            return index
    return len(lines)


def _seed_log(timestamp: str) -> OperationalNote:
    frontmatter = (
        f"title: {_LOG_TITLE}\n"
        f'created: "{timestamp}"\n'
        f'updated: "{timestamp}"\n'
        "type: log\n"
        "tags:\n"
        "  - llm-wiki\n"
        "  - knowledge-base\n"
        "  - obsidian\n"
        "sources: []"
    )
    body = f"\n# {_LOG_TITLE}\n\n{_LOG_INTRO}\n"
    return OperationalNote(frontmatter=frontmatter, body=body)
