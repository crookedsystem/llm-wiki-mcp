from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from tempfile import mkdtemp

from pydantic import Field

from common.helper.note_metadata_helper import extract_note_metadata
from common.helper.time_helper import TimeHelper
from common.model import FrozenModel
from vault.component.write_queue import VaultWriteQueue
from vault.entity.vault_note import (
    append_provenance_trailer,
    compute_sha256,
)
from vault.infrastructure.repository.vault_note_repository import VaultNoteRepository
from vault.service.command.organize_folders_command import OrganizeFoldersCommand
from vault.service.folder_organization_link_rewriter import (
    path_replacements,
    replace_wiki_links,
    stem_replacements,
)
from vault.service.folder_organization_planner import (
    SECTION_BY_ROOT,
    FolderOrganizationNote,
    normalize_tag,
    plan_moves,
)
from vault.service.folder_organization_schema import (
    append_schema_rules,
    index_summary,
    membership_rule,
    seed_schema,
)
from vault.service.result.organize_folders_result import FolderMove, OrganizeFoldersResult
from vault.service.vault_index_service import IndexEntry, VaultIndexService
from vault.service.vault_log_archiver import VaultLogArchiver
from vault.service.vault_log_service import LogEntry, VaultLogService
from vault.service.vault_operational_note import OperationalNote
from vault.service.vault_operational_paths import (
    INDEX_NOTE_PATH,
    LOG_NOTE_PATH,
    is_operational_note,
    log_archive_year,
)

SCHEMA_NOTE_PATH = "SCHEMA.md"
TEMPORARY_MOVE_DIRECTORY = ".llm-wiki-organize-tmp"
ORGANIZE_TIMESTAMP_FIELD = "organize timestamp"

ORGANIZE_FOLDERS_SAFETY_NOTICE = (
    "Folder organization can move many notes and rewrite backlinks. Run dry_run first, inspect "
    "every move, then pass the exact confirmation_phrase only when the proposed reorganization "
    "is acceptable. In-process failures roll back automatically; if the process is killed "
    "mid-apply, recover any leftover notes from the .llm-wiki-organize-tmp/ staging directory."
)

_OPERATIONAL_NOTE_PATHS = (SCHEMA_NOTE_PATH, INDEX_NOTE_PATH, LOG_NOTE_PATH)


class _FileSnapshot(FrozenModel):
    path: Path
    content: str | None


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _slug(path: str) -> str:
    return Path(path).with_suffix("").as_posix()


def _note_by_path(
    notes: list[FolderOrganizationNote],
) -> dict[str, FolderOrganizationNote]:
    return {note.relative_path: note for note in notes}


