from common.helper.wiki_link_helper import extract_wiki_links, normalize_wiki_target
from common.model import FrozenModel
from vault.service.vault_operational_note import (
    OperationalNote,
    join_body,
    strip_trailing_blank_lines,
)

_INDEX_TITLE = "Wiki Index"
_INDEX_INTRO = "> Central index of all wiki notes. Grouped by type."
_SECTION_PREFIX = "## "
_LIST_ITEM_PREFIX = "- "


class IndexEntry(FrozenModel):
    """One index list item pointing at a synthesized or raw note."""

    slug: str  # e.g. concepts/foo
    title: str
    summary: str | None  # one-line description; omitted suffix when None
    section: str  # canonical heading text, e.g. "Concepts"
    updated: str  # full timestamp used to seed/refresh frontmatter


class VaultIndexService(FrozenModel):
    """Insert or refresh a note's entry in ``index.md`` under its type section."""

    def upsert_entry(self, existing: str | None, entry: IndexEntry) -> str:
        note = self._parse_or_seed(existing, entry.updated)
        new_body = self._upsert(note.body, entry)
        return note.with_body(new_body).with_updated(entry.updated).render()

    def _parse_or_seed(self, existing: str | None, timestamp: str) -> OperationalNote:
        if existing is None:
            return _seed_index(timestamp)
        return OperationalNote.parse(existing)

    def _upsert(self, body: str, entry: IndexEntry) -> str:
        lines = body.split("\n")
        existing = _existing_entry_index(lines, entry.slug)
        if existing is None:
            result = _insert_into_section(lines, entry, _render_line(entry))
        else:
            # On a summary-less update, keep the description the entry already had so
            # a routine kb_read_note -> kb_write_note edit never wipes index.md prose.
            summary = (
                entry.summary
                if entry.summary is not None
                else _existing_description(lines[existing])
            )
            line = _compose_line(entry.slug, entry.title, summary)
            result = [*lines[:existing], line, *lines[existing + 1 :]]
        return join_body(result)


def _render_line(entry: IndexEntry) -> str:
    return _compose_line(entry.slug, entry.title, entry.summary)


def _compose_line(slug: str, title: str, summary: str | None) -> str:
    link = f"- [[{slug}|{title}]]"
    return f"{link} — {summary}" if summary else link


def _existing_entry_index(lines: list[str], slug: str) -> int | None:
    for index, line in enumerate(lines):
        if _entry_target(line) == slug:
            return index
    return None


def _existing_description(line: str) -> str | None:
    """The one-line description already on an index entry, if it has one."""
    link_close = line.find("]]")
    if link_close == -1:
        return None
    remainder = line[link_close + 2 :]
    separator = " — "
    if not remainder.startswith(separator):
        return None
    return remainder[len(separator) :].strip() or None


def _entry_target(line: str) -> str | None:
    """The slug a list item links to, taken from its first wikilink (its anchor)."""
    if not line.lstrip().startswith(_LIST_ITEM_PREFIX):
        return None
    links = extract_wiki_links(line)
    return normalize_wiki_target(links[0]) if links else None


def _insert_into_section(lines: list[str], entry: IndexEntry, line: str) -> list[str]:
    header = _section_header_index(lines, entry.section)
    if header is None:
        return [*strip_trailing_blank_lines(lines), "", f"{_SECTION_PREFIX}{entry.section}", line]
    insert_at = _section_insert_index(lines, header)
    return [*lines[:insert_at], line, *lines[insert_at:]]


def _section_header_index(lines: list[str], section: str) -> int | None:
    target = f"{_SECTION_PREFIX}{section}"
    for index, line in enumerate(lines):
        if line.strip() == target:
            return index
    return None


def _section_insert_index(lines: list[str], header: int) -> int:
    """Index just after the section's last list item (before the next heading)."""
    last_item = header
    for index in range(header + 1, len(lines)):
        if lines[index].startswith(_SECTION_PREFIX):
            break
        if lines[index].lstrip().startswith(_LIST_ITEM_PREFIX):
            last_item = index
    return last_item + 1


def _seed_index(timestamp: str) -> OperationalNote:
    frontmatter = (
        f"title: {_INDEX_TITLE}\n"
        f'created: "{timestamp}"\n'
        f'updated: "{timestamp}"\n'
        "type: index\n"
        "tags:\n"
        "  - llm-wiki\n"
        "  - knowledge-base\n"
        "  - obsidian\n"
        "sources: []"
    )
    body = f"\n# {_INDEX_TITLE}\n\n{_INDEX_INTRO}\n"
    return OperationalNote(frontmatter=frontmatter, body=body)
