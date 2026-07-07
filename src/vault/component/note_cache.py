from __future__ import annotations

import threading
from pathlib import Path

from pydantic import PrivateAttr

from common.helper.note_metadata_helper import extract_note_metadata
from common.helper.wiki_link_helper import extract_wiki_links
from common.model import FrozenModel, MutableModel
from vault.entity.vault_note import compute_sha256
from vault.infrastructure.repository.vault_note_repository import VaultNoteRepository


class NoteContext(FrozenModel):
    """Parsed, immutable view of one Markdown note used by context/search building."""

    path: str
    title: str | None
    page_type: str | None
    tags: list[str]
    headings: list[str]
    content: str
    content_hash: str
    links: list[str]


class VaultNoteCache(MutableModel):
    """Cache parsed notes across calls, revalidated by (mtime_ns, size, ctime_ns) each load.

    This is a *validation* cache, not a TTL cache: every ``load_all`` re-stats every
    file, so a note whose content changed (via kb_write_note, git, or an external
    editor) is re-read on the next call. There is no staleness window. The expensive
    per-note work (read + frontmatter parse + sha256 + wiki-link extraction) is what
    gets skipped for unchanged files; the directory walk still runs so newly added
    and deleted notes are always reflected.

    ctime_ns is included alongside mtime_ns and size because a rewrite that keeps the
    same byte length while preserving mtime (cp -p, rsync --times, tar extraction) or
    on a filesystem with coarse mtime resolution would otherwise collide on
    (mtime_ns, size) and serve the stale parse indefinitely. ctime cannot be set from
    userspace and the kernel bumps it on every content write/replace, so it closes the
    mtime-preserving vector; only a coarse-resolution filesystem taking two same-size
    writes inside one timestamp tick remains, which is exotic and equally affects any
    stat-based cache.
    """

    note_repository: VaultNoteRepository
    _entries: dict[str, tuple[int, int, int, NoteContext]] = PrivateAttr(default_factory=dict)
    _lock: threading.Lock = PrivateAttr(default_factory=threading.Lock)

    def load_all(self) -> list[NoteContext]:
        previous = self._entries
        fresh: dict[str, tuple[int, int, int, NoteContext]] = {}
        result: list[NoteContext] = []
        for note_path in self.note_repository.markdown_notes():
            relative_path = self.note_repository.relative_path(note_path)
            stat = note_path.stat()
            signature = (stat.st_mtime_ns, stat.st_size, stat.st_ctime_ns)
            cached = previous.get(relative_path)
            if cached is not None and cached[:3] == signature:
                note = cached[3]
            else:
                note = self._build_note(note_path, relative_path)
            fresh[relative_path] = (*signature, note)
            result.append(note)
        # Atomic swap drops entries for deleted notes without a separate eviction pass.
        # Concurrent loads simply rebuild independently and last-writer-wins; every
        # returned list is internally consistent because NoteContext values are frozen.
        with self._lock:
            self._entries = fresh
        return result

    def _build_note(self, note_path: Path, relative_path: str) -> NoteContext:
        content = self.note_repository.read_note(note_path)
        metadata = extract_note_metadata(content)
        return NoteContext(
            path=relative_path,
            title=metadata.title,
            page_type=metadata.page_type,
            tags=metadata.tags,
            headings=metadata.headings,
            content=content,
            content_hash=compute_sha256(content),
            links=extract_wiki_links(content),
        )
