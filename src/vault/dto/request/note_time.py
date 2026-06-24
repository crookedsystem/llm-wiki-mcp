from datetime import date, datetime
from typing import Annotated, TypeAlias

from pydantic import AfterValidator, BeforeValidator, WithJsonSchema

from common.helper.time_helper import TimeHelper
from vault.entity.note_time import (
    NOTE_TIME_FIELD_NAME,
    NOTE_TIME_UTC_Z_PATTERN,
    check_note_time_is_utc,
)


def validate_note_time_input(value: object) -> object:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        raise ValueError(f"{NOTE_TIME_FIELD_NAME} must include time down to seconds")
    if isinstance(value, str) and not TimeHelper.is_utc_timestamp_z(value):
        raise ValueError(
            f"{NOTE_TIME_FIELD_NAME} must use UTC ISO datetime format with seconds "
            "and trailing Z (YYYY-MM-DDTHH:MM:SSZ)"
        )
    return value


NoteTime: TypeAlias = Annotated[
    datetime,
    BeforeValidator(validate_note_time_input),
    AfterValidator(check_note_time_is_utc),
    WithJsonSchema(
        {
            "type": "string",
            "format": "date-time",
            "pattern": f"^{NOTE_TIME_UTC_Z_PATTERN}$",
            "examples": ["2026-06-12T09:30:45Z"],
        }
    ),
]
