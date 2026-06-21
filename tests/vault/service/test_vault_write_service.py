import asyncio
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from vault.component.write_queue import VaultWriteQueue
from vault.entity.vault_note import compute_sha256
from vault.entity.vault_path import VaultPaths
from vault.error.write_error import WriteConflictError
from vault.service.command.write_note_command import WikiNoteType, WriteNoteCommand
from vault.service.vault_write_service import VaultWriteService

_DEFAULT_CREATED = datetime(2026, 6, 12, 9, 30, 45, tzinfo=UTC)
_DEFAULT_UPDATED = datetime(2026, 6, 12, 10, 31, 46, tzinfo=UTC)


def _write_command(
    *,
    note_path: str = "concepts/today.md",
    title: str = "Today",
    note_type: WikiNoteType = "concept",
    tags: tuple[str, ...] = ("agent-memory",),
    sources: tuple[str, ...] = ("raw/articles/source.md",),
    body: str = "## Summary\nBody text",
    summary: str | None = None,
    created: Any = _DEFAULT_CREATED,
    updated: Any = _DEFAULT_UPDATED,
    if_hash: str | None = None,
) -> WriteNoteCommand:
    return WriteNoteCommand(
        note_path=note_path,
        title=title,
        type=note_type,
        tags=tags,
        sources=sources,
        body=body,
        created=created,
        updated=updated,
        summary=summary,
        confidence="medium",
        contested=False,
        if_hash=if_hash,
    )


