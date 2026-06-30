from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

from prompts.agent_hook import (
    CONTEXT_BLOCK_CLOSE,
    CONTEXT_BLOCK_OPEN,
    CONTEXT_EMPTY_TEMPLATE,
    CONTEXT_ERROR_TEMPLATE,
    CONTEXT_FOOTER,
    CONTEXT_HEADER_TEMPLATE,
    CONTEXT_RESULTS_INTRO,
)

from agent_hooks.llm_wiki_context_payload import is_link_context_payload

DEFAULT_LIMIT = 12
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
LEGACY_PROMPT_CUE_LANES = ("person_tone", "project_conventions", "repeated_mistakes")
PROMPT_CUE_LIMIT_PER_KIND = 3


def format_context_error(server_name: str, server_url: str, exc: Exception) -> str:
    del server_name, server_url
    return CONTEXT_ERROR_TEMPLATE.format(
        error_type=type(exc).__name__,
    )


def format_context_block(
    server_name: str,
    server_url: str,
    payload: Mapping[str, Any],
    *,
    max_results: int = DEFAULT_LIMIT,
) -> str:
    if is_link_context_payload(payload):
        return format_link_context_block(
            server_name,
            server_url,
            payload,
            max_results=max_results,
        )

    results = payload.get("results")
    if not isinstance(results, list) or not results:
        return CONTEXT_EMPTY_TEMPLATE

    lines = [
        CONTEXT_BLOCK_OPEN,
        CONTEXT_HEADER_TEMPLATE.format(server_name=server_name, server_url=server_url),
        CONTEXT_RESULTS_INTRO,
    ]
    for result in results[:max_results]:
        if not isinstance(result, Mapping):
            continue
        path = _clean_text(result.get("path") or "(unknown)")
        title = _clean_text(result.get("title") or path)
        page_type = _clean_text(result.get("page_type") or "unknown")
        content_hash = _clean_text(result.get("content_hash") or "")
        raw_tags = result.get("tags")
        tags = raw_tags if isinstance(raw_tags, list) else []
        tag_suffix = f" tags={','.join(_clean_text(tag) for tag in tags[:5])}" if tags else ""
        hash_suffix = f" hash={content_hash[:12]}" if content_hash else ""
        lines.append(
            f"- [[{path.removesuffix('.md')}]] — {title} ({page_type}{tag_suffix}{hash_suffix})"
        )
        raw_matches = result.get("matches")
        matches = raw_matches if isinstance(raw_matches, list) else []
        for match in matches[:2]:
            if not isinstance(match, Mapping):
                continue
            snippet = _clean_text(match.get("snippet") or "")
            line = match.get("line")
            if snippet:
                lines.append(f"  - L{line}: {snippet[:240]}")

    lines.extend([CONTEXT_FOOTER, CONTEXT_BLOCK_CLOSE])
    return "\n".join(lines)


def format_link_context_block(
    server_name: str,
    server_url: str,
    payload: Mapping[str, Any],
    *,
    max_results: int,
) -> str:
    mode = str(payload.get("mode") or "prompt")
    lines = [
        CONTEXT_BLOCK_OPEN,
        CONTEXT_HEADER_TEMPLATE.format(server_name=server_name, server_url=server_url),
        f"Wiki link context from `kb_context` (mode={mode}):",
    ]

    if mode == "prompt":
        lines.append(
            "Prompt context is advisory: use only directly scoped link targets or suggested links."
        )
    else:
        _append_usage_and_entity_guidance(lines, payload)

    printed = 0
    if mode == "prompt":
        printed += _append_prompt_cues(lines, payload, max_results=max_results)
    printed += _append_link_context(
        lines,
        payload,
        mode=mode,
        max_results=max_results - printed,
    )
    if printed == 0:
        lines.append("No link context candidates were found; use kb_search_notes for evidence.")

    lines.extend([CONTEXT_FOOTER, CONTEXT_BLOCK_CLOSE])
    return "\n".join(lines)


def _append_prompt_cues(
    lines: list[str],
    payload: Mapping[str, Any],
    *,
    max_results: int,
) -> int:
    if max_results <= 0:
        return 0

    prompt_cues = payload.get("prompt_cues")
    if isinstance(prompt_cues, list) and prompt_cues:
        return _append_prompt_cue_list(lines, prompt_cues, max_results=max_results)

    return _append_legacy_prompt_cues(lines, payload, max_results=max_results)


