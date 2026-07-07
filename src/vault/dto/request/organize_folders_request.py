from common.model import FrozenModel
from vault.service.command.organize_folders_command import (
    FolderOrganizationRoot,
    OrganizeFoldersCommand,
)


class OrganizeFoldersRequest(FrozenModel):
    root_folder: FolderOrganizationRoot | None = None
    dry_run: bool = True
    confirm: str | None = None

    def to_command(self) -> OrganizeFoldersCommand:
        return OrganizeFoldersCommand(
            root_folder=self.root_folder,
            dry_run=self.dry_run,
            confirm=self.confirm,
        )
