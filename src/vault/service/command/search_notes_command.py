from common.model import FrozenModel


class SearchNotesCommand(FrozenModel):
    query: str
    limit: int = 10
    path_prefix: str | None = None
