import re

from common.model import FrozenModel
from vault.constant.schema import (
    DEFAULT_ALLOWED_TYPES,
    LEVEL_TWO_HEADING,
    REQUIRED_RAW_FIELDS,
    REQUIRED_SYNTH_FIELDS,
    TAG_PATTERN,
    TAG_TAXONOMY_HEADING,
)
from vault.service.result.parsed_wiki_schema import ParsedWikiSchema

DEFAULT_TAXONOMY_SECTION = "General"


class VaultSchemaParser(FrozenModel):
    def parse(self, content: str) -> ParsedWikiSchema:
        """SCHEMA.md Markdown 문서에서 frontmatter/type/tag taxonomy 계약을 파싱합니다.

        입력은 `SCHEMA.md`의 전체 Markdown 문자열입니다. 출력은 허용 type, 필수 frontmatter
        필드, tag taxonomy, allowed tag list를 담는 `ParsedWikiSchema` 모델입니다.
        """
        tag_taxonomy = self._extract_tag_taxonomy(content)
        allowed_tags = sorted({tag for tags in tag_taxonomy.values() for tag in tags})
        allowed_types = self._extract_allowed_types(content) or list(DEFAULT_ALLOWED_TYPES)
        return ParsedWikiSchema(
            schema_parse_ok=bool(content and tag_taxonomy),
            allowed_types=allowed_types,
            required_synthesized_frontmatter=list(REQUIRED_SYNTH_FIELDS),
            required_raw_frontmatter=list(REQUIRED_RAW_FIELDS),
            tag_taxonomy=tag_taxonomy,
            allowed_tags=allowed_tags,
        )

    def _extract_allowed_types(self, content: str) -> list[str]:
        match = re.search(r"Allowed `type` values:\s*([^\n]+)", content)
        if match is None:
            return []
        return [
            token
            for token in self._extract_tags_from_text(match.group(1))
            if token in DEFAULT_ALLOWED_TYPES
        ]

    def _extract_tag_taxonomy(self, content: str) -> dict[str, list[str]]:
        taxonomy_lines = self._collect_taxonomy_lines(content)
        return self._parse_taxonomy_lines(taxonomy_lines)

    def _collect_taxonomy_lines(self, content: str) -> list[str]:
        """`## Tag taxonomy` heading과 다음 level-2 heading 사이의 본문 줄을 모읍니다."""
        taxonomy_lines: list[str] = []
        in_taxonomy = False
        for line in content.splitlines():
            if TAG_TAXONOMY_HEADING.match(line.strip()):
                in_taxonomy = True
                continue
            if in_taxonomy and LEVEL_TWO_HEADING.match(line.strip()):
                break
            if in_taxonomy:
                taxonomy_lines.append(line)
        return taxonomy_lines

    def _parse_taxonomy_lines(self, taxonomy_lines: list[str]) -> dict[str, list[str]]:
        """taxonomy 본문 줄을 순회하며 section -> tag list 매핑을 구성합니다."""
        taxonomy: dict[str, list[str]] = {}
        current_section = DEFAULT_TAXONOMY_SECTION
        in_fence = False
        for raw_line in taxonomy_lines:
            stripped = raw_line.strip()
            if stripped.startswith("```"):
                in_fence = not in_fence
                continue
            if self._is_skippable_line(stripped, in_fence):
                continue
            if self._is_section_header(stripped):
                current_section = self._section_name(stripped, current_section)
                taxonomy.setdefault(current_section, [])
                continue
            if not stripped.startswith("-"):
                continue

            parsed_item = self._parse_list_item(stripped, current_section)
            if parsed_item is None:
                continue
            current_section, tags = parsed_item
            self._add_tags(taxonomy, current_section, tags)

        return self._finalize_taxonomy(taxonomy)

    def _is_skippable_line(self, stripped: str, in_fence: bool) -> bool:
        return in_fence or not stripped or stripped.startswith("#")

    def _is_section_header(self, stripped: str) -> bool:
        return stripped.endswith(":") and not stripped.startswith("-")

    def _section_name(self, stripped: str, current_section: str) -> str:
        return stripped[:-1].strip() or current_section

    def _parse_list_item(
        self, stripped: str, current_section: str
    ) -> tuple[str, list[str]] | None:
        """`- ...` list item에서 (section, tags)를 추출합니다. 태그가 없으면 None."""
        item = stripped[1:].strip()
        if not item or item.startswith("["):
            return None
        section = current_section
        values = item
        if ":" in item:
            raw_section, values = item.split(":", 1)
            section = raw_section.strip().strip("`") or current_section
        tags = self._extract_tags_from_text(values)
        if not tags:
            return None
        return section, tags

    def _add_tags(
        self, taxonomy: dict[str, list[str]], section: str, tags: list[str]
    ) -> None:
        section_tags = taxonomy.setdefault(section, [])
        for tag in tags:
            if tag not in section_tags:
                section_tags.append(tag)

    def _finalize_taxonomy(self, taxonomy: dict[str, list[str]]) -> dict[str, list[str]]:
        return {section: sorted(tags) for section, tags in taxonomy.items() if tags}

    def _extract_tags_from_text(self, text: str) -> list[str]:
        code_tags = [tag for tag in re.findall(r"`([^`]+)`", text) if TAG_PATTERN.match(tag)]
        if code_tags:
            return code_tags

        candidates = [part.strip().strip("`.;") for part in text.split(",")]
        if len(candidates) == 1:
            single = candidates[0]
            return [single] if TAG_PATTERN.match(single) else []
        return [candidate for candidate in candidates if TAG_PATTERN.match(candidate)]
