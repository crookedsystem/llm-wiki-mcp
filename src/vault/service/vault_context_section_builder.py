from common.model import FrozenModel
from vault.service.command.context_command import ContextCommand
from vault.service.command.search_notes_command import SearchNotesCommand
from vault.service.result.context_result import ContextNote, ContextSection
from vault.service.result.search_notes_result import NoteSearchResult
from vault.service.vault_context_spec import SECTION_SPECS_BY_MODE, ContextSectionSpec
from vault.service.vault_search_service import VaultSearchService


class VaultContextSectionBuilder(FrozenModel):
    search_service: VaultSearchService

    def build_sections(self, command: ContextCommand) -> list[ContextSection]:
        seen_paths: set[str] = set()
        total_count = 0
        sections: list[ContextSection] = []

        for spec in SECTION_SPECS_BY_MODE[command.mode]:
            remaining = command.limit - total_count
            if remaining <= 0:
                sections.append(ContextSection(name=spec.name, purpose=spec.purpose, notes=[]))
                continue

            notes = self._section_notes(
                command,
                spec,
                seen_paths=seen_paths,
                limit=min(spec.quota, remaining),
            )
            total_count += len(notes)
            sections.append(ContextSection(name=spec.name, purpose=spec.purpose, notes=notes))

        return sections

    def _section_notes(
        self,
        command: ContextCommand,
        spec: ContextSectionSpec,
        *,
        seen_paths: set[str],
        limit: int,
    ) -> list[ContextNote]:
        if spec.explicit_paths:
            return self._explicit_path_notes(command, spec, seen_paths=seen_paths, limit=limit)

        query = VaultContextSectionBuilder._bucket_query(command.query, spec.query_terms)
        path_prefix = command.path_prefix or spec.path_prefix
        result = self.search_service.search_notes(
            SearchNotesCommand(query=query, limit=limit, path_prefix=path_prefix)
        )

        notes: list[ContextNote] = []
        for search_note in result.results:
            if search_note.path in seen_paths:
                continue
            seen_paths.add(search_note.path)
            notes.append(VaultContextSectionBuilder._context_note(search_note, spec))
        return notes

    def _explicit_path_notes(
        self,
        command: ContextCommand,
        spec: ContextSectionSpec,
        *,
        seen_paths: set[str],
        limit: int,
    ) -> list[ContextNote]:
        query = VaultContextSectionBuilder._bucket_query(command.query, spec.query_terms)
        notes: list[ContextNote] = []
        for path in spec.explicit_paths:
            if len(notes) >= limit:
                break
            result = self.search_service.search_notes(
                SearchNotesCommand(query=query, limit=1, path_prefix=path)
            )
            for search_note in result.results:
                if search_note.path in seen_paths:
                    continue
                seen_paths.add(search_note.path)
                notes.append(VaultContextSectionBuilder._context_note(search_note, spec))
                break
        return notes

    @staticmethod
    def _bucket_query(query: str, query_terms: tuple[str, ...]) -> str:
        terms = [term for term in query_terms if term]
        if not terms:
            return query
        return f"{query} {' '.join(terms)}"

    @staticmethod
    def _context_note(search_note: NoteSearchResult, spec: ContextSectionSpec) -> ContextNote:
        return ContextNote(
            path=search_note.path,
            title=search_note.title,
            page_type=search_note.page_type,
            tags=search_note.tags,
            score=search_note.score,
            content_hash=search_note.content_hash,
            matches=search_note.matches,
            why_included=f"{spec.name}: {spec.purpose}",
        )
