import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from vault.component.write_queue import VaultWriteQueue
from vault.entity.vault_note import compute_sha256
from vault.entity.vault_path import VaultPaths
from vault.error.write_error import WriteConflictError
from vault.service.command.read_note_command import ReadNoteCommand
from vault.service.command.write_note_command import WriteNoteCommand
from vault.service.vault_read_service import VaultReadService
from vault.service.vault_write_service import VaultWriteService

_DEFAULT_CREATED = datetime(2026, 6, 12, 9, 30, 45, tzinfo=UTC)
_DEFAULT_UPDATED = datetime(2026, 6, 12, 10, 31, 46, tzinfo=UTC)


def _write_command(
    *,
    note_path: str = "index.md",
    title: str = "Wiki Index",
    note_type: str = "index",
    tags: tuple[str, ...] = ("llm-wiki", "knowledge-base"),
    sources: tuple[str, ...] = (),
    body: str = "## Entities\n- [[entities/existing]] — Existing entity.",
    created: Any = _DEFAULT_CREATED,
    updated: Any = _DEFAULT_UPDATED,
    if_hash: str | None = None,
) -> WriteNoteCommand:
    return WriteNoteCommand(
        note_path=note_path,
        title=title,
        type=note_type,  # type: ignore[arg-type]
        tags=tags,
        sources=sources,
        body=body,
        created=created,
        updated=updated,
        confidence="medium",
        contested=False,
        if_hash=if_hash,
    )


def test_read_note는_write_note에_재사용할_structured_fields와_hash를_반환한다(
    tmp_path: Path,
) -> None:
    async def exercise_read() -> None:
        # Given: write tool이 렌더링한 기존 index note가 있다.
        vault_root = tmp_path / "vault"
        paths = VaultPaths(root=vault_root)
        writer = VaultWriteService(paths=paths, queue=VaultWriteQueue(), actor="tester")
        reader = VaultReadService(paths=paths)
        write_result = await writer.write_note(_write_command())

        # When: read service로 note를 structured field 형태로 읽는다.
        read_result = reader.read_note(ReadNoteCommand(note_path="index.md"))

        # Then: body는 frontmatter/title/provenance 없이 반환되고 content_hash는 현재 파일과 같다.
        assert read_result.path == Path("index.md")
        assert read_result.title == "Wiki Index"
        assert read_result.type == "index"
        assert read_result.tags == ("llm-wiki", "knowledge-base")
        assert read_result.sources == ()
        assert read_result.body == "## Entities\n- [[entities/existing]] — Existing entity."
        assert read_result.created == datetime(2026, 6, 12, 9, 30, 45, tzinfo=UTC)
        assert read_result.updated == datetime(2026, 6, 12, 10, 31, 46, tzinfo=UTC)
        assert read_result.confidence == "medium"
        assert read_result.contested is False
        assert read_result.content_hash == write_result.content_hash
        assert read_result.content_hash == compute_sha256(
            (vault_root / "index.md").read_text(encoding="utf-8")
        )

    asyncio.run(exercise_read())


def test_read_note는_non_utc_timestamp를_utc_z로_저장한_뒤_반환한다(tmp_path: Path) -> None:
    # Given: UTC offset timestamp를 가진 legacy note가 있다.
    vault_root = tmp_path / "vault"
    note_path = vault_root / "concepts" / "legacy.md"
    note_path.parent.mkdir(parents=True)
    note_path.write_text(
        """---
title: Legacy
created: "2026-06-12T18:30:45+09:00"
updated: "2026-06-12T19:31:46+09:00"
type: concept
tags: []
sources: []
---

# Legacy

## Summary
Body
""",
        encoding="utf-8",
    )
    reader = VaultReadService(paths=VaultPaths(root=vault_root))

    # When: note를 structured field로 읽는다.
    read_result = reader.read_note(ReadNoteCommand(note_path="concepts/legacy.md"))

    # Then: timestamp는 UTC Z로 파일에 저장되고 반환 hash도 저장 후 내용을 기준으로 한다.
    normalized = note_path.read_text(encoding="utf-8")
    assert 'created: "2026-06-12T09:30:45Z"' in normalized
    assert 'updated: "2026-06-12T10:31:46Z"' in normalized
    assert read_result.created == datetime(2026, 6, 12, 9, 30, 45, tzinfo=UTC)
    assert read_result.updated == datetime(2026, 6, 12, 10, 31, 46, tzinfo=UTC)
    assert read_result.content_hash == compute_sha256(normalized)


