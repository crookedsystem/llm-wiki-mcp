from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from vault.dto.request.write_note_request import WriteNoteRequest
from vault.service.command.write_note_command import WikiNoteType


def _write_request(
    *,
    note_path: str = "concepts/today.md",
    title: str = "Today",
    note_type: WikiNoteType = "concept",
    tags: list[str] | None = None,
    sources: list[str] | None = None,
    body: str = "## Summary\nBody text",
    created: Any = datetime(2026, 6, 12, 9, 30, 45, tzinfo=UTC),
    updated: Any = datetime(2026, 6, 12, 10, 31, 46, tzinfo=UTC),
    if_hash: str | None = None,
) -> WriteNoteRequest:
    return WriteNoteRequest(
        note_path=note_path,
        title=title,
        type=note_type,
        tags=tags or ["agent-memory"],
        sources=sources or ["raw/articles/source.md"],
        body=body,
        created=created,
        updated=updated,
        if_hash=if_hash,
    )


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
            "2026-06-12 09:30:45",
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
def test_write_note_request는_created_updated의_초단위_UTC_Z_datetime을_요구한다(
    created: Any,
    updated: Any,
    error: str,
) -> None:
    # When / Then: MCP/DTO boundary에서 date-only, Z 없는 값, offset, 공백 구분,
    # sub-second timestamp는 service command 생성 전에 거부된다.
    with pytest.raises(ValidationError, match=error):
        _write_request(created=created, updated=updated)


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
def test_write_note_request는_created_updated를_UTC_datetime으로_정규화한다(
    created: Any,
    updated: Any,
) -> None:
    # When: UTC Z 문자열 또는 UTC-aware datetime으로 DTO를 만든다.
    request = _write_request(created=created, updated=updated)
    command = request.to_command()

    # Then: DTO에서 두 timestamp가 UTC tz-aware datetime으로 정규화된 뒤 command로 전달된다.
    assert request.created is not None
    assert request.created.tzinfo == UTC
    assert request.updated.tzinfo == UTC
    assert command.created == datetime(2026, 6, 12, 9, 30, 45, tzinfo=UTC)
    assert command.updated == datetime(2026, 6, 12, 10, 31, 46, tzinfo=UTC)