class VaultFolderOrganizationService(FrozenModel):
    note_repository: VaultNoteRepository
    queue: VaultWriteQueue
    actor: str = "llm-wiki"
    clock: Callable[[], datetime] = _utc_now
    index_service: VaultIndexService = Field(default_factory=VaultIndexService)
    log_service: VaultLogService = Field(default_factory=VaultLogService)

    async def organize_folders(
        self,
        command: OrganizeFoldersCommand,
    ) -> OrganizeFoldersResult:
        async def operation() -> OrganizeFoldersResult:
            return self._organize_folders(command)

        return await self.queue.run(operation)

    def _organize_folders(self, command: OrganizeFoldersCommand) -> OrganizeFoldersResult:
        notes = self._notes()
        moves = plan_moves(notes, root_folder=command.root_folder)
        self._ensure_safe_destinations(moves, notes)
        confirmation_phrase = self._confirmation_phrase(moves, notes)
        created_folders = self._created_folders(moves)

        if not command.dry_run and command.confirm != confirmation_phrase:
            raise PermissionError(
                "confirm must exactly match confirmation_phrase from a dry_run result"
            )

        updated_paths: list[str] = []
        if not command.dry_run and moves:
            updated_paths = self._apply_moves(moves, notes)

        return OrganizeFoldersResult(
            dry_run=command.dry_run,
            applied=not command.dry_run,
            moves=moves,
            created_folders=created_folders,
            updated_paths=updated_paths,
            confirmation_phrase=confirmation_phrase,
            safety_notice=ORGANIZE_FOLDERS_SAFETY_NOTICE,
        )

    def _notes(self) -> list[FolderOrganizationNote]:
        notes: list[FolderOrganizationNote] = []
        for note_path in self.note_repository.markdown_notes():
            relative_path = self.note_repository.relative_path(note_path)
            if is_operational_note(relative_path):
                continue
            content = self.note_repository.read_note(note_path)
            metadata = extract_note_metadata(content)
            notes.append(
                FolderOrganizationNote(
                    path=note_path,
                    relative_path=relative_path,
                    title=metadata.title,
                    page_type=metadata.page_type,
                    tags=tuple(normalize_tag(tag) for tag in metadata.tags),
                    content=content,
                    content_hash=compute_sha256(content),
                )
            )
        return notes

    def _organize_timestamp(self) -> str:
        return TimeHelper.format_utc_timestamp(self.clock(), field_name=ORGANIZE_TIMESTAMP_FIELD)

    def _ensure_safe_destinations(
        self,
        moves: list[FolderMove],
        notes: list[FolderOrganizationNote],
    ) -> None:
        old_paths = {move.old_path for move in moves}
        existing_paths = {note.relative_path for note in notes}
        # Name the colliding sources in the error so the caller can resolve the
        # conflict (rename one note) instead of guessing which notes clashed.
        destination_source: dict[str, str] = {}
        for move in moves:
            previous_source = destination_source.get(move.new_path)
            if previous_source is not None:
                raise ValueError(
                    "folder organization destination is duplicated: "
                    f"{move.new_path} <- {previous_source}, {move.old_path}"
                )
            destination_source[move.new_path] = move.old_path
            if move.new_path in existing_paths and move.new_path not in old_paths:
                raise ValueError(
                    "folder organization destination already exists: "
                    f"{move.new_path} <- {move.old_path}"
                )

    def _confirmation_phrase(
        self,
        moves: list[FolderMove],
        notes: list[FolderOrganizationNote],
    ) -> str:
        content_hashes = self._confirmation_content_hashes(moves, notes)
        payload = "\n".join(
            [
                *(f"{move.old_path}->{move.new_path}" for move in moves),
                *(f"{path}@{content_hash}" for path, content_hash in content_hashes.items()),
            ]
        )
        return f"ORGANIZE_FOLDERS: {compute_sha256(payload)}"

    def _confirmation_content_hashes(
        self,
        moves: list[FolderMove],
        notes: list[FolderOrganizationNote],
    ) -> dict[str, str]:
        move_paths = {move.old_path for move in moves}
        replacements = path_replacements(moves)
        stem_replaces = stem_replacements(moves, self._target_paths_for_link_rewrites(notes))
        hashes = {
            note.relative_path: note.content_hash
            for note in notes
            if note.relative_path in move_paths
            or self._would_rewrite_backlinks(note, replacements, stem_replaces)
        }
        for path in (*_OPERATIONAL_NOTE_PATHS, *self._existing_log_archive_paths()):
            hashes[path] = self._operational_file_hash(path)
        return dict(sorted(hashes.items()))

    def _existing_log_archive_paths(self) -> list[str]:
        """vault에 이미 있는 log-YYYY.md의 상대 경로 목록입니다.

        archive는 _rewrite_backlinks가 log.md와 똑같이 다시 쓰는 대상이므로 confirmation
        해시에도 포함해야 한다. 빠지면 dry_run 이후 손으로 고친 archive를 apply가 그대로
        덮어쓰는데도 confirmation이 무효화되지 않는다.
        """
        return sorted(
            path.name
            for path in self.note_repository.vault_root.glob("log-*.md")
            if log_archive_year(path.name) is not None
        )

    def _would_rewrite_backlinks(
        self,
        note: FolderOrganizationNote,
        replacements: dict[str, str],
        stem_replaces: dict[str, str],
    ) -> bool:
        return (
            replace_wiki_links(
                note.content,
                replacements,
                stem_replaces,
            )
            != note.content
        )

    def _operational_file_hash(self, relative_path: str) -> str:
        path = self.note_repository.vault_root / relative_path
        if not path.exists():
            return "<missing>"
        return compute_sha256(path.read_text(encoding="utf-8"))

    def _target_paths_for_link_rewrites(self, notes: list[FolderOrganizationNote]) -> list[str]:
        target_paths = [note.relative_path for note in notes]
        target_paths.extend(
            path
            for path in _OPERATIONAL_NOTE_PATHS
            if (self.note_repository.vault_root / path).exists()
        )
        return target_paths

    def _created_folders(self, moves: list[FolderMove]) -> list[str]:
        folders = {
            Path(move.new_path).parent.as_posix()
            for move in moves
            if not (self.note_repository.vault_root / Path(move.new_path).parent).exists()
        }
        return sorted(f"{folder}/" for folder in folders if folder != ".")

    def _apply_moves(
        self,
        moves: list[FolderMove],
        notes: list[FolderOrganizationNote],
    ) -> list[str]:
        snapshots = self._snapshots_for_apply(moves)
        try:
            note_by_path = _note_by_path(notes)
            target_paths = self._target_paths_for_link_rewrites(notes)
            updated_paths = self._rewrite_backlinks(moves, target_paths)
            moved_paths = self._move_note_files(moves)
            updated_paths.extend(moved_paths)
            updated_paths.extend(self._update_index(moves, note_by_path))
            updated_paths.extend(self._update_schema(moves, target_paths))
            updated_paths.extend(self._update_log(moves, note_by_path))
            self._remove_empty_move_directories(moves)
            return sorted(set(updated_paths))
        except Exception:
            self._restore_snapshots(snapshots)
            raise

    def _snapshots_for_apply(self, moves: list[FolderMove]) -> list[_FileSnapshot]:
        paths = set(self.note_repository.markdown_notes())
        for move in moves:
            paths.add(self.note_repository.vault_root / move.old_path)
            paths.add(self.note_repository.vault_root / move.new_path)
        for operational_path in _OPERATIONAL_NOTE_PATHS:
            paths.add(self.note_repository.vault_root / operational_path)
        # log rotation이 새로 만들 수 있는 log-YYYY.md까지 포함해야 롤백이 완결된다.
        paths.update(self._log_archiver.rotation_paths([self._organize_timestamp()[:4]]))
        return [self._snapshot_path(path) for path in sorted(paths)]

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

    def _rewrite_backlinks(
        self,
        moves: list[FolderMove],
        target_paths: list[str],
    ) -> list[str]:
        replacements = path_replacements(moves)
        old_stem_replacements = stem_replacements(moves, target_paths)
        updated_paths: list[str] = []
        for note_path in self.note_repository.markdown_notes():
            relative_path = self.note_repository.relative_path(note_path)
            # index.md and SCHEMA.md are rewritten by their dedicated updaters
            # (_update_index/_update_schema). log.md is intentionally rewritten here
            # so its historical backlinks stay valid before _update_log appends new
            # entries.
            if relative_path in {INDEX_NOTE_PATH, SCHEMA_NOTE_PATH}:
                continue
            content = note_path.read_text(encoding="utf-8")
            updated = replace_wiki_links(content, replacements, old_stem_replacements)
            if updated == content:
                continue
            note_path.write_text(updated, encoding="utf-8")
            updated_paths.append(relative_path)
        return updated_paths

    def _move_note_files(self, moves: list[FolderMove]) -> list[str]:
        moved_paths: list[str] = []
        temporary_paths = self._temporary_move_paths(moves)
        try:
            for move in moves:
                old_path = self.note_repository.vault_root / move.old_path
                temporary_path = temporary_paths[move.old_path]
                temporary_path.parent.mkdir(parents=True, exist_ok=True)
                old_path.rename(temporary_path)
            for move in moves:
                temporary_path = temporary_paths[move.old_path]
                new_path = self.note_repository.vault_root / move.new_path
                new_path.parent.mkdir(parents=True, exist_ok=True)
                temporary_path.rename(new_path)
                moved_paths.append(move.new_path)
        finally:
            self._remove_temporary_move_directory(temporary_paths)
        return moved_paths

    def _temporary_move_paths(self, moves: list[FolderMove]) -> dict[str, Path]:
        temporary_root = self._create_temporary_move_root()
        return {
            move.old_path: temporary_root / f"{index}-{Path(move.old_path).name}"
            for index, move in enumerate(moves)
        }

    def _create_temporary_move_root(self) -> Path:
        temporary_base = self.note_repository.vault_root / TEMPORARY_MOVE_DIRECTORY
        temporary_base.mkdir(parents=True, exist_ok=True)
        return Path(mkdtemp(dir=temporary_base))

    def _remove_temporary_move_directory(self, temporary_paths: dict[str, Path]) -> None:
        for path in temporary_paths.values():
            path.unlink(missing_ok=True)
        temporary_roots = {path.parent for path in temporary_paths.values()}
        for path in sorted(temporary_roots, key=lambda item: len(item.parts), reverse=True):
            try:
                path.rmdir()
            except OSError:
                continue
        with suppress(OSError):
            (self.note_repository.vault_root / TEMPORARY_MOVE_DIRECTORY).rmdir()

    def _update_index(
        self,
        moves: list[FolderMove],
        note_by_path: dict[str, FolderOrganizationNote],
    ) -> list[str]:
        index_path = self.note_repository.vault_root / INDEX_NOTE_PATH
        existing = index_path.read_text(encoding="utf-8") if index_path.exists() else None
        if existing is None:
            return []

        updated = self._organize_timestamp()
        summary_by_old_slug: dict[str, str | None] = {}
        for move in moves:
            old_slug = _slug(move.old_path)
            summary_by_old_slug[old_slug] = index_summary(existing, old_slug)

        current = existing
        for move in moves:
            old_slug = _slug(move.old_path)
            current = (
                self.index_service.remove_entry(current, slug=old_slug, updated=updated) or current
            )
        for move in moves:
            old_slug = _slug(move.old_path)
            new_slug = _slug(move.new_path)
            note = note_by_path[move.old_path]
            current = self.index_service.upsert_entry(
                current,
                IndexEntry(
                    slug=new_slug,
                    title=note.title or Path(move.new_path).stem,
                    summary=summary_by_old_slug[old_slug],
                    section=SECTION_BY_ROOT[Path(move.new_path).parts[0]],
                    updated=updated,
                ),
            )

        if current == existing:
            return []
        self._persist_operational(index_path, current)
        return [INDEX_NOTE_PATH]

    def _update_schema(self, moves: list[FolderMove], target_paths: list[str]) -> list[str]:
        rules = self._subfolder_rules(moves)
        schema_path = self.note_repository.vault_root / SCHEMA_NOTE_PATH
        timestamp = self._organize_timestamp()
        note = (
            OperationalNote.parse(schema_path.read_text(encoding="utf-8"))
            if schema_path.exists()
            else seed_schema(timestamp)
        )
        body = replace_wiki_links(
            note.body,
            path_replacements(moves),
            stem_replacements(moves, target_paths),
        )
        body = append_schema_rules(body, rules)
        if body == note.body:
            return []
        self._persist_operational(
            schema_path,
            note.with_body(body).with_updated(timestamp).render(),
        )
        return [SCHEMA_NOTE_PATH]

    def _subfolder_rules(self, moves: list[FolderMove]) -> dict[str, str]:
        rules: dict[str, str] = {}
        for move in moves:
            folder = Path(move.new_path).parent.as_posix()
            if folder == Path(move.old_path).parent.as_posix():
                continue
            rules[folder] = membership_rule(folder)
        return dict(sorted(rules.items()))

    def _update_log(
        self,
        moves: list[FolderMove],
        note_by_path: dict[str, FolderOrganizationNote],
    ) -> list[str]:
        updated = self._organize_timestamp()
        entries = [
            LogEntry(
                date=updated[:10],
                action="update",
                slug=_slug(move.new_path),
                path=move.new_path,
                description=(
                    f"Moved from {move.old_path}: "
                    f"{note_by_path[move.old_path].title or move.new_path}"
                ),
                updated=updated,
            )
            for move in moves
        ]
        log_files = self._log_archiver.append_entries(entries)
        for log_file in log_files:
            self._persist_operational(log_file.path, log_file.content)
        return [self.note_repository.relative_path(log_file.path) for log_file in log_files]

    @property
    def _log_archiver(self) -> VaultLogArchiver:
        return VaultLogArchiver(
            vault_root=self.note_repository.vault_root,
            log_service=self.log_service,
        )

    def _persist_operational(self, path: Path, source_content: str) -> None:
        source_hash = compute_sha256(source_content)
        final_content = append_provenance_trailer(
            source_content,
            source_hash=source_hash,
            operation="organize_folders",
            actor=self.actor,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(final_content, encoding="utf-8")

    def _remove_empty_move_directories(self, moves: list[FolderMove]) -> None:
        for path in _old_parent_directories(self.note_repository.vault_root, moves):
            try:
                path.rmdir()
            except OSError:
                continue


def _old_parent_directories(vault_root: Path, moves: list[FolderMove]) -> list[Path]:
    candidates: set[Path] = set()
    for move in moves:
        parent = vault_root / Path(move.old_path).parent
        while parent != vault_root and parent.parent != vault_root:
            candidates.add(parent)
            parent = parent.parent
    return sorted(candidates, key=lambda path: len(path.parts), reverse=True)
