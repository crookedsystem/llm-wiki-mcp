from pathlib import Path

from pydantic import Field

from common.model import FrozenModel
from vault.component.write_queue import VaultWriteQueue
from vault.entity.vault_note import append_provenance_trailer, compute_sha256
from vault.entity.vault_path import VaultPaths
from vault.error.write_error import WriteConflictError
from vault.infrastructure.repository.git_repository import GitRepository
from vault.service.command.write_note_command import WriteNoteCommand
from vault.service.note_timestamp import format_note_timestamp
from vault.service.result.write_note_result import WriteNoteResult
from vault.service.vault_index_service import IndexEntry, VaultIndexService
from vault.service.vault_log_service import LogEntry, VaultLogService, WriteAction
from vault.service.vault_note_renderer import VaultNoteRenderer

LOG_NOTE_PATH = "log.md"
INDEX_NOTE_PATH = "index.md"
ROOT_OPERATIONAL_FILES = frozenset({"SCHEMA.md", INDEX_NOTE_PATH, LOG_NOTE_PATH})

# Map a note's top-level folder to its canonical index.md section heading.
_SECTION_BY_FOLDER: dict[str, str] = {
    "raw": "Raw Sources",
    "entities": "Entities",
    "concepts": "Concepts",
    "comparisons": "Comparisons",
    "queries": "Queries",
}


class _FileSnapshot(FrozenModel):
    path: Path
    content: str | None


class VaultWriteService(FrozenModel):
    paths: VaultPaths
    queue: VaultWriteQueue
    actor: str = "llm-wiki"
    git_repository: GitRepository | None = None
    note_renderer: VaultNoteRenderer = Field(default_factory=VaultNoteRenderer)
    log_service: VaultLogService = Field(default_factory=VaultLogService)
    index_service: VaultIndexService = Field(default_factory=VaultIndexService)

    async def write_note(self, command: WriteNoteCommand) -> WriteNoteResult:
        async def operation() -> WriteNoteResult:
            return self._run_transaction([command], atomic=True)[0]

        return await self.queue.run(operation)

    async def batch_write_notes(
        self,
        commands: list[WriteNoteCommand],
        *,
        atomic: bool = True,
    ) -> list[WriteNoteResult]:
        async def operation() -> list[WriteNoteResult]:
            return self._run_transaction(commands, atomic=atomic)

        return await self.queue.run(operation)

    def _run_transaction(
        self,
        commands: list[WriteNoteCommand],
        *,
        atomic: bool,
    ) -> list[WriteNoteResult]:
        snapshots = self._snapshot_affected(commands) if atomic else []
        try:
            return [self._write_note(command) for command in commands]
        except Exception:
            if atomic:
                self._restore_snapshots(snapshots)
            raise

    def _write_note(self, command: WriteNoteCommand) -> WriteNoteResult:
        resolved_path = self.paths.resolve_note_path(command.note_path)
        self._check_if_hash(resolved_path, command.if_hash)

        existed = resolved_path.exists()
        source_hash, content_hash = self._persist(resolved_path, self.note_renderer.render(command))

        written_paths = [resolved_path, *self._maintain_graph(command, resolved_path, existed)]
        commit_hash = self._commit_paths(written_paths)
        return WriteNoteResult(
            path=resolved_path,
            source_hash=source_hash,
            content_hash=content_hash,
            commit_hash=commit_hash,
        )

    def _maintain_graph(
        self,
        command: WriteNoteCommand,
        resolved_path: Path,
        existed: bool,
    ) -> list[Path]:
        relative_path = self._relative_note_path(resolved_path)
        if relative_path in ROOT_OPERATIONAL_FILES:
            return []

        updated = format_note_timestamp(command.updated)
        slug = Path(relative_path).with_suffix("").as_posix()
        action: WriteAction = "update" if existed else "create"

        written = [
            self._write_log(
                LogEntry(
                    date=command.updated.date().isoformat(),
                    action=action,
                    slug=slug,
                    path=relative_path,
                    description=command.summary or command.title,
                    updated=updated,
                )
            )
        ]
        section = _SECTION_BY_FOLDER.get(Path(relative_path).parts[0])
        if section is not None:
            written.append(
                self._write_index(
                    IndexEntry(
                        slug=slug,
                        title=command.title,
                        summary=command.summary,
                        section=section,
                        updated=updated,
                    )
                )
            )
        return written

    def _write_log(self, entry: LogEntry) -> Path:
        log_path = self.paths.resolve_note_path(LOG_NOTE_PATH)
        existing = log_path.read_text(encoding="utf-8") if log_path.exists() else None
        self._persist(log_path, self.log_service.append_entry(existing, entry))
        return log_path

    def _write_index(self, entry: IndexEntry) -> Path:
        index_path = self.paths.resolve_note_path(INDEX_NOTE_PATH)
        existing = index_path.read_text(encoding="utf-8") if index_path.exists() else None
        self._persist(index_path, self.index_service.upsert_entry(existing, entry))
        return index_path

    def _persist(self, path: Path, source_content: str) -> tuple[str, str]:
        source_hash = compute_sha256(source_content)
        final_content = append_provenance_trailer(
            source_content,
            source_hash=source_hash,
            operation="write_note",
            actor=self.actor,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(final_content, encoding="utf-8")
        return source_hash, compute_sha256(final_content)

    def _commit_paths(self, paths: list[Path]) -> str | None:
        if self.git_repository is None:
            return None
        return self.git_repository.commit_paths(
            paths,
            f"Update {self._relative_note_path(paths[0])}",
        )

    def _snapshot_affected(self, commands: list[WriteNoteCommand]) -> list[_FileSnapshot]:
        paths: list[Path] = []
        seen: set[Path] = set()
        maintains_graph = False
        for command in commands:
            resolved_path = self.paths.resolve_note_path(command.note_path)
            if resolved_path not in seen:
                seen.add(resolved_path)
                paths.append(resolved_path)
            if self._relative_note_path(resolved_path) not in ROOT_OPERATIONAL_FILES:
                maintains_graph = True
        if maintains_graph:
            for operational_name in (LOG_NOTE_PATH, INDEX_NOTE_PATH):
                resolved_path = self.paths.resolve_note_path(operational_name)
                if resolved_path not in seen:
                    seen.add(resolved_path)
                    paths.append(resolved_path)
        return [self._snapshot_path(path) for path in paths]

    def _snapshot_path(self, path: Path) -> _FileSnapshot:
        content = path.read_text(encoding="utf-8") if path.exists() else None
        return _FileSnapshot(path=path, content=content)

    def _restore_snapshots(self, snapshots: list[_FileSnapshot]) -> None:
        for snapshot in snapshots:
            if snapshot.content is None:
                snapshot.path.unlink(missing_ok=True)
                continue
            snapshot.path.parent.mkdir(parents=True, exist_ok=True)
            snapshot.path.write_text(snapshot.content, encoding="utf-8")

    def _relative_note_path(self, resolved_path: Path) -> str:
        return resolved_path.relative_to(self.paths.root.resolve()).as_posix()

    def _check_if_hash(self, resolved_path: Path, if_hash: str | None) -> None:
        if not resolved_path.exists():
            return
        if if_hash is None:
            raise WriteConflictError("if_hash is required for existing notes")

        current_hash = compute_sha256(resolved_path.read_text(encoding="utf-8"))
        if current_hash != if_hash:
            raise WriteConflictError("stale if_hash does not match current note content")
