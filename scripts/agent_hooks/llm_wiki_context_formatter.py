from __future__ import annotations

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
from agent_hooks.llm_wiki_context_text import clean_context_text
from agent_hooks.llm_wiki_prompt_cue_formatter import append_prompt_cues

DEFAULT_LIMIT = 12


def format_context_error(exc: Exception) -> str:
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
        path = clean_context_text(result.get("path") or "(unknown)")
        title = clean_context_text(result.get("title") or path)
        page_type = clean_context_text(result.get("page_type") or "unknown")
        content_hash = clean_context_text(result.get("content_hash") or "")
        raw_tags = result.get("tags")
        tags = raw_tags if isinstance(raw_tags, list) else []
        tag_suffix = (
            f" tags={','.join(clean_context_text(tag) for tag in tags[:5])}" if tags else ""
        )
        hash_suffix = f" hash={content_hash[:12]}" if content_hash else ""
        lines.append(
            f"- [[{path.removesuffix('.md')}]] — {title} ({page_type}{tag_suffix}{hash_suffix})"
        )
        raw_matches = result.get("matches")
        matches = raw_matches if isinstance(raw_matches, list) else []
        for match in matches[:2]:
            if not isinstance(match, Mapping):
                continue
            snippet = clean_context_text(match.get("snippet") or "")
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
        printed += append_prompt_cues(lines, payload, max_results=max_results)
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


def _append_usage_and_entity_guidance(lines: list[str], payload: Mapping[str, Any]) -> None:
    usage = payload.get("usage")
    if isinstance(usage, list) and usage:
        lines.append("Usage (navigation guidance, not evidence):")
        for item in usage[:3]:
            lines.append(f"- {clean_context_text(item)[:240]}")

    entity_guidance = payload.get("entity_guidance")
    if isinstance(entity_guidance, Mapping):
        lines.append("Entity guidance (modeling guidance, not evidence):")
        criteria = entity_guidance.get("criteria")
        if isinstance(criteria, list):
            for criterion in criteria[:2]:
                lines.append(f"- {clean_context_text(criterion)[:240]}")
        prewrite_checks = entity_guidance.get("prewrite_checks")
        if isinstance(prewrite_checks, list):
            for check in prewrite_checks[:2]:
                lines.append(f"- {clean_context_text(check)[:240]}")


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
    path = clean_context_text(reference.get("path") or "(unknown)")
    title = clean_context_text(reference.get("title") or path)
    page_type = clean_context_text(reference.get("page_type") or "unknown")
    relation = clean_context_text(reference.get("relation") or "reference")
    content_hash = clean_context_text(reference.get("content_hash") or "")
    raw_tags = reference.get("tags")
    tags = raw_tags if isinstance(raw_tags, list) else []
    tag_suffix = f" tags={','.join(clean_context_text(tag) for tag in tags[:5])}" if tags else ""
    hash_suffix = f" hash={content_hash[:12]}" if content_hash else ""
    lines = [
        f"- [[{path.removesuffix('.md')}]] — {title} "
        f"({relation}; {page_type}{tag_suffix}{hash_suffix})"
    ]
    followup_search = clean_context_text(reference.get("followup_search") or "")
    if followup_search:
        lines.append(f"  - verify before use: kb_search_notes query={followup_search[:200]}")
    return lines


def _format_broken_link(link: Mapping[str, Any]) -> list[str]:
    source_path = clean_context_text(link.get("source_path") or "(unknown)")
    source_hash = clean_context_text(link.get("source_content_hash") or "")
    target = clean_context_text(link.get("normalized_target") or link.get("target") or "(unknown)")
    occurrences = link.get("occurrences") or 1
    suggested_path = clean_context_text(link.get("suggested_path") or "")
    hash_suffix = f" hash={source_hash[:12]}" if source_hash else ""
    lines = [
        f"- [[{source_path.removesuffix('.md')}]] -> [[{target}]] "
        f"(missing x{occurrences}{hash_suffix})"
    ]
    if suggested_path:
        lines.append(f"  - suggested_path: {suggested_path}")
    followup_search = clean_context_text(link.get("followup_search") or "")
    if followup_search:
        lines.append(f"  - verify before use: kb_search_notes query={followup_search[:200]}")
    return lines


def _format_suggested_link(link: Mapping[str, Any]) -> list[str]:
    source_path = clean_context_text(link.get("source_path") or "(unknown)")
    source_hash = clean_context_text(link.get("source_content_hash") or "")
    target_path = clean_context_text(link.get("target_path") or "(unknown)")
    relation = clean_context_text(link.get("relation") or "add_link")
    reason = clean_context_text(link.get("reason") or "")
    hash_suffix = f" hash={source_hash[:12]}" if source_hash else ""
    lines = [
        f"- [[{source_path.removesuffix('.md')}]] -> "
        f"[[{target_path.removesuffix('.md')}]] ({relation}{hash_suffix})"
    ]
    if reason:
        lines.append(f"  - why: {reason[:240]}")
    followup_search = clean_context_text(link.get("followup_search") or "")
    if followup_search:
        lines.append(f"  - verify before use: kb_search_notes query={followup_search[:200]}")
    return lines
