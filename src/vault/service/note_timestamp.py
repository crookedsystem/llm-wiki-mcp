import re
from datetime import UTC, date, datetime
from typing import Annotated, Final, TypeAlias

from pydantic import AfterValidator, BeforeValidator, WithJsonSchema

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
_NOTE_TIMESTAMP_FIELD_NAME = "created and updated"


def validate_note_timestamp_input(value: object) -> object:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        raise ValueError(f"{_NOTE_TIMESTAMP_FIELD_NAME} must include time down to seconds")
    if isinstance(value, str) and not TimeHelper.is_utc_timestamp_z(value):
        raise ValueError(
            f"{_NOTE_TIMESTAMP_FIELD_NAME} must use UTC ISO datetime format with seconds "
            "and trailing Z (YYYY-MM-DDTHH:MM:SSZ)"
        )
    return value


def normalize_note_timestamp_to_utc(value: datetime) -> datetime:
    return TimeHelper.normalize_utc_timestamp(value, field_name=_NOTE_TIMESTAMP_FIELD_NAME)


def coerce_note_timestamp_to_utc(
    value: str,
    *,
    field_name: str = _NOTE_TIMESTAMP_FIELD_NAME,
) -> datetime:
    return _coerce_timestamp_to_utc(
        value,
        matcher=_NOTE_TIMESTAMP_ISO_SECONDS,
        field_name=field_name,
    )


def coerce_legacy_note_timestamp_to_utc(
    value: str,
    *,
    field_name: str = _NOTE_TIMESTAMP_FIELD_NAME,
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
    return TimeHelper.format_utc_timestamp(value, field_name=_NOTE_TIMESTAMP_FIELD_NAME)


NoteTimestamp: TypeAlias = Annotated[
    datetime,
    BeforeValidator(validate_note_timestamp_input),
    AfterValidator(normalize_note_timestamp_to_utc),
    WithJsonSchema(
        {
            "type": "string",
            "format": "date-time",
            "pattern": f"^{NOTE_TIMESTAMP_UTC_Z_PATTERN}$",
            "examples": ["2026-06-12T09:30:45Z"],
        }
    ),
]
