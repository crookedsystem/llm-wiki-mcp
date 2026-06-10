from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any, cast

import yaml
from yaml.error import YAMLError

from common.model import FrozenModel
from vault.constant.schema import (
    DATE_PATTERN,
    DEFAULT_ALLOWED_TYPES,
    LEVEL_TWO_HEADING,
    META_NOTE_PATHS,
    REQUIRED_RAW_FIELDS,
    REQUIRED_SYNTH_FIELDS,
    SYNTHESIZED_DIRS,
    SYNTHESIZED_TYPE_BY_DIR,
    TAG_PATTERN,
    TAG_TAXONOMY_HEADING,
    WIKILINK_PATTERN,
)
from vault.entity.vault_note import compute_sha256, parse_note
from vault.error.schema_validation_error import SchemaValidationError
from vault.infrastructure.repository.vault_note_repository import VaultNoteRepository
from vault.service.result.parsed_wiki_schema import ParsedWikiSchema
from vault.service.result.schema_validation_result import (
    SchemaValidationIssue,
    ValidationSummary,
    VaultValidationResult,
)
from vault.service.result.taxonomy_reconcile_result import TaxonomyReconcileResult
from vault.service.result.wiki_context_result import (
    WikiContext,
    WikiContextHealth,
    WikiContextIssueCandidate,
    WikiContextMap,
    WikiContextSummary,
    WikiPageContext,
    WikiPageDraft,
    WikiUpdateSuggestion,
)


