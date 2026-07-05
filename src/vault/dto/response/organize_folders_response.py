from typing_extensions import TypedDict

from vault.service.result.organize_folders_result import FolderMove, OrganizeFoldersResult


class FolderMoveResponse(TypedDict):
    old_path: str
    new_path: str
    reason: str


class OrganizeFoldersResponse(TypedDict):
    dry_run: bool
    applied: bool
    moves: list[FolderMoveResponse]
    created_folders: list[str]
    updated_paths: list[str]
    confirmation_phrase: str
    safety_notice: str


def organize_folders_response(result: OrganizeFoldersResult) -> OrganizeFoldersResponse:
    return {
        "dry_run": result.dry_run,
        "applied": result.applied,
        "moves": [_move_response(move) for move in result.moves],
        "created_folders": result.created_folders,
        "updated_paths": result.updated_paths,
        "confirmation_phrase": result.confirmation_phrase,
        "safety_notice": result.safety_notice,
    }


def _move_response(move: FolderMove) -> FolderMoveResponse:
    return {
        "old_path": move.old_path,
        "new_path": move.new_path,
        "reason": move.reason,
    }
