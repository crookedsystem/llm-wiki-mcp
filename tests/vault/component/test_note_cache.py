from __future__ import annotations

import os
from pathlib import Path

from pytest import MonkeyPatch

from vault.component.note_cache import VaultNoteCache
from vault.infrastructure.repository.vault_note_repository import VaultNoteRepository
from vault.service.command.context_command import ContextCommand
from vault.service.vault_context_graph_builder import VaultContextGraphBuilder


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _count_reads(monkeypatch: MonkeyPatch) -> dict[str, int]:
    counter = {"reads": 0}
    original = VaultNoteRepository.read_note

    def counting(self: VaultNoteRepository, note_path: Path) -> str:
        counter["reads"] += 1
        return original(self, note_path)

    monkeypatch.setattr(VaultNoteRepository, "read_note", counting)
    return counter


def _cache(vault_root: Path) -> VaultNoteCache:
    return VaultNoteCache(note_repository=VaultNoteRepository(root=vault_root))


def test_load_all은_변경없는_노트를_다시_읽지_않는다(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    vault = tmp_path / "vault"
    _write(vault / "concepts/a.md", "# A\n\nalpha\n")
    _write(vault / "concepts/b.md", "# B\n\nbeta\n")
    cache = _cache(vault)
    reads = _count_reads(monkeypatch)

    first = cache.load_all()
    assert reads["reads"] == 2  # cold: both notes read once

    second = cache.load_all()
    assert reads["reads"] == 2  # warm: no re-read for unchanged files
    assert {n.path for n in first} == {n.path for n in second}
    assert [n.content_hash for n in first] == [n.content_hash for n in second]


def test_load_all은_mtime이_바뀌면_재파싱한다(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    vault = tmp_path / "vault"
    target = vault / "concepts/a.md"
    _write(target, "# A\n\nalpha\n")
    cache = _cache(vault)
    reads = _count_reads(monkeypatch)

    before = cache.load_all()[0]
    assert reads["reads"] == 1

    # Change content and force a distinct mtime so the validation is deterministic
    # regardless of filesystem timestamp granularity.
    target.write_text("# A\n\nalpha updated\n", encoding="utf-8")
    stat = target.stat()
    os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))

    after = cache.load_all()[0]
    assert reads["reads"] == 2  # changed file re-read
    assert after.content_hash != before.content_hash
    assert "updated" in after.content


def test_load_all은_삭제된_노트를_제거하고_추가된_노트를_포함한다(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write(vault / "concepts/a.md", "# A\n")
    _write(vault / "concepts/b.md", "# B\n")
    cache = _cache(vault)

    assert {n.path for n in cache.load_all()} == {"concepts/a.md", "concepts/b.md"}

    (vault / "concepts/b.md").unlink()
    _write(vault / "entities/c.md", "# C\n")

    assert {n.path for n in cache.load_all()} == {"concepts/a.md", "entities/c.md"}


def test_builder는_path_prefix로_scoped_notes를_메모리에서_거른다(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write(vault / "entities/kafka.md", "---\ntype: entity\n---\n# Kafka\n\nkafka broker\n")
    _write(vault / "concepts/kafka-note.md", "---\ntype: concept\n---\n# Kafka note\n\nkafka\n")
    builder = VaultContextGraphBuilder(
        note_repository=VaultNoteRepository(root=vault),
        note_cache=_cache(vault),
    )

    scoped = builder.build_graph(
        ContextCommand(query="kafka", mode="prompt", limit=16, path_prefix="entities")
    )
    unscoped = builder.build_graph(
        ContextCommand(query="kafka", mode="prompt", limit=16, path_prefix=None)
    )

    scoped_paths = {ref.path for ref in scoped.link_targets}
    unscoped_paths = {ref.path for ref in unscoped.link_targets}
    assert scoped_paths == {"entities/kafka.md"}
    assert "concepts/kafka-note.md" in unscoped_paths