class VaultSchemaService(FrozenModel):
    note_repository: VaultNoteRepository

    def validate_write(self, note_path: str, content: str) -> VaultValidationResult:
        issues = self._validate_write_issues(note_path, content)
        return _validation_result(issues)

    def ensure_valid_write(self, note_path: str, content: str) -> None:
        result = self.validate_write(note_path, content)
        if result.issues:
            raise SchemaValidationError(result.issues)

    def validate_vault(self, *, include_raw: bool = True) -> VaultValidationResult:
        issues: list[SchemaValidationIssue] = []
        schema_path = self.note_repository.vault_root / "SCHEMA.md"
        if schema_path.exists():
            issues.extend(self._validate_schema_note(schema_path.read_text(encoding="utf-8")))
        else:
            issues.append(
                SchemaValidationIssue(
                    code="schema_missing",
                    path="SCHEMA.md",
                    field="SCHEMA.md",
                    message="Vault schema file is required before validating wiki pages",
                )
            )

        for path in self.note_repository.markdown_notes():
            relative_path = self.note_repository.relative_path(path)
            if relative_path == "SCHEMA.md" or _is_meta_note_path(relative_path):
                continue
            if _is_raw_path(relative_path):
                if include_raw:
                    issues.extend(
                        self._validate_raw_note(relative_path, path.read_text(encoding="utf-8"))
                    )
                continue
            if _is_synthesized_path(relative_path):
                issues.extend(
                    self._validate_synthesized_note(
                        relative_path,
                        path.read_text(encoding="utf-8"),
                        self._parsed_schema(),
                    )
                )
                continue
            issues.append(
                SchemaValidationIssue(
                    code="unsupported_note_path",
                    path=relative_path,
                    field="note_path",
                    value=relative_path,
                    message=(
                        "Note path must be SCHEMA.md, index.md, log.md, raw/**, "
                        "entities/**, concepts/**, comparisons/**, queries/**, or _meta/**"
                    ),
                )
            )
        return _validation_result(issues)

    def wiki_context(
        self,
        *,
        recent_log_lines: int = 30,
        include_schema_rules: bool = True,
        include_index: bool = True,
    ) -> WikiContext:
        _ = include_schema_rules
        schema_text = self._read_optional_note("SCHEMA.md")
        index_text = self._read_optional_note("index.md") if include_index else ""
        log_text = self._read_optional_note("log.md")
        recent_log = _tail_nonempty_lines(log_text, recent_log_lines)
        parsed_schema = parse_schema_document(schema_text)
        validation = self.validate_vault()
        markdown_notes = self.note_repository.markdown_notes()
        relative_paths = [self.note_repository.relative_path(path) for path in markdown_notes]
        wiki_map, issue_candidates, update_suggestions = self._build_wiki_context_guidance(
            index_text=index_text,
            validation=validation,
        )
        return WikiContext(
            schema=schema_text,
            index=index_text,
            recent_log=recent_log,
            parsed_schema=parsed_schema,
            summary=WikiContextSummary(
                total_notes=len(relative_paths),
                synthesized_pages=sum(1 for path in relative_paths if _is_synthesized_path(path)),
                raw_sources=sum(1 for path in relative_paths if _is_raw_path(path)),
                last_log_entries=len(recent_log.splitlines()) if recent_log else 0,
            ),
            health=WikiContextHealth(
                schema_parse_ok=parsed_schema.schema_parse_ok,
                unknown_tag_count=validation.summary.unknown_tags,
                missing_frontmatter_count=validation.summary.missing_frontmatter,
            ),
            wiki_map=wiki_map,
            issue_candidates=issue_candidates,
            update_suggestions=update_suggestions,
        )

    def reconcile_taxonomy(
        self,
        *,
        apply: bool = False,
        decisions: dict[str, object] | None = None,
    ) -> TaxonomyReconcileResult:
        schema = self._parsed_schema()
        tag_usage = self._tag_usage_counts()
        decisions = decisions or {}
        add_tags = sorted(_string_list(decisions.get("add")))
        rename_tags = _string_mapping(decisions.get("rename"))
        remove_tags = set(_string_list(decisions.get("remove")))

        allowed_after_add = set(schema.allowed_tags) | set(add_tags) | set(rename_tags.values())
        unknown_tags = sorted(tag for tag in tag_usage if tag not in schema.allowed_tags)
        planned_changes: list[str] = []
        changed_files: list[str] = []

        taxonomy_tags_to_add = sorted(
            {tag for tag in [*add_tags, *rename_tags.values()] if tag not in schema.allowed_tags}
        )
        for tag in taxonomy_tags_to_add:
            planned_changes.append(f"add taxonomy tag: {tag}")
        for old_tag, new_tag in sorted(rename_tags.items()):
            planned_changes.append(f"rename tag: {old_tag} -> {new_tag}")
        for tag in sorted(remove_tags):
            planned_changes.append(f"remove tag: {tag}")

        if apply:
            schema_path = self.note_repository.vault_root / "SCHEMA.md"
            if taxonomy_tags_to_add:
                schema_path.write_text(
                    _schema_with_added_tags(
                        schema_path.read_text(encoding="utf-8"), taxonomy_tags_to_add
                    ),
                    encoding="utf-8",
                )
                changed_files.append("SCHEMA.md")

            for path in self.note_repository.markdown_notes():
                relative_path = self.note_repository.relative_path(path)
                if not _is_synthesized_path(relative_path):
                    continue
                content = path.read_text(encoding="utf-8")
                rewritten = _rewrite_frontmatter_tags(content, rename_tags, remove_tags)
                if rewritten != content:
                    path.write_text(rewritten, encoding="utf-8")
                    changed_files.append(relative_path)

        unresolved_unknown_tags = sorted(tag for tag in tag_usage if tag not in allowed_after_add)
        return TaxonomyReconcileResult(
            dry_run=not apply,
            unknown_tags=unknown_tags if not apply else unresolved_unknown_tags,
            tag_usage_counts=tag_usage,
            planned_changes=planned_changes,
            changed_files=changed_files,
        )

    def _validate_write_issues(self, note_path: str, content: str) -> list[SchemaValidationIssue]:
        if note_path == "SCHEMA.md":
            return self._validate_schema_note(content)
        if _is_meta_note_path(note_path):
            return []
        if _is_raw_path(note_path):
            return self._validate_raw_note(note_path, content)
        if _is_synthesized_path(note_path):
            return self._validate_synthesized_note(note_path, content, self._parsed_schema())
        if note_path.startswith("_meta/"):
            return []
        return [
            SchemaValidationIssue(
                code="unsupported_note_path",
                path=note_path,
                field="note_path",
                value=note_path,
                message=(
                    "Note path must be SCHEMA.md, index.md, log.md, raw/**, entities/**, "
                    "concepts/**, comparisons/**, queries/**, or _meta/**"
                ),
            )
        ]

    def _validate_schema_note(self, content: str) -> list[SchemaValidationIssue]:
        parsed = parse_schema_document(content)
        issues: list[SchemaValidationIssue] = []
        if "## Frontmatter" not in content:
            issues.append(
                SchemaValidationIssue(
                    code="schema_missing_frontmatter_section",
                    path="SCHEMA.md",
                    field="Frontmatter",
                    message="SCHEMA.md must define the synthesized page frontmatter contract",
                )
            )
        if not parsed.tag_taxonomy:
            issues.append(
                SchemaValidationIssue(
                    code="schema_missing_tag_taxonomy",
                    path="SCHEMA.md",
                    field="Tag taxonomy",
                    message="SCHEMA.md must define a Tag taxonomy section before tags are used",
                )
            )
        return issues

    def _validate_synthesized_note(
        self,
        note_path: str,
        content: str,
        schema: ParsedWikiSchema,
    ) -> list[SchemaValidationIssue]:
        frontmatter, _body, issues = _frontmatter_mapping(note_path, content)
        if frontmatter is None:
            return issues

        for field_name in REQUIRED_SYNTH_FIELDS:
            if field_name not in frontmatter:
                issues.append(
                    SchemaValidationIssue(
                        code="missing_required_field",
                        path=note_path,
                        field=field_name,
                        message=f"Synthesized pages must include frontmatter field: {field_name}",
                    )
                )

        page_type = _scalar_string(frontmatter.get("type"))
        if page_type is not None:
            if page_type not in schema.allowed_types:
                issues.append(
                    SchemaValidationIssue(
                        code="invalid_type",
                        path=note_path,
                        field="type",
                        value=page_type,
                        message="Page type is not declared by SCHEMA.md allowed type values",
                    )
                )
            allowed_types_for_path = _allowed_types_for_path(note_path)
            if allowed_types_for_path and page_type not in allowed_types_for_path:
                issues.append(
                    SchemaValidationIssue(
                        code="invalid_type_for_path",
                        path=note_path,
                        field="type",
                        value=page_type,
                        message=(
                            f"Path {note_path} only allows type values: "
                            f"{', '.join(sorted(allowed_types_for_path))}"
                        ),
                    )
                )

        for field_name in ("created", "updated"):
            date_value = _date_string(frontmatter.get(field_name))
            if field_name in frontmatter and (
                date_value is None or not DATE_PATTERN.match(date_value)
            ):
                issues.append(
                    SchemaValidationIssue(
                        code="invalid_date",
                        path=note_path,
                        field=field_name,
                        value=str(frontmatter.get(field_name)),
                        message=f"{field_name} must use YYYY-MM-DD format",
                    )
                )

        tags = _frontmatter_list(frontmatter.get("tags"))
        if "tags" in frontmatter and tags is None:
            issues.append(
                SchemaValidationIssue(
                    code="invalid_field_type",
                    path=note_path,
                    field="tags",
                    message="tags must be a YAML list",
                )
            )
        for tag in tags or []:
            if tag not in schema.allowed_tags:
                issues.append(
                    SchemaValidationIssue(
                        code="unknown_tag",
                        path=note_path,
                        field="tags",
                        value=tag,
                        message="Tag is not declared in SCHEMA.md taxonomy",
                    )
                )

        sources = _frontmatter_list(frontmatter.get("sources"))
        if "sources" in frontmatter and sources is None:
            issues.append(
                SchemaValidationIssue(
                    code="invalid_field_type",
                    path=note_path,
                    field="sources",
                    message="sources must be a YAML list",
                )
            )
        elif sources == []:
            issues.append(
                SchemaValidationIssue(
                    code="empty_sources",
                    path=note_path,
                    field="sources",
                    message="sources must include at least one raw note path or source URL",
                )
            )

        confidence = _scalar_string(frontmatter.get("confidence"))
        if confidence is not None and confidence not in {"high", "medium", "low"}:
            issues.append(
                SchemaValidationIssue(
                    code="invalid_confidence",
                    path=note_path,
                    field="confidence",
                    value=confidence,
                    message="confidence must be one of: high, medium, low",
                )
            )
        contested = frontmatter.get("contested")
        if "contested" in frontmatter and not isinstance(contested, bool):
            issues.append(
                SchemaValidationIssue(
                    code="invalid_contested",
                    path=note_path,
                    field="contested",
                    value=str(contested),
                    message="contested must be a YAML boolean",
                )
            )
        return issues

    def _validate_raw_note(self, note_path: str, content: str) -> list[SchemaValidationIssue]:
        frontmatter, body, issues = _frontmatter_mapping(note_path, content)
        if frontmatter is None:
            return issues

        for field_name in REQUIRED_RAW_FIELDS:
            if field_name not in frontmatter:
                code = f"raw_missing_{field_name}"
                issues.append(
                    SchemaValidationIssue(
                        code=code,
                        path=note_path,
                        field=field_name,
                        message=f"Raw notes must include frontmatter field: {field_name}",
                    )
                )

        ingested = _date_string(frontmatter.get("ingested"))
        if "ingested" in frontmatter and (ingested is None or not DATE_PATTERN.match(ingested)):
            issues.append(
                SchemaValidationIssue(
                    code="invalid_ingested_date",
                    path=note_path,
                    field="ingested",
                    value=str(frontmatter.get("ingested")),
                    message="ingested must use YYYY-MM-DD format",
                )
            )

        if not body.strip():
            issues.append(
                SchemaValidationIssue(
                    code="raw_empty_body",
                    path=note_path,
                    field="body",
                    message="Raw note body must not be empty",
                )
            )

        expected_hash = _scalar_string(frontmatter.get("sha256"))
        if expected_hash is not None:
            actual_hash = compute_sha256(body)
            if expected_hash != actual_hash:
                issues.append(
                    SchemaValidationIssue(
                        code="raw_sha256_mismatch",
                        path=note_path,
                        field="sha256",
                        value=expected_hash,
                        message="raw sha256 must equal SHA-256 of the body after frontmatter",
                    )
                )
        return issues

    def _parsed_schema(self) -> ParsedWikiSchema:
        return parse_schema_document(self._read_optional_note("SCHEMA.md"))

    def _read_optional_note(self, relative_path: str) -> str:
        path = self.note_repository.vault_root / relative_path
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def _tag_usage_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for path in self.note_repository.markdown_notes():
            relative_path = self.note_repository.relative_path(path)
            if not _is_synthesized_path(relative_path):
                continue
            frontmatter, _body, _issues = _frontmatter_mapping(
                relative_path,
                path.read_text(encoding="utf-8"),
            )
            if frontmatter is None:
                continue
            tags = _frontmatter_list(frontmatter.get("tags")) or []
            for tag in tags:
                counts[tag] = counts.get(tag, 0) + 1
        return dict(sorted(counts.items()))

    def _build_wiki_context_guidance(
        self,
        *,
        index_text: str,
        validation: VaultValidationResult,
    ) -> tuple[WikiContextMap, list[WikiContextIssueCandidate], list[WikiUpdateSuggestion]]:
        page_drafts: dict[str, WikiPageDraft] = {}
        raw_sources: list[str] = []
        for path in self.note_repository.markdown_notes():
            relative_path = self.note_repository.relative_path(path)
            if _is_raw_path(relative_path):
                raw_sources.append(relative_path)
                continue
            if not _is_synthesized_path(relative_path):
                continue

            content = path.read_text(encoding="utf-8")
            frontmatter, body, _issues = _frontmatter_mapping(relative_path, content)
            page_drafts[relative_path] = WikiPageDraft(
                path=relative_path,
                title=_context_page_title(relative_path, frontmatter, body),
                page_type=_scalar_string(frontmatter.get("type")) if frontmatter else None,
                tags=(_frontmatter_list(frontmatter.get("tags")) or []) if frontmatter else [],
                sources=(_frontmatter_list(frontmatter.get("sources")) or [])
                if frontmatter
                else [],
                body=body,
            )

        page_paths = sorted(page_drafts)
        link_graph: dict[str, list[str]] = {path: [] for path in page_paths}
        inbound_links: dict[str, list[str]] = {path: [] for path in page_paths}
        issue_candidates: list[WikiContextIssueCandidate] = []
        update_suggestions: list[WikiUpdateSuggestion] = []

        for page_path in page_paths:
            for target in _extract_wikilink_targets(page_drafts[page_path].body):
                resolved_targets = _resolve_wikilink_target(target, page_paths)
                if len(resolved_targets) == 1:
                    resolved_target = resolved_targets[0]
                    if (
                        resolved_target != page_path
                        and resolved_target not in link_graph[page_path]
                    ):
                        link_graph[page_path].append(resolved_target)
                    continue
                if not resolved_targets:
                    issue_candidates.append(
                        WikiContextIssueCandidate(
                            code="broken_wikilink",
                            path=page_path,
                            message=f"Wikilink [[{target}]] does not resolve to a synthesized page",
                            related_paths=[target],
                        )
                    )
                    update_suggestions.append(
                        WikiUpdateSuggestion(
                            action="repair_wikilink",
                            path=page_path,
                            reason=f"Replace or create the unresolved wikilink [[{target}]]",
                            related_paths=[target],
                        )
                    )
                    continue
                issue_candidates.append(
                    WikiContextIssueCandidate(
                        code="ambiguous_wikilink",
                        path=page_path,
                        message=f"Wikilink [[{target}]] matches multiple synthesized pages",
                        related_paths=resolved_targets,
                    )
                )
                update_suggestions.append(
                    WikiUpdateSuggestion(
                        action="disambiguate_wikilink",
                        path=page_path,
                        reason=f"Use an explicit path or title for ambiguous wikilink [[{target}]]",
                        related_paths=resolved_targets,
                    )
                )

        link_graph = {path: sorted(targets) for path, targets in sorted(link_graph.items())}
        for source_path, target_paths in link_graph.items():
            for target_path in target_paths:
                inbound_links[target_path].append(source_path)
        inbound_links = {path: sorted(sources) for path, sources in sorted(inbound_links.items())}

        raw_source_set = set(raw_sources)
        referenced_raw_sources: set[str] = set()
        pages_by_type: dict[str, list[str]] = {}
        for page_path in page_paths:
            draft = page_drafts[page_path]
            pages_by_type.setdefault(draft.page_type or "unknown", []).append(page_path)
            for source in draft.sources:
                if not source.startswith("raw/"):
                    continue
                if source in raw_source_set:
                    referenced_raw_sources.add(source)
                    continue
                issue_candidates.append(
                    WikiContextIssueCandidate(
                        code="missing_raw_source",
                        path=page_path,
                        message=f"Frontmatter source {source} does not exist in raw/",
                        severity="error",
                        related_paths=[source],
                    )
                )
                update_suggestions.append(
                    WikiUpdateSuggestion(
                        action="repair_source_reference",
                        path=page_path,
                        reason=f"Add missing raw source {source} or replace the source reference",
                        related_paths=[source],
                    )
                )
        pages_by_type = {key: sorted(value) for key, value in sorted(pages_by_type.items())}

        pages: list[WikiPageContext] = []
        for page_path in page_paths:
            draft = page_drafts[page_path]
            indexed = _index_mentions_page(index_text, page_path)
            pages.append(
                WikiPageContext(
                    path=page_path,
                    title=draft.title,
                    page_type=draft.page_type,
                    tags=draft.tags,
                    sources=draft.sources,
                    outbound_links=link_graph[page_path],
                    inbound_links=inbound_links[page_path],
                    indexed=indexed,
                )
            )
            related_pages = _related_page_candidates(page_path, page_drafts)
            if not indexed:
                issue_candidates.append(
                    WikiContextIssueCandidate(
                        code="unindexed_page",
                        path=page_path,
                        message="Synthesized page is not listed in index.md",
                    )
                )
                update_suggestions.append(
                    WikiUpdateSuggestion(
                        action="add_index_entry",
                        path=page_path,
                        reason="Add the synthesized page to index.md under the right section",
                    )
                )
            if len(link_graph[page_path]) < 2:
                issue_candidates.append(
                    WikiContextIssueCandidate(
                        code="underlinked_page",
                        path=page_path,
                        message="Synthesized page has fewer than two outbound wikilinks",
                        related_paths=related_pages,
                    )
                )
                update_suggestions.append(
                    WikiUpdateSuggestion(
                        action="add_cross_links",
                        path=page_path,
                        reason=(
                            "Add at least two relevant outbound wikilinks if the page "
                            "should stay active"
                        ),
                        related_paths=related_pages,
                    )
                )
            if not inbound_links[page_path]:
                issue_candidates.append(
                    WikiContextIssueCandidate(
                        code="orphan_page",
                        path=page_path,
                        message=(
                            "Synthesized page has no inbound wikilinks from other synthesized pages"
                        ),
                        related_paths=related_pages,
                    )
                )
                update_suggestions.append(
                    WikiUpdateSuggestion(
                        action="connect_or_archive_page",
                        path=page_path,
                        reason=(
                            "Add inbound links from related pages, or archive if it is "
                            "no longer useful"
                        ),
                        related_paths=related_pages,
                    )
                )

        for source_path, target_paths in link_graph.items():
            for target_path in target_paths:
                if source_path in link_graph[target_path]:
                    continue
                issue_candidates.append(
                    WikiContextIssueCandidate(
                        code="missing_backlink",
                        path=target_path,
                        message="Linked page does not link back to the referring page",
                        related_paths=[source_path],
                    )
                )
                update_suggestions.append(
                    WikiUpdateSuggestion(
                        action="add_backlink",
                        path=target_path,
                        reason=(
                            "Consider adding a backlink to the referring page for "
                            "bidirectional navigation"
                        ),
                        related_paths=[source_path],
                    )
                )

        for raw_source in sorted(raw_source_set - referenced_raw_sources):
            issue_candidates.append(
                WikiContextIssueCandidate(
                    code="raw_source_without_synthesis",
                    path=raw_source,
                    message="Raw source is not referenced by any synthesized wiki page",
                )
            )
            update_suggestions.append(
                WikiUpdateSuggestion(
                    action="synthesize_or_link_raw_source",
                    path=raw_source,
                    reason=(
                        "Create or update a synthesized page that cites this raw source "
                        "if it is relevant"
                    ),
                )
            )

        for issue in validation.issues:
            issue_candidates.append(
                WikiContextIssueCandidate(
                    code=f"schema_{issue.code}",
                    path=issue.path,
                    message=issue.message,
                    severity=issue.severity,
                    related_paths=[issue.value] if issue.value else [],
                )
            )
            update_suggestions.append(
                WikiUpdateSuggestion(
                    action="repair_schema_issue",
                    path=issue.path,
                    reason=issue.message,
                    related_paths=[issue.value] if issue.value else [],
                )
            )

        _append_duplicate_title_guidance(page_drafts, issue_candidates, update_suggestions)
        return (
            WikiContextMap(
                pages=pages,
                pages_by_type=pages_by_type,
                raw_sources=sorted(raw_sources),
                link_graph=link_graph,
            ),
            _deduplicate_issue_candidates(issue_candidates),
            _deduplicate_update_suggestions(update_suggestions),
        )


