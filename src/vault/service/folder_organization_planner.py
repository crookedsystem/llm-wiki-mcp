import re
from collections import defaultdict
from pathlib import Path

from common.model import FrozenModel
from vault.service.command.organize_folders_command import FolderOrganizationRoot
from vault.service.result.organize_folders_result import FolderMove

ROOT_FOLDERS = frozenset({"raw", "entities", "concepts", "comparisons", "queries"})
DIRECT_SPLIT_THRESHOLD = 16
MIN_CHILD_GROUP_SIZE = 5
MAX_SUBFOLDER_SPLIT_PASSES = 5

_ROOT_BY_TYPE: dict[str, str] = {
    "raw": "raw",
    "entity": "entities",
    "concept": "concepts",
    "comparison": "comparisons",
    "query": "queries",
}
SECTION_BY_ROOT: dict[str, str] = {
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


class FolderOrganizationNote(FrozenModel):
    path: Path
    relative_path: str
    title: str | None
    page_type: str | None
    tags: tuple[str, ...]
    content: str
    content_hash: str


def normalize_tag(tag: str) -> str:
    return tag.strip().lower().replace("_", "-").replace(" ", "-")


def plan_moves(
    notes: list[FolderOrganizationNote],
    *,
    root_folder: FolderOrganizationRoot | None,
) -> list[FolderMove]:
    virtual_paths = {
        note.relative_path: _top_folder_corrected_path(note, root_folder=root_folder)
        for note in notes
    }
    reasons: dict[str, list[str]] = {
        note.relative_path: _initial_reasons(note, virtual_paths[note.relative_path])
        for note in notes
    }
    entity_scopes = _entity_scopes(notes)

    for _ in range(MAX_SUBFOLDER_SPLIT_PASSES):
        pending = _next_subfolder_moves(notes, virtual_paths, entity_scopes, root_folder)
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
    note: FolderOrganizationNote,
    *,
    root_folder: FolderOrganizationRoot | None,
) -> str:
    current_parts = Path(note.relative_path).parts
    current_root = current_parts[0] if current_parts else ""
    expected_root = _expected_root(note.page_type, current_root)
    if expected_root is None or current_root == expected_root:
        return note.relative_path
    if root_folder is not None and root_folder not in {current_root, expected_root}:
        return note.relative_path
    return f"{expected_root}/{Path(note.relative_path).name}"


def _initial_reasons(note: FolderOrganizationNote, target_path: str) -> list[str]:
    if target_path == note.relative_path:
        return []
    note_type = note.page_type or "unknown"
    return [f"type {note_type!r} belongs under {Path(target_path).parts[0]}/"]


def _expected_root(page_type: str | None, current_root: str) -> str | None:
    if page_type == "summary" and current_root in {"concepts", "queries"}:
        return current_root
    if page_type == "summary":
        return "concepts"
    return _ROOT_BY_TYPE.get(page_type or "")


def _next_subfolder_moves(
    notes: list[FolderOrganizationNote],
    virtual_paths: dict[str, str],
    entity_scopes: frozenset[str],
    root_folder: FolderOrganizationRoot | None,
) -> list[tuple[str, str, str]]:
    notes_by_relative_path = {note.relative_path: note for note in notes}
    direct_notes_by_parent: dict[str, list[FolderOrganizationNote]] = defaultdict(list)
    for note in notes:
        virtual_path = Path(virtual_paths[note.relative_path])
        if root_folder is not None and virtual_path.parts[0] != root_folder:
            continue
        direct_notes_by_parent[virtual_path.parent.as_posix()].append(note)

    moves: list[tuple[str, str, str]] = []
    for parent_path, direct_notes in sorted(direct_notes_by_parent.items()):
        if len(direct_notes) < DIRECT_SPLIT_THRESHOLD:
            continue
        grouped = _groups_for_parent(
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
    direct_notes: list[FolderOrganizationNote],
    *,
    parent_path: str,
    virtual_paths: dict[str, str],
    entity_scopes: frozenset[str],
) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for note in direct_notes:
        virtual_path = Path(virtual_paths[note.relative_path])
        key = _subfolder_key(note, virtual_path=virtual_path, entity_scopes=entity_scopes)
        if key is None or key in Path(parent_path).parts:
            continue
        groups[key].append(note.relative_path)
    return groups


def _subfolder_key(
    note: FolderOrganizationNote,
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
        return _synthesis_scope_key(note, entity_scopes)
    return None


def _synthesis_scope_key(
    note: FolderOrganizationNote,
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


def _entity_scopes(notes: list[FolderOrganizationNote]) -> frozenset[str]:
    scopes: set[str] = set()
    for note in notes:
        path = Path(note.relative_path)
        if not path.parts or path.parts[0] != "entities":
            continue
        scopes.add(path.stem)
        scopes.update(tag for tag in note.tags if _is_scope_like_tag(tag))
    return frozenset(scopes)


def _is_scope_like_tag(tag: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)+", tag))


def _first_matching_key(
    tags: tuple[str, ...],
    keyed_tags: tuple[tuple[str, frozenset[str]], ...],
) -> str | None:
    matched = [key for key, values in keyed_tags if set(tags).intersection(values)]
    return matched[0] if len(matched) == 1 else None
