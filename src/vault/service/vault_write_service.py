from pathlib import Path

from pydantic import Field

from common.model import FrozenModel
from vault.component.write_queue import VaultWriteQueue
from vault.entity.vault_note import (
    append_provenance_trailer,
    compute_sha256,
)
from vault.entity.vault_path import VaultPaths
from vault.error.write_error import WriteConflictError
from vault.infrastructure.repository.git_repository import GitRepository
from vault.service.command.read_note_command import ReadNoteCommand
from vault.service.command.write_note_command import WriteNoteCommand
from vault.service.result.write_note_result import WriteNoteResult
from vault.service.vault_note_renderer import VaultNoteRenderer
from vault.service.vault_read_service import VaultReadService

_APPEND_ONLY_LOG_PATH = Path("log.md")


class _FileSnapshot(FrozenModel):
    path: Path
    content: bytes | None


class VaultWriteService(FrozenModel):
    paths: VaultPaths
    queue: VaultWriteQueue
    actor: str = "llm-wiki"
    git_repository: GitRepository | None = None
    note_renderer: VaultNoteRenderer = Field(default_factory=VaultNoteRenderer)

    async def write_note(self, command: WriteNoteCommand) -> WriteNoteResult:
        async def operation() -> WriteNoteResult:
            return await self._write_note(command)

        return await self.queue.run(operation)

    async def batch_write_notes(
        self,
        commands: list[WriteNoteCommand],
        *,
        atomic: bool = True,
    ) -> list[WriteNoteResult]:
        async def operation() -> list[WriteNoteResult]:
            return await self._batch_write_notes(commands, atomic=atomic)

        return await self.queue.run(operation)

    async def _batch_write_notes(
        self,
        commands: list[WriteNoteCommand],
        *,
        atomic: bool,
    ) -> list[WriteNoteResult]:
        snapshots = self._snapshot_commands(commands) if atomic else []
        try:
            return [await self._write_note(command) for command in commands]
        except Exception:
            if atomic:
                self._restore_snapshots(snapshots)
            raise

    async def _write_note(
        self,
        command: WriteNoteCommand,
        *,
        allow_log_write: bool = False,
        append_audit_log: bool = True,
        commit_written: bool = True,
        operation: str = "write_note",
    ) -> WriteNoteResult:
        resolved_path = self.paths.resolve_note_path(command.note_path)
        relative_path = resolved_path.relative_to(self.paths.root.resolve())
        if relative_path == _APPEND_ONLY_LOG_PATH and not allow_log_write:
            raise WriteConflictError(
                "log.md is append-only; write the target note and let the writer append "
                "audit entries"
            )

        action = "update" if resolved_path.exists() else "create"
        self._check_if_hash(resolved_path, command.if_hash)
        attachment_paths = self._resolve_attachment_paths(command)
        audit_log_command = (
            self._audit_log_command(command, relative_path=relative_path, action=action)
            if append_audit_log
            else None
        )
        audit_log_paths = (
            [self.paths.resolve_note_path(_APPEND_ONLY_LOG_PATH)]
            if audit_log_command is not None
            else []
        )
        snapshots = self._snapshot_paths([resolved_path, *attachment_paths, *audit_log_paths])

        try:
            content = self.note_renderer.render(command)
            source_hash = compute_sha256(content)
            final_content = append_provenance_trailer(
                content,
                source_hash=source_hash,
                operation=operation,
                actor=self.actor,
            )
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
            resolved_path.write_text(final_content, encoding="utf-8")
            self._write_attachments(command, attachment_paths)
            if audit_log_command is not None:
                await self._write_note(
                    audit_log_command,
                    allow_log_write=True,
                    append_audit_log=False,
                    commit_written=False,
                    operation="append_log",
                )
            commit_paths = [resolved_path, *attachment_paths, *audit_log_paths]
            commit_hash = self._commit_written_paths(commit_paths) if commit_written else None
            return WriteNoteResult(
                path=resolved_path,
                source_hash=source_hash,
                content_hash=compute_sha256(final_content),
                commit_hash=commit_hash,
                attachment_paths=tuple(attachment_paths),
            )
        except Exception:
            self._restore_snapshots(snapshots)
            raise

    def _commit_written_path(self, resolved_path: Path) -> str | None:
        return self._commit_written_paths([resolved_path])

    def _commit_written_paths(self, resolved_paths: list[Path]) -> str | None:
        if self.git_repository is None:
            return None
        relative_paths = [
            resolved_path.relative_to(self.paths.root.resolve()).as_posix()
            for resolved_path in resolved_paths
        ]
        return self.git_repository.commit_paths(
            resolved_paths,
            f"Update {', '.join(relative_paths)}",
        )

    def _snapshot_commands(self, commands: list[WriteNoteCommand]) -> list[_FileSnapshot]:
        paths: list[Path] = []
        for command in commands:
            paths.extend(self._snapshot_paths_for_command(command))
        return self._snapshot_paths(paths)

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

    def _snapshot_paths_for_command(self, command: WriteNoteCommand) -> list[Path]:
        resolved_path = self.paths.resolve_note_path(command.note_path)
        paths = [resolved_path, *self._resolve_attachment_paths(command)]
        relative_path = resolved_path.relative_to(self.paths.root.resolve())
        if relative_path != _APPEND_ONLY_LOG_PATH:
            paths.append(self.paths.resolve_note_path(_APPEND_ONLY_LOG_PATH))
        return paths

    def _audit_log_command(
        self,
        source_command: WriteNoteCommand,
        *,
        relative_path: Path,
        action: str,
    ) -> WriteNoteCommand:
        log_path = self.paths.resolve_note_path(_APPEND_ONLY_LOG_PATH)
        entry = self._audit_log_entry(source_command, relative_path=relative_path, action=action)

        if log_path.exists():
            current_log = VaultReadService(paths=self.paths).read_note(
                ReadNoteCommand(note_path=_APPEND_ONLY_LOG_PATH)
            )
            body = f"{current_log.body.rstrip()}\n\n{entry}"
            return WriteNoteCommand(
                note_path=_APPEND_ONLY_LOG_PATH,
                title=current_log.title,
                type="log",
                tags=current_log.tags,
                sources=current_log.sources,
                body=body,
                created=current_log.created,
                updated=max(current_log.updated, source_command.updated),
                confidence=current_log.confidence,
                contested=current_log.contested,
                if_hash=current_log.content_hash,
            )

        return WriteNoteCommand(
            note_path=_APPEND_ONLY_LOG_PATH,
            title="Wiki Log",
            type="log",
            tags=("llm-wiki", "audit-log"),
            sources=(),
            body=f"{self._initial_log_body()}\n\n{entry}",
            created=source_command.updated,
            updated=source_command.updated,
            confidence="high",
            contested=False,
        )

    def _audit_log_entry(
        self,
        source_command: WriteNoteCommand,
        *,
        relative_path: Path,
        action: str,
    ) -> str:
        day = source_command.updated.date().isoformat()
        path = relative_path.as_posix()
        action_line = "Wrote" if action == "create" else "Updated"
        lines = [
            f"## [{day}] {action} | {path}",
            f"- {action_line}: {path}",
        ]
        lines.extend(f"- Source: {source}" for source in source_command.sources)
        return "\n".join(lines)

    def _initial_log_body(self) -> str:
        return "\n".join(
            [
                "> Format: `## [YYYY-MM-DD] action | subject`",
                "> Actions: ingest, create, update, query, lint, archive, hook-sync",
            ]
        )

    def _restore_snapshots(self, snapshots: list[_FileSnapshot]) -> None:
        for snapshot in snapshots:
            if snapshot.content is None:
                snapshot.path.unlink(missing_ok=True)
                continue
            snapshot.path.parent.mkdir(parents=True, exist_ok=True)
            snapshot.path.write_bytes(snapshot.content)

    def _check_if_hash(self, resolved_path: Path, if_hash: str | None) -> None:
        if not resolved_path.exists():
            return
        if if_hash is None:
            raise WriteConflictError("if_hash is required for existing notes")

        current_hash = compute_sha256(resolved_path.read_text(encoding="utf-8"))
        if current_hash != if_hash:
            raise WriteConflictError("stale if_hash does not match current note content")

    def _resolve_attachment_paths(self, command: WriteNoteCommand) -> list[Path]:
        return [self.paths.resolve_file_path(attachment.path) for attachment in command.attachments]

    def _write_attachments(self, command: WriteNoteCommand, attachment_paths: list[Path]) -> None:
        for attachment, path in zip(command.attachments, attachment_paths, strict=True):
            content = attachment.decoded_bytes()
            if path.exists() and path.read_bytes() != content:
                raise WriteConflictError(f"attachment already exists: {attachment.path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