def parse_schema_document(content: str) -> ParsedWikiSchema:
    tag_taxonomy = _extract_tag_taxonomy(content)
    allowed_tags = sorted({tag for tags in tag_taxonomy.values() for tag in tags})
    allowed_types = _extract_allowed_types(content) or list(DEFAULT_ALLOWED_TYPES)
    return ParsedWikiSchema(
        schema_parse_ok=bool(content and tag_taxonomy),
        allowed_types=allowed_types,
        required_synthesized_frontmatter=list(REQUIRED_SYNTH_FIELDS),
        required_raw_frontmatter=list(REQUIRED_RAW_FIELDS),
        tag_taxonomy=tag_taxonomy,
        allowed_tags=allowed_tags,
    )


def _frontmatter_mapping(
    note_path: str,
    content: str,
) -> tuple[dict[str, Any] | None, str, list[SchemaValidationIssue]]:
    parsed = parse_note(content)
    if parsed.frontmatter is None:
        return (
            None,
            parsed.body,
            [
                SchemaValidationIssue(
                    code="missing_frontmatter",
                    path=note_path,
                    field="frontmatter",
                    message="Markdown note must start with YAML frontmatter delimited by ---",
                )
            ],
        )
    try:
        loaded = yaml.safe_load(parsed.frontmatter) or {}
    except YAMLError as error:
        return (
            None,
            parsed.body,
            [
                SchemaValidationIssue(
                    code="invalid_yaml_frontmatter",
                    path=note_path,
                    field="frontmatter",
                    message=f"YAML frontmatter could not be parsed: {error}",
                )
            ],
        )
    if not isinstance(loaded, dict):
        return (
            None,
            parsed.body,
            [
                SchemaValidationIssue(
                    code="invalid_yaml_frontmatter",
                    path=note_path,
                    field="frontmatter",
                    message="YAML frontmatter must be a mapping/object",
                )
            ],
        )
    return cast(dict[str, Any], loaded), parsed.body, []


