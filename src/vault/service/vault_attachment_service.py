from pathlib import Path

from pydantic import Field

from common.model import FrozenModel
from vault.component.write_queue import VaultWriteQueue
from vault.entity.vault_note import (
    PROVENANCE_PREFIX,
    append_provenance_trailer,
    compute_sha256,
)
from vault.entity.vault_path import VaultPaths
from vault.error.write_error import WriteConflictError
from vault.service.command.insert_attachment_command import InsertAttachmentCommand
from vault.service.result.insert_attachment_result import InsertAttachmentResult


class _FileSnapshot(FrozenModel):
    path: Path
    content: bytes | None


class VaultAttachmentService(FrozenModel):
    paths: VaultPaths
    queue: VaultWriteQueue
    actor: str = "llm-wiki"
    asset_root: str = Field(default="raw/assets")

    async def insert_attachment(self, command: InsertAttachmentCommand) -> InsertAttachmentResult:
        async def operation() -> InsertAttachmentResult:
            return self._insert_attachment(command)

        return await self.queue.run(operation)

    def _insert_attachment(self, command: InsertAttachmentCommand) -> InsertAttachmentResult:
        note_path = self.paths.resolve_note_path(command.note_path)
        if not note_path.exists():
            raise FileNotFoundError(f"note not found: {Path(command.note_path).as_posix()}")

        current_content = note_path.read_text(encoding="utf-8")
        if compute_sha256(current_content) != command.if_hash:
            raise WriteConflictError("stale if_hash does not match current note content")

        attachment_relative_path = self._attachment_relative_path(command)
        attachment_path = self.paths.resolve_file_path(attachment_relative_path)
        snapshots = self._snapshot_paths([note_path, attachment_path])

        try:
            if attachment_path.exists() and attachment_path.read_bytes() != command.content:
                raise WriteConflictError(
                    f"attachment already exists: {attachment_relative_path.as_posix()}"
                )
            attachment_path.parent.mkdir(parents=True, exist_ok=True)
            attachment_path.write_bytes(command.content)

            content = _strip_provenance_trailer(current_content)
            link = self._markdown_image_link(command, attachment_relative_path)
            patched_content = _append_attachment_link(content, link)
            source_hash = compute_sha256(patched_content)
            final_content = append_provenance_trailer(
                patched_content,
                source_hash=source_hash,
                operation="insert_attachment",
                actor=self.actor,
            )
            note_path.write_text(final_content, encoding="utf-8")
            return InsertAttachmentResult(
                note_path=note_path,
                attachment_path=attachment_path,
                attachment_link=link,
                source_hash=source_hash,
                content_hash=compute_sha256(final_content),
            )
        except Exception:
            self._restore_snapshots(snapshots)
            raise

    def _attachment_relative_path(self, command: InsertAttachmentCommand) -> Path:
        note_stem = Path(command.note_path).with_suffix("")
        return Path(self.asset_root) / note_stem / command.filename

    def _markdown_image_link(self, command: InsertAttachmentCommand, relative_path: Path) -> str:
        alt_text = command.alt_text or command.filename
        return f"![{alt_text}]({relative_path.as_posix()})"

    def _snapshot_paths(self, paths: list[Path]) -> list[_FileSnapshot]:
        snapshots: list[_FileSnapshot] = []
        seen_paths: set[Path] = set()
        for path in paths:
            if path in seen_paths:
                continue
            seen_paths.add(path)
            content = path.read_bytes() if path.exists() else None
            snapshots.append(_FileSnapshot(path=path, content=content))
        return snapshots

    def _restore_snapshots(self, snapshots: list[_FileSnapshot]) -> None:
        for snapshot in snapshots:
            if snapshot.content is None:
                snapshot.path.unlink(missing_ok=True)
                continue
            snapshot.path.parent.mkdir(parents=True, exist_ok=True)
            snapshot.path.write_bytes(snapshot.content)


def _strip_provenance_trailer(content: str) -> str:
    marker_index = content.rfind(PROVENANCE_PREFIX)
    if marker_index == -1:
        return content
    return content[:marker_index].rstrip("\n")


def _append_attachment_link(content: str, link: str) -> str:
    content_without_trailing_newline = content.rstrip("\n")
    if "\n## Attachments\n" in f"\n{content_without_trailing_newline}\n":
        return f"{content_without_trailing_newline}\n{link}\n"
    return f"{content_without_trailing_newline}\n\n## Attachments\n{link}\n"
