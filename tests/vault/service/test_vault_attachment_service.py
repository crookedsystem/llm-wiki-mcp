import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from vault.component.write_queue import VaultWriteQueue
from vault.entity.vault_note import compute_sha256
from vault.entity.vault_path import VaultPaths
from vault.error.write_error import WriteConflictError
from vault.service.command.insert_attachment_command import InsertAttachmentCommand
from vault.service.command.write_note_command import WriteNoteCommand
from vault.service.vault_attachment_service import VaultAttachmentService
from vault.service.vault_write_service import VaultWriteService


def _write_command() -> WriteNoteCommand:
    return WriteNoteCommand(
        note_path="concepts/today.md",
        title="Today",
        type="concept",
        tags=("agent-memory",),
        sources=("raw/articles/source.md",),
        body="## Summary\nBody text",
        created=datetime(2026, 6, 12, 9, 30, 45, tzinfo=UTC),
        updated=datetime(2026, 6, 12, 10, 31, 46, tzinfo=UTC),
        confidence="medium",
        contested=False,
    )


def test_attachment_service는_기존_note에_이미지_link를_partial_insert한다(
    tmp_path: Path,
) -> None:
    async def exercise_service() -> None:
        # Given: 먼저 생성된 note와 현재 content hash가 있다.
        paths = VaultPaths(root=tmp_path / "vault")
        queue = VaultWriteQueue()
        writer = VaultWriteService(paths=paths, queue=queue, actor="tester")
        attachment_service = VaultAttachmentService(paths=paths, queue=queue, actor="tester")
        write_result = await writer.write_note(_write_command())

        # When: attachment endpoint와 같은 command로 이미지 bytes를 partial insert한다.
        result = await attachment_service.insert_attachment(
            InsertAttachmentCommand(
                note_path="concepts/today.md",
                filename="chart.png",
                mime_type="image/png",
                content=b"fake image bytes",
                if_hash=write_result.content_hash,
                alt_text="chart",
            )
        )

        # Then: assets 아래에 파일이 저장되고 note에는 새 링크와 갱신된 provenance가 기록된다.
        attachment_path = tmp_path / "vault" / "raw" / "assets" / "concepts" / "today" / "chart.png"
        note_path = tmp_path / "vault" / "concepts" / "today.md"
        note_content = note_path.read_text(encoding="utf-8")
        assert attachment_path.read_bytes() == b"fake image bytes"
        assert "## Summary\nBody text" in note_content
        assert "## Attachments\n![chart](raw/assets/concepts/today/chart.png)" in note_content
        assert "operation=insert_attachment" in note_content
        assert result.attachment_path == attachment_path.resolve()
        assert result.attachment_link == "![chart](raw/assets/concepts/today/chart.png)"
        assert result.content_hash == compute_sha256(note_content)

    asyncio.run(exercise_service())


def test_attachment_service는_stale_hash와_unsafe_filename을_거부한다(tmp_path: Path) -> None:
    async def exercise_service() -> None:
        # Given: 먼저 생성된 note가 있다.
        paths = VaultPaths(root=tmp_path / "vault")
        queue = VaultWriteQueue()
        writer = VaultWriteService(paths=paths, queue=queue, actor="tester")
        attachment_service = VaultAttachmentService(paths=paths, queue=queue, actor="tester")
        await writer.write_note(_write_command())

        # When / Then: stale hash로는 partial insert를 거부한다.
        with pytest.raises(WriteConflictError, match="stale if_hash"):
            await attachment_service.insert_attachment(
                InsertAttachmentCommand(
                    note_path="concepts/today.md",
                    filename="chart.png",
                    mime_type="image/png",
                    content=b"fake image bytes",
                    if_hash="bad",
                )
            )

    asyncio.run(exercise_service())

    with pytest.raises(ValidationError, match="single safe file name"):
        InsertAttachmentCommand(
            note_path="concepts/today.md",
            filename="../chart.png",
            mime_type="image/png",
            content=b"fake image bytes",
            if_hash="hash",
        )

    with pytest.raises(ValidationError, match="image MIME type"):
        InsertAttachmentCommand(
            note_path="concepts/today.md",
            filename="chart.png",
            mime_type="application/pdf",
            content=b"fake image bytes",
            if_hash="hash",
        )
