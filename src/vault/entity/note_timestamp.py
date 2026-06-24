import re
from datetime import UTC, datetime
from typing import Final

from common.helper.time_helper import TimeHelper

NOTE_TIMESTAMP_UTC_Z_PATTERN = TimeHelper.UTC_TIMESTAMP_Z_PATTERN
NOTE_TIMESTAMP_ISO_SECONDS_PATTERN: Final[str] = (
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})?"
)
NOTE_TIMESTAMP_LEGACY_ISO_SECONDS_PATTERN: Final[str] = (
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})?"
)
_NOTE_TIMESTAMP_ISO_SECONDS: Final[re.Pattern[str]] = re.compile(NOTE_TIMESTAMP_ISO_SECONDS_PATTERN)
_NOTE_TIMESTAMP_LEGACY_ISO_SECONDS: Final[re.Pattern[str]] = re.compile(
    NOTE_TIMESTAMP_LEGACY_ISO_SECONDS_PATTERN
)
NOTE_TIMESTAMP_FIELD_NAME = "created and updated"


def normalize_note_timestamp_to_utc(value: datetime) -> datetime:
    return TimeHelper.normalize_utc_timestamp(value, field_name=NOTE_TIMESTAMP_FIELD_NAME)


def coerce_note_timestamp_to_utc(
    value: str,
    *,
    field_name: str = NOTE_TIMESTAMP_FIELD_NAME,
) -> datetime:
    return _coerce_timestamp_to_utc(
        value,
        matcher=_NOTE_TIMESTAMP_ISO_SECONDS,
        field_name=field_name,
    )


def coerce_legacy_note_timestamp_to_utc(
    value: str,
    *,
    field_name: str = NOTE_TIMESTAMP_FIELD_NAME,
) -> datetime:
    normalized_value = value.replace(" ", "T", 1)
    return _coerce_timestamp_to_utc(
        normalized_value,
        matcher=_NOTE_TIMESTAMP_LEGACY_ISO_SECONDS,
        field_name=field_name,
    )


def is_note_timestamp_utc_z(value: str) -> bool:
    return TimeHelper.is_utc_timestamp_z(value)


def _coerce_timestamp_to_utc(
    value: str,
    *,
    matcher: re.Pattern[str],
    field_name: str,
) -> datetime:
    if not matcher.fullmatch(value):
        raise ValueError(
            f"{field_name} must use ISO datetime format with seconds "
            "(YYYY-MM-DDTHH:MM:SSZ or explicit offset)"
        )
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def format_note_timestamp(value: datetime) -> str:
    return TimeHelper.format_utc_timestamp(value, field_name=NOTE_TIMESTAMP_FIELD_NAME)
