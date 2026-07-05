import re
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import Field

from common.helper.note_metadata_helper import extract_note_metadata
from common.helper.time_helper import TimeHelper
from common.helper.wiki_link_helper import WIKI_LINK_PATTERN, normalize_wiki_target
from common.model import FrozenModel
from vault.component.write_queue import VaultWriteQueue
from vault.entity.vault_note import (
    append_provenance_trailer,
    compute_sha256,
    strip_provenance_trailer,
)
from vault.infrastructure.repository.vault_note_repository import VaultNoteRepository
from vault.service.command.organize_folders_command import (
    FolderOrganizationRoot,
    OrganizeFoldersCommand,
)
from vault.service.result.organize_folders_result import FolderMove, OrganizeFoldersResult
from vault.service.vault_index_service import IndexEntry, VaultIndexService
from vault.service.vault_log_service import LogEntry, VaultLogService
from vault.service.vault_operational_paths import INDEX_NOTE_PATH, LOG_NOTE_PATH

ROOT_FOLDERS = frozenset({"raw", "entities", "concepts", "comparisons", "queries"})
DIRECT_SPLIT_THRESHOLD = 16
MIN_CHILD_GROUP_SIZE = 5

ORGANIZE_FOLDERS_SAFETY_NOTICE = (
    "Folder organization can move many notes and rewrite backlinks. Run dry_run first, inspect "
    "every move, then pass the exact confirmation_phrase only when the proposed reorganization "
    "is acceptable."
)

_ROOT_BY_TYPE: dict[str, str] = {
    "raw": "raw",
    "entity": "entities",
    "concept": "concepts",
    "comparison": "comparisons",
    "query": "queries",
}
_SECTION_BY_ROOT: dict[str, str] = {
    "raw": "Raw Sources",
    "entities": "Entities",
    "concepts": "Concepts",
    "comparisons": "Comparisons",
    "queries": "Queries",
}
_ENTITY_KIND_TAGS: tuple[tuple[str, frozenset[str]], ...] = (
    ("projects", frozenset({"github", "repository", "repo", "project", "project-context"})),
    ("people", frozenset({"person", "people", "human"})),
    ("orgs", frozenset({"org", "organization", "company", "team"})),
    ("products", frozenset({"product", "tool", "software", "framework", "library", "package"})),
    ("models", frozenset({"model", "llm"})),
    ("standards", frozenset({"standard", "protocol", "specification"})),
    ("apis", frozenset({"api", "openapi"})),
    ("services", frozenset({"service", "backend", "frontend", "module"})),
)
_RAW_SOURCE_TYPE_TAGS: tuple[tuple[str, frozenset[str]], ...] = (
    ("articles", frozenset({"article", "articles", "blog", "paper"})),
    ("transcripts", frozenset({"transcript", "transcripts", "meeting", "conversation"})),
    ("assets", frozenset({"asset", "assets", "image", "audio", "video"})),
)
_DOMAIN_SCOPE_TAGS = frozenset(
    {
        "database",
        "postgresql",
        "mysql",
        "redis",
        "kafka",
        "docker",
        "kubernetes",
        "python",
        "fastapi",
        "nestjs",
        "spring-boot",
        "react",
        "nextjs",
        "openai",
        "obsidian",
    }
)
_LIST_ENTRY_PATTERN = re.compile(r"^\s*-\s+\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?]](.*)$")


class _FolderOrganizationNote(FrozenModel):
    path: Path
    relative_path: str
    title: str | None
    page_type: str | None
    tags: tuple[str, ...]
    content: str
    content_hash: str