def _validation_result(issues: list[SchemaValidationIssue]) -> VaultValidationResult:
    return VaultValidationResult(
        issues=issues,
        summary=ValidationSummary(
            missing_frontmatter=_count_code(issues, "missing_frontmatter"),
            missing_required_fields=_count_code(issues, "missing_required_field"),
            unknown_tags=_count_code(issues, "unknown_tag"),
            invalid_type_for_path=_count_code(issues, "invalid_type_for_path"),
            raw_missing_sha256=_count_code(issues, "raw_missing_sha256"),
            raw_sha256_mismatch=_count_code(issues, "raw_sha256_mismatch"),
            empty_sources=_count_code(issues, "empty_sources"),
            issue_count=len(issues),
        ),
    )


def _count_code(issues: list[SchemaValidationIssue], code: str) -> int:
    return sum(1 for issue in issues if issue.code == code)


def _extract_allowed_types(content: str) -> list[str]:
    match = re.search(r"Allowed `type` values:\s*([^\n]+)", content)
    if match is None:
        return []
    return [
        token for token in _extract_tags_from_text(match.group(1)) if token in DEFAULT_ALLOWED_TYPES
    ]


def _extract_tag_taxonomy(content: str) -> dict[str, list[str]]:
    lines = content.splitlines()
    taxonomy_lines: list[str] = []
    in_taxonomy = False
    for line in lines:
        if TAG_TAXONOMY_HEADING.match(line.strip()):
            in_taxonomy = True
            continue
        if in_taxonomy and LEVEL_TWO_HEADING.match(line.strip()):
            break
        if in_taxonomy:
            taxonomy_lines.append(line)

    taxonomy: dict[str, list[str]] = {}
    current_section = "General"
    in_fence = False
    for raw_line in taxonomy_lines:
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped or stripped.startswith("#"):
            continue
        if stripped.endswith(":") and not stripped.startswith("-"):
            current_section = stripped[:-1].strip() or current_section
            taxonomy.setdefault(current_section, [])
            continue
        if not stripped.startswith("-"):
            continue

        item = stripped[1:].strip()
        if not item or item.startswith("["):
            continue
        values = item
        if ":" in item:
            raw_section, values = item.split(":", 1)
            current_section = raw_section.strip().strip("`") or current_section
        tags = _extract_tags_from_text(values)
        if not tags:
            continue
        section_tags = taxonomy.setdefault(current_section, [])
        for tag in tags:
            if tag not in section_tags:
                section_tags.append(tag)

    return {section: sorted(tags) for section, tags in taxonomy.items() if tags}


