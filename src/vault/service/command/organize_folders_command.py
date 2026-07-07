from pathlib import Path
from typing import Literal, TypeAlias

from pydantic import field_validator, model_validator

from common.model import FrozenModel

FolderOrganizationRoot: TypeAlias = Literal[
    "raw",
    "entities",
    "concepts",
    "comparisons",
    "queries",
]


class OrganizeFoldersCommand(FrozenModel):
    root_folder: FolderOrganizationRoot | None = None
    dry_run: bool = True
    confirm: str | None = None

    @field_validator("root_folder", mode="before")
    @classmethod
    def _normalize_root_folder(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _validate_contract(self) -> "OrganizeFoldersCommand":
        # Defense-in-depth: FolderOrganizationRoot already restricts root_folder to a
        # fixed Literal set, so this guard is unreachable today. It is kept so widening
        # the type later cannot silently reintroduce a path-traversal segment.
        if isinstance(self.root_folder, str) and ".." in Path(self.root_folder).parts:
            raise ValueError("root_folder must not contain parent directory segments")
        return self
