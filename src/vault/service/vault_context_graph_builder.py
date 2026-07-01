from pathlib import Path

from pydantic import Field

from common.helper.note_metadata_helper import extract_note_metadata
from common.helper.wiki_link_helper import extract_wiki_links, normalize_wiki_target
from common.model import FrozenModel
from vault.constant.search import QUERY_TOKEN_PATTERN
from vault.entity.vault_note import compute_sha256
from vault.infrastructure.repository.vault_note_repository import VaultNoteRepository
from vault.service.command.context_command import ContextCommand
from vault.service.result.context_result import (
    BrokenWikiLink,
    ContextReference,
    PromptCue,
    SuggestedLink,
)
from vault.service.vault_context_spec import ORIENTATION_PATHS

PROMPT_MEMORY_KINDS = (
    "working_context",
    "episodic_event",
    "semantic_fact",
    "procedural_pattern",
    "preference_profile",
    "project_convention",
    "constraint_policy",
    "failure_prevention",
    "prospective_task",
    "evaluation_feedback",
    "provenance_signal",
)
PROMPT_CUE_LIMIT_PER_KIND = 3


class ContextGraph(FrozenModel):
    orientation: list[ContextReference]
    broken_links: list[BrokenWikiLink]
    link_targets: list[ContextReference]
    suggested_links: list[SuggestedLink]
    prompt_cues: list[PromptCue] = Field(default_factory=list)


class _NoteContext(FrozenModel):
    path: str
    title: str | None
    page_type: str | None
    tags: list[str]
    headings: list[str]
    content: str
    content_hash: str
    links: list[str]


