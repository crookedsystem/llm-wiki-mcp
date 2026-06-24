import re
from datetime import UTC, datetime
from typing import Final

from common.helper.time_helper import TimeHelper

NOTE_TIME_UTC_Z_PATTERN = TimeHelper.UTC_TIMESTAMP_Z_PATTERN
NOTE_TIME_TEXT_PATTERN: Final[str] = (
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})?"
)
OLD_NOTE_TIME_TEXT_PATTERN: Final[str] = (
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})?"
)
_NOTE_TIME_TEXT: Final[re.Pattern[str]] = re.compile(NOTE_TIME_TEXT_PATTERN)
_OLD_NOTE_TIME_TEXT: Final[re.Pattern[str]] = re.compile(
    OLD_NOTE_TIME_TEXT_PATTERN
)
NOTE_TIME_FIELD_NAME = "created and updated"


def check_note_time_is_utc(value: datetime) -> datetime:
    return TimeHelper.normalize_utc_timestamp(value, field_name=NOTE_TIME_FIELD_NAME)


def parse_note_time(
    text: str,
    *,
    field_name: str = NOTE_TIME_FIELD_NAME,
) -> datetime:
    return _parse_note_time_text(
        text,
        pattern=_NOTE_TIME_TEXT,
        field_name=field_name,
    )


def parse_old_note_time(
    text: str,
    *,
    field_name: str = NOTE_TIME_FIELD_NAME,
) -> datetime:
    fixed_text = text.replace(" ", "T", 1)
    return _parse_note_time_text(
        fixed_text,
        pattern=_OLD_NOTE_TIME_TEXT,
        field_name=field_name,
    )


def is_utc_note_time_text(value: str) -> bool:
    return TimeHelper.is_utc_timestamp_z(value)


def _parse_note_time_text(
    text: str,
    *,
    pattern: re.Pattern[str],
    field_name: str,
) -> datetime:
    if not pattern.fullmatch(text):
        raise ValueError(
            f"{field_name} must use ISO datetime format with seconds "
            "(YYYY-MM-DDTHH:MM:SSZ or explicit offset)"
        )
    time_value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if time_value.tzinfo is None:
        time_value = time_value.replace(tzinfo=UTC)
    return time_value.astimezone(UTC)


def format_note_time(value: datetime) -> str:
    return TimeHelper.format_utc_timestamp(value, field_name=NOTE_TIME_FIELD_NAME)