def _extract_tags_from_text(text: str) -> list[str]:
    code_tags = [tag for tag in re.findall(r"`([^`]+)`", text) if TAG_PATTERN.match(tag)]
    if code_tags:
        return code_tags

    candidates = [part.strip().strip("`.;") for part in text.split(",")]
    if len(candidates) == 1:
        single = candidates[0]
        return [single] if TAG_PATTERN.match(single) else []
    return [candidate for candidate in candidates if TAG_PATTERN.match(candidate)]


def _allowed_types_for_path(note_path: str) -> set[str]:
    first_part = Path(note_path).parts[0]
    return SYNTHESIZED_TYPE_BY_DIR.get(first_part, set())


def _is_synthesized_path(note_path: str) -> bool:
    parts = Path(note_path).parts
    return bool(parts) and parts[0] in SYNTHESIZED_DIRS


def _is_raw_path(note_path: str) -> bool:
    parts = Path(note_path).parts
    return bool(parts) and parts[0] == "raw"


def _is_meta_note_path(note_path: str) -> bool:
    return note_path in META_NOTE_PATHS or note_path.startswith("_meta/")


def _scalar_string(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _date_string(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, date):
        return value.isoformat()
    return None


def _frontmatter_list(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            return None
        result.append(item)
    return result


def _tail_nonempty_lines(content: str, line_count: int) -> str:
    lines = [line for line in content.splitlines() if line.strip()]
    if line_count <= 0:
        return ""
    return "\n".join(lines[-line_count:])


def _context_page_title(
    note_path: str,
    frontmatter: dict[str, Any] | None,
    body: str,
) -> str:
    if frontmatter is not None:
        title = _scalar_string(frontmatter.get("title"))
        if title:
            return title
    heading_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    if heading_match:
        return heading_match.group(1).strip()
    return Path(note_path).stem.replace("-", " ").title()


def _extract_wikilink_targets(body: str) -> list[str]:
    targets: set[str] = set()
    for match in WIKILINK_PATTERN.finditer(body):
        target = match.group(1).strip()
        if target:
            targets.add(target)
    return sorted(targets)


def _resolve_wikilink_target(target: str, page_paths: list[str]) -> list[str]:
    normalized = target.strip().strip("/")
    if normalized.endswith(".md"):
        normalized = normalized[:-3]
    normalized_lower = normalized.lower()
    candidates: set[str] = set()
    for page_path in page_paths:
        page_without_suffix = page_path[:-3] if page_path.endswith(".md") else page_path
        values = {
            page_path,
            page_without_suffix,
            Path(page_path).stem,
        }
        if normalized in values or normalized_lower in {value.lower() for value in values}:
            candidates.add(page_path)
    return sorted(candidates)


def _index_mentions_page(index_text: str, page_path: str) -> bool:
    page_without_suffix = page_path[:-3] if page_path.endswith(".md") else page_path
    stem = Path(page_path).stem
    return any(
        marker in index_text
        for marker in (
            page_path,
            page_without_suffix,
            f"[[{page_path}]]",
            f"[[{page_without_suffix}]]",
            f"[[{stem}]]",
        )
    )


def _related_page_candidates(
    page_path: str,
    page_drafts: dict[str, WikiPageDraft],
    *,
    limit: int = 5,
) -> list[str]:
    current = page_drafts[page_path]
    ranked: list[tuple[int, str]] = []
    current_tags = set(current.tags)
    current_sources = set(current.sources)
    for candidate_path, candidate in page_drafts.items():
        if candidate_path == page_path:
            continue
        score = len(current_tags & set(candidate.tags)) * 3
        if current.page_type is not None and current.page_type == candidate.page_type:
            score += 2
        if current_sources & set(candidate.sources):
            score += 1
        if score > 0:
            ranked.append((-score, candidate_path))
    return [candidate_path for _score, candidate_path in sorted(ranked)[:limit]]


def _append_duplicate_title_guidance(
    page_drafts: dict[str, WikiPageDraft],
    issue_candidates: list[WikiContextIssueCandidate],
    update_suggestions: list[WikiUpdateSuggestion],
) -> None:
    title_paths: dict[str, list[str]] = {}
    for page_path, draft in page_drafts.items():
        title_paths.setdefault(draft.title.casefold(), []).append(page_path)
    for paths in title_paths.values():
        if len(paths) < 2:
            continue
        sorted_paths = sorted(paths)
        issue_candidates.append(
            WikiContextIssueCandidate(
                code="duplicate_title",
                path=sorted_paths[0],
                message="Multiple synthesized pages share the same title",
                related_paths=sorted_paths[1:],
            )
        )
        update_suggestions.append(
            WikiUpdateSuggestion(
                action="merge_or_disambiguate_duplicate_pages",
                path=sorted_paths[0],
                reason=(
                    "Merge duplicate pages or rename them so the entity/concept map is unambiguous"
                ),
                related_paths=sorted_paths[1:],
            )
        )


def _deduplicate_issue_candidates(
    issues: list[WikiContextIssueCandidate],
) -> list[WikiContextIssueCandidate]:
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    deduplicated: list[WikiContextIssueCandidate] = []
    for issue in issues:
        key = (issue.code, issue.path, tuple(issue.related_paths))
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(issue)
    return deduplicated


def _deduplicate_update_suggestions(
    suggestions: list[WikiUpdateSuggestion],
) -> list[WikiUpdateSuggestion]:
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    deduplicated: list[WikiUpdateSuggestion] = []
    for suggestion in suggestions:
        key = (suggestion.action, suggestion.path, tuple(suggestion.related_paths))
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(suggestion)
    return deduplicated


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _string_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for key, mapped_value in value.items():
        if isinstance(key, str) and isinstance(mapped_value, str):
            result[key] = mapped_value
    return result


def _schema_with_added_tags(content: str, tags: list[str]) -> str:
    tags_to_add = [tag for tag in tags if TAG_PATTERN.match(tag)]
    if not tags_to_add:
        return content
    addition = f"- Added: {', '.join(tags_to_add)}"
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if TAG_TAXONOMY_HEADING.match(line.strip()):
            insert_at = index + 1
            while insert_at < len(lines) and not lines[insert_at].strip():
                insert_at += 1
            lines.insert(insert_at, addition)
            return "\n".join(lines) + "\n"
    return f"{content.rstrip()}\n\n## Tag taxonomy\n{addition}\n"


def _rewrite_frontmatter_tags(
    content: str,
    rename_tags: dict[str, str],
    remove_tags: set[str],
) -> str:
    if not rename_tags and not remove_tags:
        return content
    frontmatter, body, issues = _frontmatter_mapping("<rewrite>", content)
    if frontmatter is None or issues:
        return content
    tags = _frontmatter_list(frontmatter.get("tags"))
    if tags is None:
        return content
    rewritten_tags: list[str] = []
    for tag in tags:
        rewritten = rename_tags.get(tag, tag)
        if rewritten in remove_tags:
            continue
        if rewritten not in rewritten_tags:
            rewritten_tags.append(rewritten)
    if rewritten_tags == tags:
        return content
    frontmatter["tags"] = rewritten_tags
    dumped_frontmatter = yaml.safe_dump(
        frontmatter,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    return f"---\n{dumped_frontmatter}---\n{body}"