def test_note_작성은_hash와_provenance를_함께_반환한다(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        # Given: provenance actor가 지정된 vault writer가 있다.
        writer = VaultWriteService(
            paths=VaultPaths(root=tmp_path / "vault"), queue=VaultWriteQueue(), actor="tester"
        )

        # When: structured field 기반 command로 새 markdown note를 작성한다.
        result = await writer.write_note(_write_command())
        written_content = result.path.read_text(encoding="utf-8")
        source_content = written_content.split("<!-- kb-provenance:", maxsplit=1)[0]

        # Then: 렌더링된 note와 provenance hash가 함께 남는다.
        assert source_content.startswith("---\ntitle: Today\n")
        assert "\n# Today\n\n## Summary\nBody text\n" in source_content
        assert result.source_hash == compute_sha256(source_content)
        assert result.content_hash == compute_sha256(written_content)
        assert result.commit_hash is None
        assert f"source_hash={result.source_hash}" in written_content
        assert "actor=tester" in written_content

    asyncio.run(exercise_writer())


def test_existing_note_수정은_현재_content_hash가_맞을_때만_허용된다(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        # Given: 이미 작성된 note와 그 note의 현재 content hash가 있다.
        writer = VaultWriteService(
            paths=VaultPaths(root=tmp_path / "vault"), queue=VaultWriteQueue(), actor="tester"
        )
        first_result = await writer.write_note(_write_command(body="## Summary\nInitial body"))

        # When / Then: if_hash가 없거나 오래된 값이면 수정이 거부된다.
        with pytest.raises(WriteConflictError, match="if_hash is required"):
            await writer.write_note(_write_command(body="## Summary\nUpdate without hash"))

        with pytest.raises(WriteConflictError, match="stale if_hash"):
            await writer.write_note(_write_command(body="## Summary\nStale update", if_hash="bad"))

        with pytest.raises(ValueError, match="created must not be provided"):
            await writer.write_note(
                _write_command(
                    body="## Summary\nCreated mutation",
                    if_hash=first_result.content_hash,
                )
            )

        # When: 현재 content hash로 note를 수정한다.
        updated_result = await writer.write_note(
            _write_command(
                body="## Summary\nFresh update",
                created=None,
                if_hash=first_result.content_hash,
            )
        )

        # Then: stale overwrite 없이 새 본문과 hash가 기록된다.
        assert updated_result.source_hash
        assert "Fresh update" in updated_result.path.read_text(encoding="utf-8")

    asyncio.run(exercise_writer())


def test_새_note_작성은_created를_요구한다(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        # Given: 빈 vault를 바라보는 writer가 있다.
        writer = VaultWriteService(
            paths=VaultPaths(root=tmp_path / "vault"), queue=VaultWriteQueue(), actor="tester"
        )

        # When / Then: 새 note 생성에서 created를 생략하면 거부된다.
        with pytest.raises(ValueError, match="created is required"):
            await writer.write_note(_write_command(created=None))

    asyncio.run(exercise_writer())


def test_write_command는_path와_type_불일치와_full_markdown_body를_거부한다() -> None:
    # When / Then: 폴더와 type이 맞지 않거나 body가 full markdown이면 command 검증에서 거부된다.
    with pytest.raises(ValidationError, match="type 'entity' is not allowed"):
        WriteNoteCommand(
            note_path="concepts/bad.md",
            title="Bad",
            type="entity",
            tags=("agent-memory",),
            sources=("raw/articles/source.md",),
            body="## Summary\nBody",
            created=datetime(2026, 6, 12, 9, 30, 45, tzinfo=UTC),
            updated=datetime(2026, 6, 12, 10, 31, 46, tzinfo=UTC),
        )

    with pytest.raises(ValidationError, match="YAML frontmatter"):
        _write_command(body="---\ntitle: Bad\n---\n# Bad")


@pytest.mark.parametrize(
    ("created", "updated", "error"),
    [
        (date(2026, 6, 12), datetime(2026, 6, 12, 10, 31, 46, tzinfo=UTC), "include time"),
        (
            "2026-06-12T09:30",
            "2026-06-12T10:31:46Z",
            "YYYY-MM-DDTHH:MM:SSZ",
        ),
        (
            "2026-06-12T09:30:45",
            "2026-06-12T10:31:46Z",
            "YYYY-MM-DDTHH:MM:SSZ",
        ),
        (
            "2026-06-12T18:30:45+09:00",
            "2026-06-12T10:31:46Z",
            "YYYY-MM-DDTHH:MM:SSZ",
        ),
        (
            datetime(2026, 6, 12, 9, 30, 45),
            datetime(2026, 6, 12, 10, 31, 46, tzinfo=UTC),
            "UTC timezone",
        ),
        (
            datetime(2026, 6, 12, 18, 30, 45, tzinfo=timezone(timedelta(hours=9))),
            datetime(2026, 6, 12, 10, 31, 46, tzinfo=UTC),
            "UTC timezone",
        ),
        (
            datetime(2026, 6, 12, 9, 30, 45, 123, tzinfo=UTC),
            datetime(2026, 6, 12, 10, 31, 46, tzinfo=UTC),
            "sub-second precision",
        ),
    ],
)
def test_write_command는_created_updated의_초단위_UTC_Z_datetime을_요구한다(
    created: Any,
    updated: Any,
    error: str,
) -> None:
    # When / Then: date-only, Z 없는 값, offset, sub-second timestamp는 거부된다.
    with pytest.raises(ValidationError, match=error):
        WriteNoteCommand(
            note_path="concepts/today.md",
            title="Today",
            type="concept",
            tags=("agent-memory",),
            sources=("raw/articles/source.md",),
            body="## Summary\nBody text",
            created=created,
            updated=updated,
        )


@pytest.mark.parametrize(
    ("created", "updated"),
    [
        ("2026-06-12T09:30:45Z", "2026-06-12T10:31:46Z"),
        (
            datetime(2026, 6, 12, 9, 30, 45, tzinfo=UTC),
            datetime(2026, 6, 12, 10, 31, 46, tzinfo=UTC),
        ),
    ],
)
def test_write_command는_created_updated를_UTC_Z_datetime으로_정규화한다(
    created: Any,
    updated: Any,
) -> None:
    # When: UTC Z 문자열 또는 UTC-aware datetime으로 command를 만든다.
    command = WriteNoteCommand(
        note_path="concepts/today.md",
        title="Today",
        type="concept",
        tags=("agent-memory",),
        sources=("raw/articles/source.md",),
        body="## Summary\nBody text",
        created=created,
        updated=updated,
    )

    # Then: 두 timestamp 모두 UTC tz-aware로 정규화되어 혼합 awareness 비교가 발생하지 않는다.
    assert command.created is not None
    assert command.created.tzinfo == UTC
    assert command.updated.tzinfo == UTC
    assert command.created == datetime(2026, 6, 12, 9, 30, 45, tzinfo=UTC)
    assert command.updated == datetime(2026, 6, 12, 10, 31, 46, tzinfo=UTC)


@pytest.mark.parametrize("line_separator", ["\n", "\r", "\r\n", "\u2028"])
def test_write_command는_title의_line_separator를_거부한다(line_separator: str) -> None:
    # When / Then: YAML frontmatter에 새 줄을 만들 수 있는 모든 line separator는 title에서 거부된다.
    with pytest.raises(ValidationError, match="title must be a single line"):
        _write_command(title=f"Safe{line_separator}contested: true")


def test_write_command는_tags와_sources의_line_separator를_거부한다() -> None:
    # When / Then: tag/source list 값도 렌더링 전 단일 라인 문자열이어야 한다.
    with pytest.raises(ValidationError, match="list values must be single-line"):
        _write_command(tags=("safe\rcontested: true",))

    with pytest.raises(ValidationError, match="list values must be single-line"):
        _write_command(sources=("raw/articles/source.md\rcontested: true",))


@pytest.mark.parametrize(
    ("note_path", "note_type"),
    [
        ("entities/../concepts/bad.md", "entity"),
        ("raw/../index.md", "raw"),
    ],
)
def test_write_command는_parent_segment로_path_type_검증을_우회하지_못한다(
    note_path: str,
    note_type: WikiNoteType,
) -> None:
    # When / Then: writer가 resolve할 위치와 command의 type 검증 대상이
    # 달라질 수 있는 path는 거부된다.
    with pytest.raises(ValidationError, match="parent directory segments"):
        _write_command(note_path=note_path, note_type=note_type)


def test_note_작성은_log와_index를_자동으로_쌓는다(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        # Given: 새 vault를 바라보는 writer가 있다.
        vault = tmp_path / "vault"
        writer = VaultWriteService(
            paths=VaultPaths(root=vault), queue=VaultWriteQueue(), actor="tester"
        )

        # When: concept note 하나를 작성한다.
        await writer.write_note(_write_command(note_path="concepts/today.md", title="Today"))

        # Then: log.md와 index.md가 자동 생성되고 각각 유효한 provenance 1개를 가진다.
        log = (vault / "log.md").read_text(encoding="utf-8")
        index = (vault / "index.md").read_text(encoding="utf-8")
        assert "## [2026-06-12] create | concepts/today" in log
        assert "- Created: `concepts/today.md` — Today" in log  # summary 없으면 title fallback
        assert "## Concepts" in index
        assert "- [[concepts/today|Today]]" in index
        assert log.count("<!-- kb-provenance:") == 1
        assert index.count("<!-- kb-provenance:") == 1

    asyncio.run(exercise_writer())


def test_summary는_log와_index_설명으로_쓰인다(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        # Given: 새 vault writer가 있다.
        vault = tmp_path / "vault"
        writer = VaultWriteService(
            paths=VaultPaths(root=vault), queue=VaultWriteQueue(), actor="tester"
        )

        # When: summary를 함께 넘겨 note를 작성한다.
        await writer.write_note(
            _write_command(note_path="concepts/x.md", title="X Title", summary="짧은 설명")
        )

        # Then: summary가 log bullet과 index 설명에 모두 반영된다.
        assert "- Created: `concepts/x.md` — 짧은 설명" in (vault / "log.md").read_text(
            encoding="utf-8"
        )
        assert "- [[concepts/x|X Title]] — 짧은 설명" in (vault / "index.md").read_text(
            encoding="utf-8"
        )

    asyncio.run(exercise_writer())


def test_note_수정은_log를_추가하고_index를_제자리_갱신한다(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        # Given: 이미 작성되어 log/index에 등재된 note가 있다.
        vault = tmp_path / "vault"
        writer = VaultWriteService(
            paths=VaultPaths(root=vault), queue=VaultWriteQueue(), actor="tester"
        )
        first = await writer.write_note(
            _write_command(note_path="concepts/x.md", title="X", summary="first")
        )

        # When: 같은 note를 현재 hash로 수정한다.
        await writer.write_note(
            _write_command(
                note_path="concepts/x.md",
                title="X",
                summary="second",
                created=None,
                if_hash=first.content_hash,
            )
        )

        # Then: log는 update entry가 위에 추가되고 index는 한 줄로 제자리 갱신된다.
        log = (vault / "log.md").read_text(encoding="utf-8")
        index = (vault / "index.md").read_text(encoding="utf-8")
        assert log.index("update | concepts/x") < log.index("create | concepts/x")
        assert "- Updated: `concepts/x.md` — second" in log
        assert index.count("[[concepts/x|") == 1
        assert "- [[concepts/x|X]] — second" in index
        assert "first" not in index

    asyncio.run(exercise_writer())


def test_summary_없는_수정은_기존_index_설명을_보존한다(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        # Given: summary와 함께 작성되어 index에 설명이 등재된 note가 있다.
        vault = tmp_path / "vault"
        writer = VaultWriteService(
            paths=VaultPaths(root=vault), queue=VaultWriteQueue(), actor="tester"
        )
        first = await writer.write_note(
            _write_command(note_path="concepts/x.md", title="X", summary="중요한 한 줄 설명")
        )

        # When: kb_read_note -> kb_write_note 흐름처럼 summary 없이 본문만 수정한다.
        await writer.write_note(
            _write_command(
                note_path="concepts/x.md",
                title="X",
                body="## Summary\nrevised body",
                summary=None,
                created=None,
                if_hash=first.content_hash,
            )
        )

        # Then: index 설명이 지워지지 않고 그대로 보존된다(중복 없음).
        index = (vault / "index.md").read_text(encoding="utf-8")
        assert "- [[concepts/x|X]] — 중요한 한 줄 설명" in index
        assert index.count("[[concepts/x|") == 1

    asyncio.run(exercise_writer())


def test_root_운영파일_작성은_log_index를_만들지_않는다(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        # Given: 새 vault writer가 있다.
        vault = tmp_path / "vault"
        writer = VaultWriteService(
            paths=VaultPaths(root=vault), queue=VaultWriteQueue(), actor="tester"
        )

        # When: 운영 파일(SCHEMA.md)을 직접 작성한다.
        await writer.write_note(
            _write_command(note_path="SCHEMA.md", title="Wiki Schema", note_type="schema")
        )

        # Then: 자기 자신을 log/index에 쌓지 않아 두 파일이 생기지 않는다.
        assert (vault / "SCHEMA.md").exists()
        assert not (vault / "log.md").exists()
        assert not (vault / "index.md").exists()

    asyncio.run(exercise_writer())


def test_write_command는_summary의_줄바꿈과_빈값을_거부하고_공백을_정리한다() -> None:
    # When / Then: 여러 줄 summary는 frontmatter/log/index 줄을 깨뜨릴 수 있어 거부된다.
    with pytest.raises(ValidationError, match="summary must be a single line"):
        _write_command(summary="line1\nline2")

    # When / Then: 공백뿐인 summary는 거부된다.
    with pytest.raises(ValidationError, match="summary must not be empty"):
        _write_command(summary="   ")

    # When: 앞뒤 공백이 있는 summary를 넘기면 정리된 한 줄 값으로 저장된다.
    assert _write_command(summary="  trimmed summary  ").summary == "trimmed summary"
