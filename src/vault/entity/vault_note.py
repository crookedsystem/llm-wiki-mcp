from hashlib import sha256
from typing import Final

from common.model import FrozenModel

FRONTMATTER_DELIMITER: Final = "---"
PROVENANCE_PREFIX: Final = "<!-- kb-provenance:"


class ParsedNote(FrozenModel):
    """Markdown note split into optional raw frontmatter and body text."""

    frontmatter: str | None
    body: str


def compute_sha256(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def parse_note(raw_note: str) -> ParsedNote:
    if not raw_note.startswith(f"{FRONTMATTER_DELIMITER}\n"):
        return ParsedNote(frontmatter=None, body=raw_note)

    closing_delimiter = raw_note.find(f"\n{FRONTMATTER_DELIMITER}\n", 4)
    if closing_delimiter == -1:
        return ParsedNote(frontmatter=None, body=raw_note)

    frontmatter = raw_note[4:closing_delimiter]
    body_start = closing_delimiter + len(f"\n{FRONTMATTER_DELIMITER}\n")
    return ParsedNote(frontmatter=frontmatter, body=raw_note[body_start:])


def append_provenance_trailer(
    content: str,
    *,
    source_hash: str,
    operation: str,
    actor: str,
) -> str:
    content_with_newline = content if content.endswith("\n") else f"{content}\n"
    trailer = (
        f"{PROVENANCE_PREFIX} source_hash={source_hash}; operation={operation}; actor={actor} -->\n"
    )
    return f"{content_with_newline}{trailer}"


def strip_provenance_trailer(content: str) -> str:
    """Return *content* without its trailing kb-provenance comment, if present.

    The trailer is always the last thing in a written note, so removing from the
    final ``PROVENANCE_PREFIX`` onward yields the original source content. Note
    bodies are validated to never contain the prefix, so this never cuts a body.
    """
    marker_index = content.rfind(PROVENANCE_PREFIX)
    if marker_index == -1:
        return content
    return content[:marker_index]
