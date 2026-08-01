import re
from typing import Literal

from common.model import FrozenModel
from vault.service.vault_operational_note import (
    OperationalNote,
    join_body,
    strip_leading_blank_lines,
    strip_trailing_blank_lines,
)
from vault.service.vault_operational_paths import log_archive_path

WriteAction = Literal["create", "update", "delete"]

_LOG_TITLE = "Wiki Log"
_LOG_INTRO = "> Append-only changelog of wiki writes. Newest entries at top."
_ENTRY_HEADING_PREFIX = "## ["
_ARCHIVE_POINTER_PREFIX = "> Archived: "
_ARCHIVE_LINK_PATTERN = re.compile(r"\[\[log-(\d{4})]]")
_ENTRY_DATE_LENGTH = len("YYYY-MM-DD")
_ENTRY_YEAR_LENGTH = len("YYYY")
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


class LogArchive(FrozenModel):
    """지난 연도 changelog만 담는 log-YYYY.md 한 개의 상대 경로와 최종 본문."""

    path: str
    content: str


class LogRotation(FrozenModel):
    """연도 rotation을 적용한 log.md 본문과, 같은 transaction에서 함께 써야 할 archive들."""

    log: str
    archives: list[LogArchive]


class VaultLogService(FrozenModel):
    """Append a write to ``log.md`` as a newest-at-top changelog entry."""

    def append_entry(self, existing: str | None, entry: LogEntry) -> str:
        note = self._parse_or_seed(existing, entry.updated)
        new_body = self._prepend(note.body, entry)
        return note.with_body(new_body).with_updated(entry.updated).render()

    def rotate_by_year(
        self,
        log_content: str,
        *,
        existing_archives: dict[str, str],
        timestamp: str,
    ) -> LogRotation:
        """가장 최근 연도가 아닌 항목을 log-YYYY.md로 옮겨 log.md가 한 해 분량을 넘지 않게 합니다.

        log.md 상단에는 옮겨간 연도를 가리키는 ``> Archived:`` 포인터가 남아 전체 히스토리를
        따라갈 수 있습니다. 날짜를 읽을 수 없는 항목이 하나라도 있으면 rotation을 건너뛰어
        손으로 편집된 log를 잘라내지 않습니다.
        """
        note = OperationalNote.parse(log_content)
        lines = note.body.split("\n")
        first_entry = _first_entry_index(lines)
        blocks = _entry_blocks(lines[first_entry:])
        if any(_entry_year(block[0]) is None for block in blocks):
            return LogRotation(log=log_content, archives=[])

        blocks_by_year = _blocks_by_year(blocks)
        if len(blocks_by_year) <= 1:
            return LogRotation(log=log_content, archives=[])

        current_year = max(blocks_by_year)
        archived_years = sorted(year for year in blocks_by_year if year != current_year)
        archives = [
            LogArchive(
                path=log_archive_path(year),
                content=_merged_archive(
                    existing_archives.get(log_archive_path(year)),
                    year=year,
                    blocks=blocks_by_year[year],
                    timestamp=timestamp,
                ),
            )
            for year in archived_years
        ]
        head = _head_with_archive_pointer(lines[:first_entry], archived_years)
        body = join_body([*head, "", *_block_lines(blocks_by_year[current_year])])
        return LogRotation(
            log=note.with_body(body).with_updated(timestamp).render(),
            archives=archives,
        )

    def entry_years(self, log_content: str) -> list[str]:
        """log.md에 남아 있는 changelog 항목의 연도 목록 — rotation 대상 경로 예측에 씁니다."""
        lines = OperationalNote.parse(log_content).body.split("\n")
        blocks = _entry_blocks(lines[_first_entry_index(lines) :])
        return sorted({year for block in blocks if (year := _entry_year(block[0])) is not None})

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


def _entry_blocks(lines: list[str]) -> list[list[str]]:
    """changelog 본문을 항목 heading 단위 block으로 쪼갭니다."""
    blocks: list[list[str]] = []
    for line in lines:
        if line.startswith(_ENTRY_HEADING_PREFIX):
            blocks.append([line])
        elif blocks:
            blocks[-1].append(line)
    return [strip_trailing_blank_lines(block) for block in blocks]


def _block_lines(blocks: list[list[str]]) -> list[str]:
    return [line for block in blocks for line in (*block, "")]


def _entry_year(heading: str) -> str | None:
    year = heading[len(_ENTRY_HEADING_PREFIX) :][:_ENTRY_YEAR_LENGTH]
    return year if year.isdigit() else None


def _entry_date(block: list[str]) -> str:
    return block[0][len(_ENTRY_HEADING_PREFIX) :][:_ENTRY_DATE_LENGTH]


def _blocks_by_year(blocks: list[list[str]]) -> dict[str, list[list[str]]]:
    grouped: dict[str, list[list[str]]] = {}
    for block in blocks:
        year = _entry_year(block[0])
        if year is not None:
            grouped.setdefault(year, []).append(block)
    return grouped


def _head_with_archive_pointer(head: list[str], archived_years: list[str]) -> list[str]:
    """intro 아래의 archive 포인터 줄을, 이번에 옮겨간 연도까지 합쳐 다시 씁니다."""
    years = set(archived_years)
    kept: list[str] = []
    for line in head:
        if line.startswith(_ARCHIVE_POINTER_PREFIX):
            years.update(_ARCHIVE_LINK_PATTERN.findall(line))
            continue
        kept.append(line)
    pointer = _ARCHIVE_POINTER_PREFIX + ", ".join(f"[[log-{year}]]" for year in sorted(years))
    return [*strip_trailing_blank_lines(kept), pointer]


def _merged_archive(
    existing: str | None,
    *,
    year: str,
    blocks: list[list[str]],
    timestamp: str,
) -> str:
    """이미 있는 archive에 이번에 옮겨온 항목을 합쳐 최신순으로 다시 씁니다."""
    note = (
        OperationalNote.parse(existing) if existing is not None else _seed_archive(year, timestamp)
    )
    lines = note.body.split("\n")
    first_entry = _first_entry_index(lines)
    merged = sorted([*blocks, *_entry_blocks(lines[first_entry:])], key=_entry_date, reverse=True)
    head = strip_trailing_blank_lines(lines[:first_entry])
    body = join_body([*head, "", *_block_lines(merged)])
    return note.with_body(body).with_updated(timestamp).render()


def _seed_archive(year: str, timestamp: str) -> OperationalNote:
    return OperationalNote(
        frontmatter=_operational_frontmatter(f"{_LOG_TITLE} {year}", timestamp),
        body=(
            f"\n# {_LOG_TITLE} {year}\n\n"
            f"> {year} changelog entries archived from [[log]]. Newest entries at top.\n"
        ),
    )


def _seed_log(timestamp: str) -> OperationalNote:
    return OperationalNote(
        frontmatter=_operational_frontmatter(_LOG_TITLE, timestamp),
        body=f"\n# {_LOG_TITLE}\n\n{_LOG_INTRO}\n",
    )


def _operational_frontmatter(title: str, timestamp: str) -> str:
    return (
        f"title: {title}\n"
        f'created: "{timestamp}"\n'
        f'updated: "{timestamp}"\n'
        "type: log\n"
        "tags:\n"
        "  - llm-wiki\n"
        "  - knowledge-base\n"
        "  - obsidian\n"
        "sources: []"
    )
