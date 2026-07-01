from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent_hooks.llm_wiki_context_text import clean_context_text

_PROMPT_MEMORY_KINDS = (
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
_PROMPT_CUE_LIMIT_PER_KIND = 3


def append_prompt_cues(
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

    return 0


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
        memory_kind = clean_context_text(cue.get("memory_kind") or "semantic_fact")[:64]
        if printed_by_kind.get(memory_kind, 0) >= _PROMPT_CUE_LIMIT_PER_KIND:
            continue
        if printed_by_kind.get(memory_kind, 0) == 0:
            lines.append(memory_kind)
        lines.extend(_format_prompt_cue(cue))
        printed += 1
        printed_by_kind[memory_kind] = printed_by_kind.get(memory_kind, 0) + 1
    return printed


def _prompt_cue_sort_key(cue: Any) -> tuple[int, str, str]:
    if not isinstance(cue, Mapping):
        return (99, "", "")
    memory_kind = str(cue.get("memory_kind") or "")
    kind_rank = (
        _PROMPT_MEMORY_KINDS.index(memory_kind)
        if memory_kind in _PROMPT_MEMORY_KINDS
        else len(_PROMPT_MEMORY_KINDS)
    )
    path = str(cue.get("path") or cue.get("note_path") or "")
    title = str(cue.get("title") or "")
    return (kind_rank, path, title)


def _format_prompt_cue(cue: Mapping[str, Any]) -> list[str]:
    path = clean_context_text(cue.get("path") or cue.get("note_path") or "")[:120]
    title = clean_context_text(cue.get("title") or path or "prompt cue")[:120]
    status = clean_context_text(cue.get("evidence_status") or cue.get("status") or "candidate")[:40]
    updated = clean_context_text(cue.get("updated") or "")[:32]
    review_after = clean_context_text(cue.get("review_after") or "")[:32]
    confidence = clean_context_text(cue.get("confidence") or "")[:24]
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
        value = clean_context_text(cue.get(field) or "")
        if value:
            lines.append(f"  - {label}: {value[:220]}")
    return lines
