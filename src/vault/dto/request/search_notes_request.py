from common.model import FrozenModel
from vault.service.command.search_notes_command import SearchNotesCommand


class SearchNotesRequest(FrozenModel):
    query: str
    limit: int = 10
    path_prefix: str | None = None

    def to_command(self) -> SearchNotesCommand:
        return SearchNotesCommand(
            query=self.query,
            limit=self.limit,
            path_prefix=self.path_prefix,
        )
