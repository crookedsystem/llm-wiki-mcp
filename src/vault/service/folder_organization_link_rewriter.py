import re
from collections import defaultdict
from pathlib import Path

from common.helper.wiki_link_helper import WIKI_LINK_PATTERN, normalize_wiki_target
from vault.service.result.organize_folders_result import FolderMove


def path_replacements(moves: list[FolderMove]) -> dict[str, str]:
    return {move.old_path: move.new_path for move in moves}


def stem_replacements(
    moves: list[FolderMove],
    target_paths: list[str],
) -> dict[str, str]:
    stem_counts: dict[str, int] = defaultdict(int)
    for target_path in target_paths:
        stem_counts[Path(target_path).stem] += 1
    return {
        Path(move.old_path).stem: move.new_path
        for move in moves
        if stem_counts[Path(move.old_path).stem] == 1
    }


def replace_wiki_links(
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