def test_read_note는_timestamp_정규화시_provenance_hash를_갱신한다(tmp_path: Path) -> None:
    # Given: provenance trailer가 있는 legacy note가 있다.
    vault_root = tmp_path / "vault"
    note_path = vault_root / "concepts" / "legacy.md"
    note_path.parent.mkdir(parents=True)
    note_path.write_text(
        """---
title: Legacy
created: "2026-06-12T18:30:45+09:00"
updated: "2026-06-12T19:31:46+09:00"
type: concept
tags: []
sources: []
---

# Legacy

## Summary
Body
<!-- kb-provenance: source_hash=stale; operation=write_note; actor=tester -->
""",
        encoding="utf-8",
    )
    reader = VaultReadService(paths=VaultPaths(root=vault_root), actor="tester")

    # When: note를 읽으면서 timestamp를 정규화한다.
    reader.read_note(ReadNoteCommand(note_path="concepts/legacy.md"))

    # Then: provenance trailer의 source_hash도 정규화된 source content 기준으로 갱신된다.
    normalized = note_path.read_text(encoding="utf-8")
    source_content = normalized.split("<!-- kb-provenance:", maxsplit=1)[0]
    assert f"source_hash={compute_sha256(source_content)}" in normalized
    assert "source_hash=stale" not in normalized
    assert "operation=read_note" in normalized


def test_read후_full_body_patch와_matching_hash로_기존_note를_재작성한다(
    tmp_path: Path,
) -> None:
    async def exercise_full_patch() -> None:
        # Given: 기존 index note를 read해서 현재 full body와 content hash를 확보한다.
        paths = VaultPaths(root=tmp_path / "vault")
        writer = VaultWriteService(paths=paths, queue=VaultWriteQueue(), actor="tester")
        reader = VaultReadService(paths=paths)
        await writer.write_note(_write_command())
        read_result = reader.read_note(ReadNoteCommand(note_path="index.md"))

        # When: 기존 body 전체를 보존한 채 새 entry를 추가하고 if_hash로 재작성한다.
        patched_body = (
            f"{read_result.body}\n- [[entities/fanplus-old-api]] — Legacy FanPlus API boundary."
        )
        update_result = await writer.write_note(
            WriteNoteCommand(
                note_path="index.md",
                title=read_result.title,
                type=read_result.type,
                tags=read_result.tags,
                sources=read_result.sources,
                body=patched_body,
                updated=datetime(2026, 6, 12, 11, 0, 0, tzinfo=UTC),
                confidence=read_result.confidence,
                contested=read_result.contested,
                if_hash=read_result.content_hash,
            )
        )

        # Then: 기존 entry와 새 entry가 모두 보존되고 hash는 변경된다.
        updated_content = update_result.path.read_text(encoding="utf-8")
        assert "[[entities/existing]]" in updated_content
        assert "[[entities/fanplus-old-api]]" in updated_content
        assert update_result.content_hash != read_result.content_hash

    asyncio.run(exercise_full_patch())


def test_read후_stale_hash로_full_rewrite하면_기존_note를_보존하고_거부한다(
    tmp_path: Path,
) -> None:
    async def exercise_stale_hash() -> None:
        # Given: note를 읽은 뒤 다른 write가 먼저 파일을 변경했다.
        paths = VaultPaths(root=tmp_path / "vault")
        writer = VaultWriteService(paths=paths, queue=VaultWriteQueue(), actor="tester")
        reader = VaultReadService(paths=paths)
        initial_write = await writer.write_note(_write_command())
        read_result = reader.read_note(ReadNoteCommand(note_path="index.md"))
        await writer.write_note(
            _write_command(
                body="## Entities\n- [[entities/newer]] — Newer update.",
                created=None,
                if_hash=initial_write.content_hash,
            )
        )

        # When / Then: 오래된 hash로 full rewrite를 시도하면 거부되고 최신 내용은 유지된다.
        with pytest.raises(WriteConflictError, match="stale if_hash"):
            await writer.write_note(
                _write_command(
                    body=f"{read_result.body}\n- [[entities/stale]] — Stale update.",
                    if_hash=read_result.content_hash,
                )
            )

        final_content = (tmp_path / "vault" / "index.md").read_text(encoding="utf-8")
        assert "[[entities/newer]]" in final_content
        assert "[[entities/stale]]" not in final_content

    asyncio.run(exercise_stale_hash())


def test_read_note는_없는_note를_명확히_거부한다(tmp_path: Path) -> None:
    # Given: 빈 vault를 바라보는 reader가 있다.
    reader = VaultReadService(paths=VaultPaths(root=tmp_path / "vault"))

    # When / Then: 존재하지 않는 note read는 not found 오류를 낸다.
    with pytest.raises(FileNotFoundError, match="note not found"):
        reader.read_note(ReadNoteCommand(note_path="index.md"))