class VaultContextGraphBuilder(FrozenModel):
    note_repository: VaultNoteRepository

    def build_graph(self, command: ContextCommand) -> ContextGraph:
        all_notes = self._notes(path_prefix=None)
        scoped_notes = self._notes(path_prefix=command.path_prefix)
        notes_by_path = {note.path: note for note in all_notes}
        note_ids = self._note_ids(all_notes)

        if command.mode == "prompt":
            return self._build_prompt_graph(command, scoped_notes, notes_by_path, note_ids)

        remaining = command.limit
        orientation = self._orientation(notes_by_path, command.query, limit=min(3, remaining))
        remaining -= len(orientation)

        broken_links = self._broken_links(scoped_notes, note_ids, limit=remaining)
        remaining -= len(broken_links)

        link_targets = self._link_targets(scoped_notes, command.query, limit=remaining)
        remaining -= len(link_targets)

        suggested_links = self._suggested_links(
            scoped_notes,
            link_targets,
            notes_by_path,
            command.query,
            limit=remaining,
        )

        return ContextGraph(
            orientation=orientation,
            broken_links=broken_links,
            link_targets=link_targets,
            suggested_links=suggested_links,
        )

    def _build_prompt_graph(
        self,
        command: ContextCommand,
        scoped_notes: list[_NoteContext],
        notes_by_path: dict[str, _NoteContext],
        note_ids: dict[str, str],
    ) -> ContextGraph:
        remaining = command.limit
        link_targets = self._link_targets(scoped_notes, command.query, limit=remaining)
        remaining -= len(link_targets)

        suggested_links = self._suggested_links(
            scoped_notes,
            link_targets,
            notes_by_path,
            command.query,
            limit=remaining,
        )
        remaining -= len(suggested_links)

        orientation = self._orientation(notes_by_path, command.query, limit=min(3, remaining))
        remaining -= len(orientation)

        broken_links = self._broken_links(scoped_notes, note_ids, limit=remaining)
        prompt_cues = self._prompt_cues(scoped_notes, command.query, limit=command.limit)

        return ContextGraph(
            orientation=orientation,
            broken_links=broken_links,
            link_targets=link_targets,
            suggested_links=suggested_links,
            prompt_cues=prompt_cues,
        )

    def _notes(self, path_prefix: str | None) -> list[_NoteContext]:
        search_root = self.note_repository.resolve_search_root(path_prefix)
        notes: list[_NoteContext] = []
        for note_path in self.note_repository.markdown_notes(search_root):
            relative_path = self.note_repository.relative_path(note_path)
            content = self.note_repository.read_note(note_path)
            metadata = extract_note_metadata(content)
            notes.append(
                _NoteContext(
                    path=relative_path,
                    title=metadata.title,
                    page_type=metadata.page_type,
                    tags=metadata.tags,
                    headings=metadata.headings,
                    content=content,
                    content_hash=compute_sha256(content),
                    links=extract_wiki_links(content),
                )
            )
        return notes

    def _orientation(
        self,
        notes_by_path: dict[str, _NoteContext],
        query: str,
        *,
        limit: int,
    ) -> list[ContextReference]:
        references: list[ContextReference] = []
        for path in ORIENTATION_PATHS:
            if len(references) >= limit:
                break
            note = notes_by_path.get(path)
            if note is None:
                continue
            references.append(self._reference(note, relation="orientation", query=query))
        return references

    def _broken_links(
        self,
        notes: list[_NoteContext],
        note_ids: dict[str, str],
        *,
        limit: int,
    ) -> list[BrokenWikiLink]:
        broken_by_source_target: dict[tuple[str, str], BrokenWikiLink] = {}
        for note in notes:
            for raw_target in note.links:
                normalized_target = normalize_wiki_target(raw_target)
                if not normalized_target:
                    continue
                if self._target_key(normalized_target) in note_ids:
                    continue

                key = (note.path, normalized_target)
                existing = broken_by_source_target.get(key)
                if existing is not None:
                    broken_by_source_target[key] = existing.model_copy(
                        update={"occurrences": existing.occurrences + 1}
                    )
                    continue

                broken_by_source_target[key] = BrokenWikiLink(
                    source_path=note.path,
                    source_content_hash=note.content_hash,
                    target=raw_target,
                    normalized_target=normalized_target,
                    occurrences=1,
                    suggested_path=self._suggested_path(normalized_target),
                    followup_search=normalized_target,
                )

        return sorted(
            broken_by_source_target.values(),
            key=lambda link: (link.source_path, link.normalized_target),
        )[:limit]

    def _link_targets(
        self,
        notes: list[_NoteContext],
        query: str,
        *,
        limit: int,
    ) -> list[ContextReference]:
        terms = self._query_terms(query)
        references: list[ContextReference] = []
        for note in notes:
            relation = self._target_relation(note)
            if relation is None:
                continue
            if not self._matches_terms(note, terms):
                continue
            references.append(self._reference(note, relation=relation, query=query))

        return sorted(
            references,
            key=lambda reference: (self._relation_rank(reference), reference.path),
        )[:limit]

    def _suggested_links(
        self,
        notes: list[_NoteContext],
        link_targets: list[ContextReference],
        notes_by_path: dict[str, _NoteContext],
        query: str,
        *,
        limit: int,
    ) -> list[SuggestedLink]:
        if limit <= 0:
            return []

        terms = self._query_terms(query)
        suggestions: list[SuggestedLink] = []
        for source in notes:
            if not self._matches_terms(source, terms):
                continue
            linked_targets = {
                self._target_key(normalize_wiki_target(link)) for link in source.links
            }
            for target in link_targets:
                if len(suggestions) >= limit:
                    return suggestions
                if target.relation == "reference_note":
                    continue
                target_note = notes_by_path.get(target.path)
                if target_note is None or target_note.path == source.path:
                    continue
                if linked_targets.intersection(self._note_keys(target_note)):
                    continue

                reason = self._suggestion_reason(source, target_note, terms)
                if reason is None:
                    continue
                suggestions.append(
                    SuggestedLink(
                        source_path=source.path,
                        source_content_hash=source.content_hash,
                        target_path=target_note.path,
                        target_title=target_note.title,
                        relation=f"add_link_to_{target.relation}",
                        reason=reason,
                        followup_search=f"{source.path} {target_note.title or target_note.path}",
                    )
                )
        return suggestions

    def _reference(self, note: _NoteContext, *, relation: str, query: str) -> ContextReference:
        return ContextReference(
            path=note.path,
            title=note.title,
            page_type=note.page_type,
            tags=note.tags,
            content_hash=note.content_hash,
            relation=relation,
            followup_search=f"{query} {note.title or note.path}".strip(),
        )

    def _prompt_cues(
        self,
        notes: list[_NoteContext],
        query: str,
        *,
        limit: int,
    ) -> list[PromptCue]:
        terms = self._query_terms(query)
        cues: list[PromptCue] = []
        cues_by_kind: dict[str, int] = {kind: 0 for kind in PROMPT_MEMORY_KINDS}
        for note in notes:
            for cue in self._note_prompt_cues(note):
                if len(cues) >= limit:
                    return cues
                if cues_by_kind.get(cue.memory_kind, 0) >= PROMPT_CUE_LIMIT_PER_KIND:
                    continue
                if not self._cue_matches_terms(cue, terms):
                    continue
                cues.append(cue)
                cues_by_kind[cue.memory_kind] = cues_by_kind.get(cue.memory_kind, 0) + 1
        return cues

    def _note_prompt_cues(self, note: _NoteContext) -> list[PromptCue]:
        cues: list[PromptCue] = []
        in_prompt_hints = False
        for line in note.content.splitlines():
            stripped = line.strip()
            if stripped.startswith("## "):
                in_prompt_hints = stripped.lower() == "## prompt hints"
                continue
            if not in_prompt_hints or not stripped.startswith("- "):
                continue

            fields = self._prompt_hint_fields(stripped[2:])
            memory_kind = self._prompt_memory_kind(fields)
            if memory_kind is None:
                continue
            cues.append(self._prompt_cue(note, fields, memory_kind=memory_kind))
        return cues

    def _prompt_hint_fields(self, raw_bullet: str) -> dict[str, str]:
        fields: dict[str, str] = {}
        for raw_part in raw_bullet.split(";"):
            key, separator, value = raw_part.partition(":")
            if not separator:
                continue
            normalized_key = key.strip().lower().replace("-", "_").replace(" ", "_")
            normalized_value = value.strip().rstrip(".")
            if normalized_key and normalized_value:
                fields[normalized_key] = normalized_value
        return fields

    def _prompt_memory_kind(self, fields: dict[str, str]) -> str | None:
        raw_kind = fields.get("memory_kind") or fields.get("kind") or fields.get("memory")
        if raw_kind is None:
            return None
        normalized_kind = raw_kind.strip().lower().replace("-", "_").replace(" ", "_")
        if normalized_kind not in PROMPT_MEMORY_KINDS:
            return None
        return normalized_kind

    def _prompt_cue(
        self,
        note: _NoteContext,
        fields: dict[str, str],
        *,
        memory_kind: str,
    ) -> PromptCue:
        return PromptCue(
            path=note.path,
            title=note.title,
            content_hash=note.content_hash,
            memory_kind=memory_kind,
            evidence_status=fields.get("evidence_status", "verified"),
            updated=fields.get("updated"),
            review_after=fields.get("review_after"),
            confidence=fields.get("confidence"),
            scope=fields.get("scope"),
            applies_when=fields.get("applies_when"),
            do=fields.get("do"),
            avoid=fields.get("avoid"),
            check_before_acting=fields.get("check_before_acting"),
            prevention_cue=fields.get("prevention_cue"),
            evidence=fields.get("evidence"),
        )

    def _cue_matches_terms(self, cue: PromptCue, terms: list[str]) -> bool:
        haystack = " ".join(
            value
            for value in (
                cue.path,
                cue.title or "",
                cue.memory_kind,
                cue.scope or "",
                cue.applies_when or "",
                cue.do or "",
                cue.avoid or "",
                cue.check_before_acting or "",
                cue.prevention_cue or "",
                cue.evidence or "",
                cue.confidence or "",
            )
            if value
        ).lower()
        return any(term in haystack for term in terms)

    def _target_relation(self, note: _NoteContext) -> str | None:
        tags = {tag.lower() for tag in note.tags}
        page_type = (note.page_type or "").lower()
        if note.path.startswith("entities/") or page_type == "entity":
            return "entity_anchor"
        if "domain-rule" in tags or "domain-rules" in tags:
            return "domain_rule"
        if "code-style" in tags or "naming-convention" in tags:
            return "code_convention"
        if page_type in {"concept", "query", "comparison", "summary"}:
            return "reference_note"
        return None

    def _matches_terms(self, note: _NoteContext, terms: list[str]) -> bool:
        haystack = " ".join(
            [
                note.path,
                note.title or "",
                note.page_type or "",
                " ".join(note.tags),
                " ".join(note.headings),
                note.content,
            ]
        ).lower()
        return any(term in haystack for term in terms)

    def _suggestion_reason(
        self,
        source: _NoteContext,
        target: _NoteContext,
        terms: list[str],
    ) -> str | None:
        source_tags = {tag.lower() for tag in source.tags}
        target_tags = {tag.lower() for tag in target.tags}
        shared_tags = sorted(source_tags.intersection(target_tags))
        if shared_tags:
            return f"shared tags: {', '.join(shared_tags[:3])}"
        if self._matches_terms(target, terms):
            return "source and target both match the context query"
        return None

    def _note_ids(self, notes: list[_NoteContext]) -> dict[str, str]:
        note_ids: dict[str, str] = {}
        for note in notes:
            for key in self._note_keys(note):
                note_ids[key] = note.path
        return note_ids

    def _note_keys(self, note: _NoteContext) -> set[str]:
        relative_path = Path(note.path)
        keys = {
            relative_path.with_suffix("").as_posix(),
            relative_path.stem,
        }
        if note.title:
            keys.add(note.title)
        return {self._target_key(key) for key in keys if key}

    def _suggested_path(self, normalized_target: str) -> str:
        target = normalized_target.removesuffix(".md")
        if "/" in target:
            return f"{target}.md"
        return f"concepts/{target}.md"

    def _query_terms(self, query: str) -> list[str]:
        terms = [token.lower() for token in QUERY_TOKEN_PATTERN.findall(query) if len(token) > 1]
        return terms or [query.lower()]

    def _target_key(self, target: str) -> str:
        return target.strip().lower()

    def _relation_rank(self, reference: ContextReference) -> int:
        return {
            "entity_anchor": 0,
            "domain_rule": 1,
            "code_convention": 2,
            "reference_note": 3,
            "orientation": 4,
        }.get(reference.relation, 9)
