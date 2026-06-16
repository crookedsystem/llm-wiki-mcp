import re
from pathlib import Path

from common.helper.note_metadata_helper import extract_note_metadata
from common.helper.wiki_link_helper import extract_wiki_links, normalize_wiki_target
from common.model import FrozenModel
from vault.component.write_queue import VaultWriteQueue
from vault.entity.vault_note import compute_sha256
from vault.entity.vault_path import VaultPaths
from vault.infrastructure.repository.vault_note_repository import VaultNoteRepository
from vault.service.command.delete_note_command import DeleteNoteCommand
from vault.service.result.delete_note_result import DeleteNoteResult, RelatedNoteCandidate

DELETE_SAFETY_NOTICE = (
    "Deletion is destructive. Use dry_run first, ask the user directly with the listed "
    "evidence before deleting the target note or cleaning references, and pass the exact "
    "confirmation_phrase only after the user explicitly requests deletion."
)

WIKI_LINK_PATTERN = re.compile(r"\[\[([^\]]+)]]")


class _NoteGraphNode(FrozenModel):
    path: Path
    relative_path: str
    title: str | None
    content: str
    content_hash: str
    links: list[str]


class VaultDeleteService(FrozenModel):
    paths: VaultPaths
    note_repository: VaultNoteRepository
    queue: VaultWriteQueue

    async def delete_note(self, command: DeleteNoteCommand) -> DeleteNoteResult:
        async def operation() -> DeleteNoteResult:
            return self._delete_note(command)

        return await self.queue.run(operation)

    def _delete_note(self, command: DeleteNoteCommand) -> DeleteNoteResult:
        target_path = self.paths.resolve_note_path(command.note_path)
        if not target_path.exists():
            raise FileNotFoundError(f"note not found: {Path(command.note_path).as_posix()}")

        nodes = self._graph_nodes()
        node_by_path = {node.relative_path: node for node in nodes}
        target_relative_path = self.note_repository.relative_path(target_path)
        target = node_by_path.get(target_relative_path)
        if target is None:
            raise FileNotFoundError(f"note not found: {target_relative_path}")

        related_candidates = self._related_candidates(target, nodes)
        reference_cleanup_paths = self._reference_cleanup_paths(command.reference_cleanup_paths)
        self._ensure_cleanup_paths_have_backlinks(reference_cleanup_paths, related_candidates)

        content_hashes = {
            path: node_by_path[path].content_hash
            for path in [target_relative_path, *reference_cleanup_paths]
        }
        confirmation_phrase = self._confirmation_phrase(
            target_relative_path,
            reference_cleanup_paths,
            content_hashes,
        )
        if not command.dry_run and command.confirm != confirmation_phrase:
            raise PermissionError(
                "confirm must exactly match confirmation_phrase from a dry_run result"
            )

        if not command.dry_run:
            for relative_path in reference_cleanup_paths:
                cleanup_node = node_by_path[relative_path]
                cleanup_node.path.write_text(
                    self._remove_target_references(cleanup_node.content, target),
                    encoding="utf-8",
                )
            target.path.unlink()

        return DeleteNoteResult(
            dry_run=command.dry_run,
            deleted=not command.dry_run,
            target_path=target_relative_path,
            reference_cleanup_paths=reference_cleanup_paths,
            deleted_paths=[] if command.dry_run else [target_relative_path],
            updated_paths=[] if command.dry_run else reference_cleanup_paths,
            content_hashes=content_hashes,
            related_candidates=related_candidates,
            confirmation_phrase=confirmation_phrase,
            safety_notice=DELETE_SAFETY_NOTICE,
        )

    def _graph_nodes(self) -> list[_NoteGraphNode]:
        nodes: list[_NoteGraphNode] = []
        for note_path in self.note_repository.markdown_notes():
            content = self.note_repository.read_note(note_path)
            metadata = extract_note_metadata(content)
            nodes.append(
                _NoteGraphNode(
                    path=note_path,
                    relative_path=self.note_repository.relative_path(note_path),
                    title=metadata.title,
                    content=content,
                    content_hash=compute_sha256(content),
                    links=extract_wiki_links(content),
                )
            )
        return nodes

    def _related_candidates(
        self,
        target: _NoteGraphNode,
        nodes: list[_NoteGraphNode],
    ) -> list[RelatedNoteCandidate]:
        target_keys = self._note_keys(target)
        evidence_by_path: dict[str, list[str]] = {}
        relationships_by_path: dict[str, set[str]] = {}

        for node in nodes:
            if node.relative_path == target.relative_path:
                continue
            for raw_link in node.links:
                if self._target_key(normalize_wiki_target(raw_link)) not in target_keys:
                    continue
                relationships_by_path.setdefault(node.relative_path, set()).add("backlink")
                evidence_by_path.setdefault(node.relative_path, []).append(
                    f"{node.relative_path} links to target via [[{raw_link}]]"
                )

        node_by_path = {node.relative_path: node for node in nodes}
        return [
            RelatedNoteCandidate(
                path=relative_path,
                title=node_by_path[relative_path].title,
                content_hash=node_by_path[relative_path].content_hash,
                relationships=sorted(relationships_by_path[relative_path]),
                evidence=evidence_by_path[relative_path],
            )
            for relative_path in sorted(relationships_by_path)
        ]

    def _reference_cleanup_paths(
        self, reference_cleanup_paths: tuple[str | Path, ...]
    ) -> list[str]:
        cleanup_paths: list[str] = []
        for note_path in reference_cleanup_paths:
            resolved_path = self.paths.resolve_note_path(note_path)
            if not resolved_path.exists():
                raise FileNotFoundError(
                    f"reference cleanup note not found: {Path(note_path).as_posix()}"
                )
            cleanup_paths.append(self.note_repository.relative_path(resolved_path))
        return sorted(cleanup_paths)

    def _ensure_cleanup_paths_have_backlinks(
        self,
        cleanup_paths: list[str],
        candidates: list[RelatedNoteCandidate],
    ) -> None:
        backlink_paths = {
            candidate.path for candidate in candidates if "backlink" in candidate.relationships
        }
        paths_without_backlinks = sorted(
            path for path in cleanup_paths if path not in backlink_paths
        )
        if paths_without_backlinks:
            raise ValueError(
                "reference_cleanup_paths must link to note_path: "
                + ", ".join(paths_without_backlinks)
            )

    def _remove_target_references(self, content: str, target: _NoteGraphNode) -> str:
        target_keys = self._note_keys(target)

        def replace_link(match: re.Match[str]) -> str:
            raw_target, separator, alias = match.group(1).partition("|")
            if self._target_key(normalize_wiki_target(raw_target)) not in target_keys:
                return match.group(0)
            return alias if separator else ""

        cleaned_content = WIKI_LINK_PATTERN.sub(replace_link, content)
        return re.sub(r"[ \t]+([,.;:!?])", r"\1", cleaned_content)

    def _note_keys(self, node: _NoteGraphNode) -> set[str]:
        relative_path = Path(node.relative_path)
        keys = {
            relative_path.with_suffix("").as_posix(),
            relative_path.stem,
        }
        if node.title:
            keys.add(node.title)
        return {self._target_key(key) for key in keys if key}

    def _target_key(self, target: str) -> str:
        return target.strip().lower()

    def _confirmation_phrase(
        self,
        target_path: str,
        cleanup_paths: list[str],
        content_hashes: dict[str, str],
    ) -> str:
        phrase = f"DELETE: {target_path}@{content_hashes[target_path]}"
        if cleanup_paths:
            cleanup_targets = ", ".join(f"{path}@{content_hashes[path]}" for path in cleanup_paths)
            phrase += f"; CLEAN REFERENCES: {cleanup_targets}"
        return phrase