class _FileSnapshot(FrozenModel):
    path: Path
    content: str | None


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


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
        moves = self._plan_moves(notes, root_folder=command.root_folder)
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

    def _notes(self) -> list[_FolderOrganizationNote]:
        notes: list[_FolderOrganizationNote] = []
        for note_path in self.note_repository.markdown_notes():
            relative_path = self.note_repository.relative_path(note_path)
            if relative_path in {INDEX_NOTE_PATH, LOG_NOTE_PATH, "SCHEMA.md"}:
                continue
            content = self.note_repository.read_note(note_path)
            metadata = extract_note_metadata(content)
            notes.append(
                _FolderOrganizationNote(
                    path=note_path,
                    relative_path=relative_path,
                    title=metadata.title,
                    page_type=metadata.page_type,
                    tags=tuple(_normalize_tag(tag) for tag in metadata.tags),
                    content=content,
                    content_hash=compute_sha256(content),
                )
            )
        return notes

    def _plan_moves(
        self,
        notes: list[_FolderOrganizationNote],
        *,
        root_folder: FolderOrganizationRoot | None,
    ) -> list[FolderMove]:
        virtual_paths = {
            note.relative_path: self._top_folder_corrected_path(note, root_folder=root_folder)
            for note in notes
        }
        reasons: dict[str, list[str]] = {
            note.relative_path: self._initial_reasons(note, virtual_paths[note.relative_path])
            for note in notes
        }
        entity_scopes = self._entity_scopes(notes)

        for _ in range(5):
            pending = self._next_subfolder_moves(notes, virtual_paths, entity_scopes, root_folder)
            if not pending:
                break
            for old_path, new_path, reason in pending:
                virtual_paths[old_path] = new_path
                reasons[old_path].append(reason)

        return [
            FolderMove(
                old_path=note.relative_path,
                new_path=virtual_paths[note.relative_path],
                reason="; ".join(reasons[note.relative_path]),
            )
            for note in sorted(notes, key=lambda item: item.relative_path)
            if virtual_paths[note.relative_path] != note.relative_path
        ]

    def _top_folder_corrected_path(
        self,
        note: _FolderOrganizationNote,
        *,
        root_folder: FolderOrganizationRoot | None,
    ) -> str:
        current_parts = Path(note.relative_path).parts
        current_root = current_parts[0] if current_parts else ""
        expected_root = self._expected_root(note.page_type, current_root)
        if expected_root is None or current_root == expected_root:
            return note.relative_path
        if root_folder is not None and root_folder not in {current_root, expected_root}:
            return note.relative_path
        return f"{expected_root}/{Path(note.relative_path).name}"

    def _initial_reasons(self, note: _FolderOrganizationNote, target_path: str) -> list[str]:
        if target_path == note.relative_path:
            return []
        note_type = note.page_type or "unknown"
        return [f"type {note_type!r} belongs under {Path(target_path).parts[0]}/"]

    def _expected_root(self, page_type: str | None, current_root: str) -> str | None:
        if page_type == "summary" and current_root in {"concepts", "queries"}:
            return current_root
        if page_type == "summary":
            return "concepts"
        return _ROOT_BY_TYPE.get(page_type or "")

    def _next_subfolder_moves(
        self,
        notes: list[_FolderOrganizationNote],
        virtual_paths: dict[str, str],
        entity_scopes: frozenset[str],
        root_folder: FolderOrganizationRoot | None,
    ) -> list[tuple[str, str, str]]:
        notes_by_relative_path = {note.relative_path: note for note in notes}
        direct_notes_by_parent: dict[str, list[_FolderOrganizationNote]] = defaultdict(list)
        for note in notes:
            virtual_path = Path(virtual_paths[note.relative_path])
            if root_folder is not None and virtual_path.parts[0] != root_folder:
                continue
            direct_notes_by_parent[virtual_path.parent.as_posix()].append(note)

        moves: list[tuple[str, str, str]] = []
        for parent_path, direct_notes in sorted(direct_notes_by_parent.items()):
            if len(direct_notes) < DIRECT_SPLIT_THRESHOLD:
                continue
            grouped = self._groups_for_parent(
                direct_notes,
                parent_path=parent_path,
                virtual_paths=virtual_paths,
                entity_scopes=entity_scopes,
            )
            eligible_groups = {
                key: group for key, group in grouped.items() if len(group) >= MIN_CHILD_GROUP_SIZE
            }
            if len(eligible_groups) < 2:
                continue
            for key, group in sorted(eligible_groups.items()):
                for note_path in sorted(group):
                    note = notes_by_relative_path[note_path]
                    old_virtual = Path(virtual_paths[note.relative_path])
                    new_virtual = old_virtual.parent / key / old_virtual.name
                    moves.append(
                        (
                            note.relative_path,
                            new_virtual.as_posix(),
                            f"{parent_path}/ split by closed key {key!r}",
                        )
                    )
        return moves

    def _groups_for_parent(
        self,
        direct_notes: list[_FolderOrganizationNote],
        *,
        parent_path: str,
        virtual_paths: dict[str, str],
        entity_scopes: frozenset[str],
    ) -> dict[str, list[str]]:
        groups: dict[str, list[str]] = defaultdict(list)
        for note in direct_notes:
            virtual_path = Path(virtual_paths[note.relative_path])
            key = self._subfolder_key(note, virtual_path=virtual_path, entity_scopes=entity_scopes)
            if key is None or key in Path(parent_path).parts:
                continue
            groups[key].append(note.relative_path)
        return groups

    def _subfolder_key(
        self,
        note: _FolderOrganizationNote,
        *,
        virtual_path: Path,
        entity_scopes: frozenset[str],
    ) -> str | None:
        if not virtual_path.parts:
            return None
        root = virtual_path.parts[0]
        if root == "entities":
            return _first_matching_key(note.tags, _ENTITY_KIND_TAGS)
        if root == "raw":
            return _first_matching_key(note.tags, _RAW_SOURCE_TYPE_TAGS)
        if root in {"concepts", "comparisons", "queries"}:
            return self._synthesis_scope_key(note, entity_scopes)
        return None

    def _synthesis_scope_key(
        self,
        note: _FolderOrganizationNote,
        entity_scopes: frozenset[str],
    ) -> str | None:
        matching_scopes = sorted(set(note.tags).intersection(entity_scopes))
        if len(matching_scopes) == 1:
            return matching_scopes[0]
        if matching_scopes:
            return None

        matching_domains = sorted(set(note.tags).intersection(_DOMAIN_SCOPE_TAGS))
        if len(matching_domains) == 1:
            return matching_domains[0]
        return None

    def _entity_scopes(self, notes: list[_FolderOrganizationNote]) -> frozenset[str]:
        scopes: set[str] = set()
        for note in notes:
            path = Path(note.relative_path)
            if not path.parts or path.parts[0] != "entities":
                continue
            scopes.add(path.stem)
            scopes.update(tag for tag in note.tags if _is_scope_like_tag(tag))
        return frozenset(scopes)

    def _ensure_safe_destinations(
        self,
        moves: list[FolderMove],
        notes: list[_FolderOrganizationNote],
    ) -> None:
        old_paths = {move.old_path for move in moves}
        existing_paths = {note.relative_path for note in notes}
        seen_destinations: set[str] = set()
        for move in moves:
            if move.new_path in seen_destinations:
                raise ValueError(f"folder organization destination is duplicated: {move.new_path}")
            seen_destinations.add(move.new_path)
            if move.new_path in existing_paths and move.new_path not in old_paths:
                raise ValueError(f"folder organization destination already exists: {move.new_path}")

    def _confirmation_phrase(
        self,
        moves: list[FolderMove],
        notes: list[_FolderOrganizationNote],
    ) -> str:
        note_by_path = {note.relative_path: note for note in notes}
        payload = "\n".join(
            f"{move.old_path}->{move.new_path}@{note_by_path[move.old_path].content_hash}"
            for move in moves
        )
        return f"ORGANIZE_FOLDERS: {compute_sha256(payload)}"

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
        notes: list[_FolderOrganizationNote],
    ) -> list[str]:
        snapshots = self._snapshots_for_apply(moves)
        try:
            updated_paths = self._rewrite_backlinks(moves)
            moved_paths = self._move_note_files(moves)
            updated_paths.extend(moved_paths)
            updated_paths.extend(self._update_index(moves, notes))
            updated_paths.extend(self._update_schema(moves))
            updated_paths.extend(self._update_log(moves, notes))
            self._remove_empty_directories()
            return sorted(set(updated_paths))
        except Exception:
            self._restore_snapshots(snapshots)
            raise

    def _snapshots_for_apply(self, moves: list[FolderMove]) -> list[_FileSnapshot]:
        paths = set(self.note_repository.markdown_notes())
        for move in moves:
            paths.add(self.note_repository.vault_root / move.old_path)
            paths.add(self.note_repository.vault_root / move.new_path)
        for operational_path in ("SCHEMA.md", INDEX_NOTE_PATH, LOG_NOTE_PATH):
            paths.add(self.note_repository.vault_root / operational_path)
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

    def _rewrite_backlinks(self, moves: list[FolderMove]) -> list[str]:
        replacements = {move.old_path: move.new_path for move in moves}
        old_stem_replacements = {
            Path(move.old_path).stem: move.new_path
            for move in moves
            if sum(
                1
                for candidate in moves
                if Path(candidate.old_path).stem == Path(move.old_path).stem
            )
            == 1
        }
        updated_paths: list[str] = []
        for note_path in self.note_repository.markdown_notes():
            relative_path = self.note_repository.relative_path(note_path)
            if relative_path == INDEX_NOTE_PATH:
                continue
            content = note_path.read_text(encoding="utf-8")
            updated = _replace_wiki_links(content, replacements, old_stem_replacements)
            if updated == content:
                continue
            note_path.write_text(updated, encoding="utf-8")
            updated_paths.append(relative_path)
        return updated_paths

    def _move_note_files(self, moves: list[FolderMove]) -> list[str]:
        moved_paths: list[str] = []
        for move in moves:
            old_path = self.note_repository.vault_root / move.old_path
            new_path = self.note_repository.vault_root / move.new_path
            new_path.parent.mkdir(parents=True, exist_ok=True)
            old_path.rename(new_path)
            moved_paths.append(move.new_path)
        return moved_paths

    def _update_index(
        self,
        moves: list[FolderMove],
        notes: list[_FolderOrganizationNote],
    ) -> list[str]:
        index_path = self.note_repository.vault_root / INDEX_NOTE_PATH
        existing = index_path.read_text(encoding="utf-8") if index_path.exists() else None
        if existing is None:
            return []

        updated = TimeHelper.format_utc_timestamp(self.clock(), field_name="organize timestamp")
        note_by_path = {note.relative_path: note for note in notes}
        current = existing
        for move in moves:
            old_slug = Path(move.old_path).with_suffix("").as_posix()
            new_slug = Path(move.new_path).with_suffix("").as_posix()
            note = note_by_path[move.old_path]
            summary = _index_summary(current, old_slug)
            current = (
                self.index_service.remove_entry(current, slug=old_slug, updated=updated) or current
            )
            current = self.index_service.upsert_entry(
                current,
                IndexEntry(
                    slug=new_slug,
                    title=note.title or Path(move.new_path).stem,
                    summary=summary,
                    section=_SECTION_BY_ROOT[Path(move.new_path).parts[0]],
                    updated=updated,
                ),
            )

        if current == existing:
            return []
        self._persist_operational(index_path, current)
        return [INDEX_NOTE_PATH]

    def _update_schema(self, moves: list[FolderMove]) -> list[str]:
        rules = self._subfolder_rules(moves)
        if not rules:
            return []

        schema_path = self.note_repository.vault_root / "SCHEMA.md"
        existing = (
            strip_provenance_trailer(schema_path.read_text(encoding="utf-8"))
            if schema_path.exists()
            else None
        )
        updated = _append_schema_rules(existing, rules)
        if updated == existing:
            return []
        self._persist_operational(schema_path, updated)
        return ["SCHEMA.md"]

    def _subfolder_rules(self, moves: list[FolderMove]) -> dict[str, str]:
        rules: dict[str, str] = {}
        for move in moves:
            folder = Path(move.new_path).parent.as_posix()
            if folder == Path(move.old_path).parent.as_posix():
                continue
            rules[folder] = _membership_rule(folder)
        return dict(sorted(rules.items()))

    def _update_log(
        self,
        moves: list[FolderMove],
        notes: list[_FolderOrganizationNote],
    ) -> list[str]:
        log_path = self.note_repository.vault_root / LOG_NOTE_PATH
        existing = log_path.read_text(encoding="utf-8") if log_path.exists() else None
        updated = TimeHelper.format_utc_timestamp(self.clock(), field_name="organize timestamp")
        note_by_path = {note.relative_path: note for note in notes}
        current = existing
        for move in moves:
            note = note_by_path[move.old_path]
            current = self.log_service.append_entry(
                current,
                LogEntry(
                    date=updated[:10],
                    action="update",
                    slug=Path(move.new_path).with_suffix("").as_posix(),
                    path=move.new_path,
                    description=f"Moved from {move.old_path}: {note.title or move.new_path}",
                    updated=updated,
                ),
            )
        if current is None:
            return []
        self._persist_operational(log_path, current)
        return [LOG_NOTE_PATH]

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

    def _remove_empty_directories(self) -> None:
        for path in sorted(self.note_repository.vault_root.rglob("*"), reverse=True):
            if not path.is_dir() or path == self.note_repository.vault_root:
                continue
            if path.parent == self.note_repository.vault_root and path.name in ROOT_FOLDERS:
                continue
            try:
                path.rmdir()
            except OSError:
                continue


