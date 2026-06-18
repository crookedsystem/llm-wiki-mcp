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
        line = _render_line(entry)
        lines = body.split("\n")
        replaced = _replace_existing(lines, entry.slug, line)
        result = replaced if replaced is not None else _insert_into_section(lines, entry, line)
        return join_body(result)


def _render_line(entry: IndexEntry) -> str:
    link = f"- [[{entry.slug}|{entry.title}]]"
    return f"{link} — {entry.summary}" if entry.summary else link


def _replace_existing(lines: list[str], slug: str, line: str) -> list[str] | None:
    for index, existing_line in enumerate(lines):
        if _entry_target(existing_line) == slug:
            return [*lines[:index], line, *lines[index + 1 :]]
    return None


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
