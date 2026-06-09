from pydantic import Field

from common.model import FrozenModel


class LineMatch(FrozenModel):
    line: int
    snippet: str


class NoteSearchResult(FrozenModel):
    path: str
    title: str | None
    page_type: str | None
    tags: list[str]
    score: float
    content_hash: str
    matches: list[LineMatch]


class SearchNotesResult(FrozenModel):
    query: str
    count: int
    results: list[NoteSearchResult]


class FrontmatterMetadata(FrozenModel):
    title: str | None = None
    page_type: str | None = None
    tags: list[str] = Field(default_factory=list)


class NoteMetadata(FrozenModel):
    title: str | None
    page_type: str | None
    tags: list[str]
    headings: list[str]
