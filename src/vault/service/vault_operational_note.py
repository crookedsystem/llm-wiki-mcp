from common.model import FrozenModel
from vault.entity.vault_note import parse_note, strip_provenance_trailer

_UPDATED_FIELD_PREFIX = "updated:"


class OperationalNote(FrozenModel):
    """An editable view of a vault operational file (``log.md`` / ``index.md``).

    ``frontmatter`` is the text between the ``---`` fences (without the fences;
    empty when the file has none). ``body`` is everything after the closing
    fence with the provenance trailer removed. ``parse`` and ``render`` are
    inverses, so a transform is ``parse -> edit body -> render`` and the write
    service then re-attaches a fresh provenance trailer.
    """

    frontmatter: str
    body: str

    @classmethod
    def parse(cls, content: str) -> "OperationalNote":
        parsed = parse_note(strip_provenance_trailer(content))
        return cls(frontmatter=parsed.frontmatter or "", body=parsed.body)

    def render(self) -> str:
        if not self.frontmatter:
            return self.body
        return f"---\n{self.frontmatter}\n---\n{self.body}"

    def with_body(self, body: str) -> "OperationalNote":
        return OperationalNote(frontmatter=self.frontmatter, body=body)

    def with_updated(self, timestamp: str) -> "OperationalNote":
        return OperationalNote(
            frontmatter=_replace_updated_line(self.frontmatter, timestamp),
            body=self.body,
        )


def _replace_updated_line(frontmatter: str, timestamp: str) -> str:
    lines = frontmatter.split("\n")
    for index, line in enumerate(lines):
        if line.startswith(_UPDATED_FIELD_PREFIX):
            lines[index] = f'updated: "{timestamp}"'
            return "\n".join(lines)
    return frontmatter


def strip_trailing_blank_lines(lines: list[str]) -> list[str]:
    end = len(lines)
    while end > 0 and not lines[end - 1].strip():
        end -= 1
    return lines[:end]


def strip_leading_blank_lines(lines: list[str]) -> list[str]:
    start = 0
    while start < len(lines) and not lines[start].strip():
        start += 1
    return lines[start:]


def join_body(lines: list[str]) -> str:
    """Join body lines back into text with exactly one trailing newline."""
    return "\n".join(strip_trailing_blank_lines(lines)) + "\n"