def _append_prompt_cue_list(
    lines: list[str],
    cues: list[Any],
    *,
    max_results: int,
) -> int:
    printed = 0
    printed_by_kind: dict[str, int] = {}
    sorted_cues = sorted(cues, key=_prompt_cue_sort_key)
    for cue in sorted_cues:
        if printed >= max_results:
            return printed
        if not isinstance(cue, Mapping):
            continue
        memory_kind = _clean_text(cue.get("memory_kind") or "semantic_fact")[:64]
        if printed_by_kind.get(memory_kind, 0) >= PROMPT_CUE_LIMIT_PER_KIND:
            continue
        if printed_by_kind.get(memory_kind, 0) == 0:
            lines.append(memory_kind)
        lines.extend(_format_prompt_cue(cue))
        printed += 1
        printed_by_kind[memory_kind] = printed_by_kind.get(memory_kind, 0) + 1
    return printed


def _append_legacy_prompt_cues(
    lines: list[str],
    payload: Mapping[str, Any],
    *,
    max_results: int,
) -> int:
    printed = 0
    for lane in LEGACY_PROMPT_CUE_LANES:
        cues = payload.get(lane)
        if not isinstance(cues, list) or not cues:
            continue

        section_started = False
        lane_printed = 0
        for cue in cues:
            if printed >= max_results:
                return printed
            if lane_printed >= PROMPT_CUE_LIMIT_PER_KIND:
                break
            if not isinstance(cue, Mapping):
                continue
            if not section_started:
                lines.append(lane)
                section_started = True
            lines.extend(_format_prompt_cue(cue))
            printed += 1
            lane_printed += 1
    return printed


def _prompt_cue_sort_key(cue: Any) -> tuple[int, str, str]:
    if not isinstance(cue, Mapping):
        return (99, "", "")
    memory_kind = str(cue.get("memory_kind") or "")
    kind_rank = (
        PROMPT_MEMORY_KINDS.index(memory_kind)
        if memory_kind in PROMPT_MEMORY_KINDS
        else len(PROMPT_MEMORY_KINDS)
    )
    path = str(cue.get("path") or cue.get("note_path") or "")
    title = str(cue.get("title") or "")
    return (kind_rank, path, title)


def _format_prompt_cue(cue: Mapping[str, Any]) -> list[str]:
    path = _clean_text(cue.get("path") or cue.get("note_path") or "")[:120]
    title = _clean_text(cue.get("title") or path or "prompt cue")[:120]
    status = _clean_text(cue.get("evidence_status") or cue.get("status") or "candidate")[:40]
    updated = _clean_text(cue.get("updated") or "")[:32]
    review_after = _clean_text(cue.get("review_after") or "")[:32]
    confidence = _clean_text(cue.get("confidence") or "")[:24]
    target = f"[[{path.removesuffix('.md')}|{title}]]" if path else title

    suffix_parts = [
        part
        for part in (
            f"updated: {updated}" if updated else "",
            f"review after: {review_after}" if review_after else "",
            f"confidence: {confidence}" if confidence else "",
        )
        if part
    ]
    suffix = f"; {'; '.join(suffix_parts)}" if suffix_parts else ""
    lines = [f"- [{status}] {target}{suffix}"]

    for field, label in (
        ("memory_kind", "kind"),
        ("scope", "scope"),
        ("applies_when", "applies when"),
        ("do", "do"),
        ("avoid", "avoid"),
        ("check_before_acting", "check before acting"),
        ("prevention_cue", "prevention cue"),
        ("evidence", "evidence"),
    ):
        value = _clean_text(cue.get(field) or "")
        if value:
            lines.append(f"  - {label}: {value[:220]}")
    return lines


def _append_usage_and_entity_guidance(lines: list[str], payload: Mapping[str, Any]) -> None:
    usage = payload.get("usage")
    if isinstance(usage, list) and usage:
        lines.append("Usage (navigation guidance, not evidence):")
        for item in usage[:3]:
            lines.append(f"- {_clean_text(item)[:240]}")

    entity_guidance = payload.get("entity_guidance")
    if isinstance(entity_guidance, Mapping):
        lines.append("Entity guidance (modeling guidance, not evidence):")
        criteria = entity_guidance.get("criteria")
        if isinstance(criteria, list):
            for criterion in criteria[:2]:
                lines.append(f"- {_clean_text(criterion)[:240]}")
        prewrite_checks = entity_guidance.get("prewrite_checks")
        if isinstance(prewrite_checks, list):
            for check in prewrite_checks[:2]:
                lines.append(f"- {_clean_text(check)[:240]}")


