import re
from pathlib import Path

from common.helper.wiki_link_helper import normalize_wiki_target
from vault.service.vault_operational_note import OperationalNote

_LIST_ENTRY_PATTERN = re.compile(r"^\s*-\s+\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?]](.*)$")


def index_summary(index_content: str, slug: str) -> str | None:
    for line in index_content.splitlines():
        match = _LIST_ENTRY_PATTERN.match(line)
        if match is None or normalize_wiki_target(match.group(1)) != slug:
            continue
        description = match.group(2).strip()
        if description.startswith("—"):
            return description.removeprefix("—").strip() or None
    return None


def append_schema_rules(existing: str, rules: dict[str, str]) -> str:
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


def membership_rule(folder: str) -> str:
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


def seed_schema(timestamp: str) -> OperationalNote:
    frontmatter = (
        "title: Wiki Schema\n"
        f'created: "{timestamp}"\n'
        f'updated: "{timestamp}"\n'
        "type: schema\n"
        "tags:\n"
        "  - llm-wiki\n"
        "sources: []"
    )
    return OperationalNote(frontmatter=frontmatter, body="\n# Wiki Schema\n\n## Subfolders\n")
