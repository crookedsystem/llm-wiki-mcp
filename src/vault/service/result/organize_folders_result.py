from common.model import FrozenModel


class FolderMove(FrozenModel):
    old_path: str
    new_path: str
    reason: str


class OrganizeFoldersResult(FrozenModel):
    dry_run: bool
    applied: bool
    moves: list[FolderMove]
    created_folders: list[str]
    updated_paths: list[str]
    confirmation_phrase: str
    safety_notice: str