def _append_link_context(
    lines: list[str],
    payload: Mapping[str, Any],
    *,
    mode: str,
    max_results: int,
) -> int:
    printed = 0
    if mode != "prompt":
        printed += _append_context_items(
            lines,
            "orientation",
            payload.get("orientation"),
            _format_context_reference,
            max_results=max_results - printed,
        )
        printed += _append_context_items(
            lines,
            "broken_links",
            payload.get("broken_links"),
            _format_broken_link,
            max_results=max_results - printed,
        )
    printed += _append_context_items(
        lines,
        "link_targets",
        payload.get("link_targets"),
        _format_context_reference,
        max_results=max_results - printed,
    )
    printed += _append_context_items(
        lines,
        "suggested_links",
        payload.get("suggested_links"),
        _format_suggested_link,
        max_results=max_results - printed,
    )
    return printed


def _append_context_items(
    lines: list[str],
    label: str,
    value: object,
    formatter: Callable[[Mapping[str, Any]], list[str]],
    *,
    max_results: int,
) -> int:
    if max_results <= 0:
        return 0
    items = value if isinstance(value, list) else []
    if not items:
        return 0
    lines.append(label)
    printed = 0
    for item in items:
        if printed >= max_results:
            break
        if not isinstance(item, Mapping):
            continue
        lines.extend(formatter(item))
        printed += 1
    return printed


def _format_context_reference(reference: Mapping[str, Any]) -> list[str]:
    path = _clean_text(reference.get("path") or "(unknown)")
    title = _clean_text(reference.get("title") or path)
    page_type = _clean_text(reference.get("page_type") or "unknown")
    relation = _clean_text(reference.get("relation") or "reference")
    content_hash = _clean_text(reference.get("content_hash") or "")
    raw_tags = reference.get("tags")
    tags = raw_tags if isinstance(raw_tags, list) else []
    tag_suffix = f" tags={','.join(_clean_text(tag) for tag in tags[:5])}" if tags else ""
    hash_suffix = f" hash={content_hash[:12]}" if content_hash else ""
    lines = [
        f"- [[{path.removesuffix('.md')}]] — {title} "
        f"({relation}; {page_type}{tag_suffix}{hash_suffix})"
    ]
    followup_search = _clean_text(reference.get("followup_search") or "")
    if followup_search:
        lines.append(f"  - verify before use: kb_search_notes query={followup_search[:200]}")
    return lines


def _format_broken_link(link: Mapping[str, Any]) -> list[str]:
    source_path = _clean_text(link.get("source_path") or "(unknown)")
    source_hash = _clean_text(link.get("source_content_hash") or "")
    target = _clean_text(link.get("normalized_target") or link.get("target") or "(unknown)")
    occurrences = link.get("occurrences") or 1
    suggested_path = _clean_text(link.get("suggested_path") or "")
    hash_suffix = f" hash={source_hash[:12]}" if source_hash else ""
    lines = [
        f"- [[{source_path.removesuffix('.md')}]] -> [[{target}]] "
        f"(missing x{occurrences}{hash_suffix})"
    ]
    if suggested_path:
        lines.append(f"  - suggested_path: {suggested_path}")
    followup_search = _clean_text(link.get("followup_search") or "")
    if followup_search:
        lines.append(f"  - verify before use: kb_search_notes query={followup_search[:200]}")
    return lines


def _format_suggested_link(link: Mapping[str, Any]) -> list[str]:
    source_path = _clean_text(link.get("source_path") or "(unknown)")
    source_hash = _clean_text(link.get("source_content_hash") or "")
    target_path = _clean_text(link.get("target_path") or "(unknown)")
    relation = _clean_text(link.get("relation") or "add_link")
    reason = _clean_text(link.get("reason") or "")
    hash_suffix = f" hash={source_hash[:12]}" if source_hash else ""
    lines = [
        f"- [[{source_path.removesuffix('.md')}]] -> "
        f"[[{target_path.removesuffix('.md')}]] ({relation}{hash_suffix})"
    ]
    if reason:
        lines.append(f"  - why: {reason[:240]}")
    followup_search = _clean_text(link.get("followup_search") or "")
    if followup_search:
        lines.append(f"  - verify before use: kb_search_notes query={followup_search[:200]}")
    return lines


def _clean_text(value: object) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("]]", "] ]")
        .replace("[[", "[ [")
    )