def _normalize_tag(tag: str) -> str:
    return tag.strip().lower().replace("_", "-").replace(" ", "-")


def _is_scope_like_tag(tag: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)+", tag))


def _first_matching_key(
    tags: tuple[str, ...],
    keyed_tags: tuple[tuple[str, frozenset[str]], ...],
) -> str | None:
    matched = [key for key, values in keyed_tags if set(tags).intersection(values)]
    return matched[0] if len(matched) == 1 else None


def _replace_wiki_links(
    content: str,
    replacements: dict[str, str],
    stem_replacements: dict[str, str],
) -> str:
    def replace_link(match: re.Match[str]) -> str:
        raw_link = match.group(1)
        target, separator, alias = raw_link.partition("|")
        target_path, anchor_separator, anchor = target.partition("#")
        normalized = normalize_wiki_target(target)
        replacement = replacements.get(f"{normalized}.md") or replacements.get(normalized)
        if replacement is None:
            replacement = stem_replacements.get(normalized)
        if replacement is None:
            return match.group(0)

        new_target = Path(replacement).with_suffix("").as_posix()
        if anchor_separator:
            new_target = f"{new_target}#{anchor}"
        return f"[[{new_target}|{alias}]]" if separator else f"[[{new_target}]]"

    return WIKI_LINK_PATTERN.sub(replace_link, content)


