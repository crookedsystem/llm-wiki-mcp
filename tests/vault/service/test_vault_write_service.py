import asyncio
import base64
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from vault.component.write_queue import VaultWriteQueue
from vault.entity.vault_note import compute_sha256
from vault.entity.vault_path import VaultPaths
from vault.error.write_error import WriteConflictError
from vault.service.command.write_note_command import (
    WikiNoteType,
    WriteNoteAttachment,
    WriteNoteCommand,
)
from vault.service.vault_write_service import VaultWriteService


def _write_command(
    *,
    note_path: str = "concepts/today.md",
    title: str = "Today",
    note_type: WikiNoteType = "concept",
    tags: tuple[str, ...] = ("agent-memory",),
    sources: tuple[str, ...] = ("raw/articles/source.md",),
    body: str = "## Summary\nBody text",
    if_hash: str | None = None,
    attachments: tuple[WriteNoteAttachment, ...] = (),
) -> WriteNoteCommand:
    return WriteNoteCommand(
        note_path=note_path,
        title=title,
        type=note_type,
        tags=tags,
        sources=sources,
        body=body,
        created=datetime(2026, 6, 12, 9, 30, 45, tzinfo=UTC),
        updated=datetime(2026, 6, 12, 10, 31, 46, tzinfo=UTC),
        confidence="medium",
        contested=False,
        if_hash=if_hash,
        attachments=attachments,
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

        # When: 현재 content hash로 note를 수정한다.
        updated_result = await writer.write_note(
            _write_command(body="## Summary\nFresh update", if_hash=first_result.content_hash)
        )

        # Then: stale overwrite 없이 새 본문과 hash가 기록된다.
        assert updated_result.source_hash
        assert "Fresh update" in updated_result.path.read_text(encoding="utf-8")

    asyncio.run(exercise_writer())


def test_note_작성은_type별_감사_log를_자동_append한다(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        # Given: 새 vault에 concept note를 작성할 writer가 있다.
        writer = VaultWriteService(
            paths=VaultPaths(root=tmp_path / "vault"), queue=VaultWriteQueue(), actor="tester"
        )

        # When: 일반 note를 새로 작성한다.
        await writer.write_note(_write_command())

        # Then: log.md가 자동 생성되고 작성한 note type과 경로가 감사 로그에 남는다.
        log_content = (tmp_path / "vault" / "log.md").read_text(encoding="utf-8")
        assert "# Wiki Log" in log_content
        assert "> Actions: ingest, create, update, query, lint, archive, hook-sync" in log_content
        assert "## [2026-06-12] create | concepts/today.md" in log_content
        assert "- Wrote: concepts/today.md" in log_content
        assert "- Source: raw/articles/source.md" in log_content
        assert "- Actor:" not in log_content
        assert "operation=append_log" in log_content

    asyncio.run(exercise_writer())


def test_existing_note_수정은_감사_log에_update_entry를_append한다(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        # Given: 이미 작성된 note와 자동 생성된 log.md가 있다.
        writer = VaultWriteService(
            paths=VaultPaths(root=tmp_path / "vault"), queue=VaultWriteQueue(), actor="tester"
        )
        first_result = await writer.write_note(_write_command(body="## Summary\nInitial body"))
        log_path = tmp_path / "vault" / "log.md"
        original_log = log_path.read_text(encoding="utf-8")

        # When: 현재 content hash로 note를 수정한다.
        await writer.write_note(
            _write_command(body="## Summary\nFresh update", if_hash=first_result.content_hash)
        )

        # Then: 기존 로그 본문은 보존되고 update entry만 append된다.
        updated_log = log_path.read_text(encoding="utf-8")
        assert original_log.split("<!-- kb-provenance:", maxsplit=1)[0].rstrip() in updated_log
        assert "## [2026-06-12] update | concepts/today.md" in updated_log
        assert "- Updated: concepts/today.md" in updated_log

    asyncio.run(exercise_writer())


def test_existing_log_형식은_유지하고_새_entry만_append한다(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        # Given: 기존 log.md가 기존 Wrote/Updated/Source 형식으로 작성되어 있다.
        vault_root = tmp_path / "vault"
        (vault_root).mkdir(parents=True)
        existing_log = (
            "---\n"
            "title: Wiki Log\n"
            "created: 2026-06-11T09:30:45Z\n"
            "updated: 2026-06-11T10:31:46Z\n"
            "type: log\n"
            "tags:\n"
            "  - llm-wiki\n"
            "sources: []\n"
            "confidence: high\n"
            "contested: false\n"
            "---\n\n"
            "# Wiki Log\n\n"
            "> Format: `## [YYYY-MM-DD] action | subject`\n"
            "> Actions: ingest, create, update, query, lint, archive, hook-sync\n\n"
            "## [2026-06-11] create | concepts/existing.md\n"
            "- Wrote: concepts/existing.md\n"
            "- Updated: index.md\n"
            "- Source: raw/articles/existing.md\n"
        )
        source_hash = compute_sha256(existing_log)
        (vault_root / "log.md").write_text(
            f"{existing_log}"
            f"<!-- kb-provenance: source_hash={source_hash}; "
            "operation=write_note; actor=llm-wiki -->\n",
            encoding="utf-8",
        )
        writer = VaultWriteService(paths=VaultPaths(root=vault_root), queue=VaultWriteQueue())

        # When: 새 note를 작성해 log.md에 자동 감사 entry를 붙인다.
        await writer.write_note(_write_command())

        # Then: 기존 entry 형식은 사라지지 않고 새 entry도 같은 Source 중심 형식으로 붙는다.
        log_content = (vault_root / "log.md").read_text(encoding="utf-8")
        assert "## [2026-06-11] create | concepts/existing.md" in log_content
        assert "- Updated: index.md" in log_content
        assert "- Source: raw/articles/existing.md" in log_content
        assert "## [2026-06-12] create | concepts/today.md" in log_content
        assert "- Wrote: concepts/today.md" in log_content
        assert "- Source: raw/articles/source.md" in log_content
        assert "- Actor:" not in log_content

    asyncio.run(exercise_writer())


def test_plain_legacy_log도_structured_log로_마이그레이션하며_append한다(
    tmp_path: Path,
) -> None:
    async def exercise_writer() -> None:
        # Given: 이전 템플릿처럼 YAML frontmatter가 없는 plain log.md가 있다.
        vault_root = tmp_path / "vault"
        vault_root.mkdir(parents=True)
        (vault_root / "log.md").write_text(
            "# Wiki Log\n\n"
            "> Format: `## [YYYY-MM-DD] action | subject`\n"
            "> Actions: ingest, create, update, query, lint, archive, hook-sync\n\n"
            "## [2026-06-11] create | concepts/existing.md\n"
            "- Wrote: concepts/existing.md\n"
            "- Source: raw/articles/existing.md\n",
            encoding="utf-8",
        )
        writer = VaultWriteService(paths=VaultPaths(root=vault_root), queue=VaultWriteQueue())

        # When: 일반 note를 작성한다.
        result = await writer.write_note(_write_command())

        # Then: target note 작성이 실패하지 않고 log.md는 structured note로 마이그레이션된다.
        log_content = (vault_root / "log.md").read_text(encoding="utf-8")
        assert result.path.exists()
        assert log_content.startswith("---\ntitle: Wiki Log\n")
        assert "\n# Wiki Log\n\n" in log_content
        assert "## [2026-06-11] create | concepts/existing.md" in log_content
        assert "- Source: raw/articles/existing.md" in log_content
        assert "## [2026-06-12] create | concepts/today.md" in log_content
        assert "- Wrote: concepts/today.md" in log_content
        assert "- Source: raw/articles/source.md" in log_content
        assert "operation=append_log" in log_content

    asyncio.run(exercise_writer())


def test_log_md는_direct_write로_수정할_수_없다(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        # Given: append-only log writer가 있다.
        writer = VaultWriteService(
            paths=VaultPaths(root=tmp_path / "vault"), queue=VaultWriteQueue(), actor="tester"
        )

        # When / Then: log.md를 직접 쓰는 command는 거부된다.
        with pytest.raises(WriteConflictError, match="log.md is append-only"):
            await writer.write_note(
                _write_command(
                    note_path="log.md",
                    title="Wiki Log",
                    note_type="log",
                    tags=("llm-wiki",),
                    sources=(),
                    body="## [2026-06-12] create | concepts/manual",
                )
            )

    asyncio.run(exercise_writer())


def test_note_작성은_base64_attachment를_vault_file로_저장하고_링크를_추가한다(
    tmp_path: Path,
) -> None:
    async def exercise_writer() -> None:
        # Given: base64로 인코딩한 이미지 attachment가 포함된 command가 있다.
        writer = VaultWriteService(
            paths=VaultPaths(root=tmp_path / "vault"), queue=VaultWriteQueue(), actor="tester"
        )
        attachment = WriteNoteAttachment(
            path="raw/assets/chart.png",
            mime_type="image/png",
            data_base64=base64.b64encode(b"fake image bytes").decode("ascii"),
        )

        # When: note를 작성한다.
        result = await writer.write_note(
            _write_command(
                body=(
                    "## Summary\nBody text\n\n"
                    "차트는 ![chart.png](raw/assets/chart.png)에서 확인한다."
                ),
                attachments=(attachment,),
            )
        )

        # Then: attachment 파일이 vault 안에 생성되고 note 본문은 입력 흐름을 유지한다.
        attachment_path = tmp_path / "vault" / "raw" / "assets" / "chart.png"
        assert attachment_path.read_bytes() == b"fake image bytes"
        written_content = result.path.read_text(encoding="utf-8")
        assert "차트는 ![chart.png](raw/assets/chart.png)에서 확인한다." in written_content
        assert "## Attachments" not in written_content
        assert result.attachment_paths == (attachment_path.resolve(),)

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


def test_write_command는_unsafe_attachment_payload를_거부한다() -> None:
    # When / Then: vault 밖 경로, markdown note 경로, 잘못된 base64 payload는 거부된다.
    with pytest.raises(ValidationError, match="parent directory segments"):
        WriteNoteAttachment(path="../chart.png", mime_type="image/png", data_base64="Zm9v")

    with pytest.raises(ValidationError, match="must not be a markdown note"):
        WriteNoteAttachment(
            path="raw/assets/chart.md",
            mime_type="text/markdown",
            data_base64="Zm9v",
        )

    with pytest.raises(ValidationError, match="valid base64"):
        WriteNoteAttachment(path="raw/assets/chart.png", mime_type="image/png", data_base64="???")


def test_write_command는_body에서_참조하지_않는_attachment를_거부한다() -> None:
    attachment = WriteNoteAttachment(
        path="raw/assets/chart.png",
        mime_type="image/png",
        data_base64="Zm9v",
    )

    with pytest.raises(ValidationError, match="referenced in body"):
        _write_command(attachments=(attachment,))
