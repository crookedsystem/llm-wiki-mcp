from pathlib import Path

from pydantic import Field

from common.model import FrozenModel
from vault.component.write_queue import VaultWriteQueue
from vault.entity.vault_note import (
    PROVENANCE_PREFIX,
    append_provenance_trailer,
    compute_sha256,
    parse_note,
)
from vault.entity.vault_path import VaultPaths
from vault.error.write_error import WriteConflictError
from vault.service.command.write_note_command import WriteNoteCommand
from vault.service.result.write_note_result import WriteNoteResult
from vault.service.vault_note_renderer import VaultNoteRenderer

_APPEND_ONLY_LOG_PATH = Path("log.md")


class _FileSnapshot(FrozenModel):
    path: Path
    content: bytes | None


class VaultWriteService(FrozenModel):
    paths: VaultPaths
    queue: VaultWriteQueue
    actor: str = "llm-wiki"
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

    async def _write_note(self, command: WriteNoteCommand) -> WriteNoteResult:
        resolved_path = self.paths.resolve_note_path(command.note_path)
        relative_path = resolved_path.relative_to(self.paths.root.resolve())
        if relative_path == _APPEND_ONLY_LOG_PATH:
            raise WriteConflictError(
                "log.md is append-only; write the target note and let the writer append "
                "audit entries"
            )

        action = "update" if resolved_path.exists() else "create"
        self._check_if_hash(resolved_path, command.if_hash)
        attachment_paths = self._resolve_attachment_paths(command)
        log_path = self.paths.resolve_note_path(_APPEND_ONLY_LOG_PATH)
        snapshots = self._snapshot_paths([resolved_path, *attachment_paths, log_path])

        try:
            content = self.note_renderer.render(command)
            source_hash = compute_sha256(content)
            final_content = append_provenance_trailer(
                content,
                source_hash=source_hash,
                operation="write_note",
                actor=self.actor,
            )
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
            resolved_path.write_text(final_content, encoding="utf-8")
            self._write_attachments(command, attachment_paths)
            self._append_audit_log(command, relative_path=relative_path, action=action)
            return WriteNoteResult(
                path=resolved_path,
                source_hash=source_hash,
                content_hash=compute_sha256(final_content),
                attachment_paths=tuple(attachment_paths),
            )
        except Exception:
            self._restore_snapshots(snapshots)
            raise

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

    def _append_audit_log(
        self,
        source_command: WriteNoteCommand,
        *,
        relative_path: Path,
        action: str,
    ) -> None:
        log_path = self.paths.resolve_note_path(_APPEND_ONLY_LOG_PATH)
        entry = self._audit_log_entry(source_command, relative_path=relative_path, action=action)
        content = f"{self._log_base_content(log_path, source_command).rstrip()}\n\n{entry}\n"
        final_content = append_provenance_trailer(
            content,
            source_hash=compute_sha256(content),
            operation="append_log",
            actor=self.actor,
        )
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(final_content, encoding="utf-8")

    def _log_base_content(self, log_path: Path, source_command: WriteNoteCommand) -> str:
        """Return existing log content (without its provenance trailer) to append onto.

        A fresh or plain legacy log is rendered into the structured `Wiki Log` shape; an
        already-structured log keeps its frontmatter and prior entries verbatim so we only
        strip the trailer and append the new entry at the end.
        """
        if not log_path.exists():
            return self._render_log(self._initial_log_body(), source_command)
        raw_log = log_path.read_text(encoding="utf-8")
        if parse_note(raw_log).frontmatter is None:
            return self._render_log(self._plain_log_body(raw_log), source_command)
        return self._strip_trailer(raw_log)

    def _render_log(self, body: str, source_command: WriteNoteCommand) -> str:
        command = WriteNoteCommand(
            note_path=_APPEND_ONLY_LOG_PATH,
            title="Wiki Log",
            type="log",
            tags=("llm-wiki", "audit-log"),
            sources=(),
            body=body,
            created=source_command.updated,
            updated=source_command.updated,
            confidence="high",
            contested=False,
        )
        return self.note_renderer.render(command)

    def _strip_trailer(self, raw_log: str) -> str:
        lines = raw_log.splitlines()
        while lines and not lines[-1].strip():
            lines.pop()
        if lines and lines[-1].startswith(PROVENANCE_PREFIX):
            lines.pop()
        return "\n".join(lines)

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

    def _plain_log_body(self, raw_log: str) -> str:
        lines = raw_log.splitlines()
        while lines and not lines[-1].strip():
            lines.pop()
        if lines and lines[-1].startswith(PROVENANCE_PREFIX):
            lines.pop()
        while lines and not lines[0].strip():
            lines.pop(0)
        if lines and lines[0] == "# Wiki Log":
            lines.pop(0)
            if lines and not lines[0].strip():
                lines.pop(0)
        body = "\n".join(lines).strip("\n")
        return body if body else self._initial_log_body()

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