def _index_summary(index_content: str, slug: str) -> str | None:
    for line in index_content.splitlines():
        match = _LIST_ENTRY_PATTERN.match(line)
        if match is None or normalize_wiki_target(match.group(1)) != slug:
            continue
        description = match.group(2).strip()
        if description.startswith("—"):
            return description.removeprefix("—").strip() or None
    return None


def _append_schema_rules(existing: str | None, rules: dict[str, str]) -> str:
    if existing is None:
        body = [
            "# Wiki Schema",
            "",
            "## Subfolders",
            *[_schema_rule_line(folder, rule) for folder, rule in rules.items()],
        ]
        return "\n".join(body) + "\n"

    lines = existing.splitlines()
    missing_lines = [
        _schema_rule_line(folder, rule)
        for folder, rule in rules.items()
        if not _schema_has_rule(lines, folder)
    ]
    if not missing_lines:
        return existing

    insert_at = _subfolder_rule_insert_index(lines)
    if insert_at is None:
        base = [*lines, "", "## Subfolders"]
        return "\n".join([*base, *missing_lines]) + "\n"
    return "\n".join([*lines[:insert_at], *missing_lines, *lines[insert_at:]]) + "\n"


def _schema_rule_line(folder: str, rule: str) -> str:
    return f"- `{folder}/`: {rule}"


def _schema_has_rule(lines: list[str], folder: str) -> bool:
    marker = f"`{folder}/`"
    return any(marker in line for line in lines)


def _subfolder_rule_insert_index(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if line.strip() != "## Subfolders":
            continue
        insert_at = index + 1
        while insert_at < len(lines):
            if lines[insert_at].startswith("## "):
                break
            insert_at += 1
        return insert_at
    return None


def _membership_rule(folder: str) -> str:
    parts = Path(folder).parts
    if len(parts) < 2:
        return "Notes assigned by a deterministic folder organization rule."
    root, key = parts[0], parts[-1]
    if root == "entities":
        return f"Entity pages whose stable entity kind is `{key}`."
    if root == "raw":
        return f"Raw source notes whose source type is `{key}`."
    if root == "concepts":
        return f"Concept pages scoped to `{key}`."
    if root == "queries":
        return f"Durable query notes scoped to `{key}`."
    if root == "comparisons":
        return f"Comparison and decision notes scoped to `{key}`."
    return f"Notes assigned to `{key}` by a deterministic folder organization rule."
