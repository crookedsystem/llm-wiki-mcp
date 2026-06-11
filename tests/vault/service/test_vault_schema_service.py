from pathlib import Path

from vault.infrastructure.repository.vault_note_repository import VaultNoteRepository
from vault.service.vault_schema_service import VaultSchemaService

SCHEMA = """# Wiki Schema

## Frontmatter
Required fields: `title`, `created`, `updated`, `type`, `tags`, `sources`,
`confidence`, `contested`.
Allowed `type` values: `entity`, `concept`, `comparison`, `query`, `summary`.

## Tag taxonomy
- Knowledge: knowledge-base, agent-memory, mcp
- Engineering: verification
"""


def _write_schema(vault_root: Path, schema: str = SCHEMA) -> None:
    vault_root.mkdir(parents=True, exist_ok=True)
    (vault_root / "SCHEMA.md").write_text(schema, encoding="utf-8")


def test_validate_write_rejects_invalid_synthesized_frontmatter(tmp_path: Path) -> None:
    # Given: tag taxonomy가 있는 LLM Wiki vault가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))

    # When: synthesized page frontmatter가 없거나 taxonomy 밖 tag를 쓰면 검증한다.
    missing_frontmatter = schema_service.validate_write(
        "concepts/agent-memory.md",
        "# Agent Memory\n",
    )
    unknown_tag = schema_service.validate_write(
        "concepts/agent-memory.md",
        """---
title: Agent Memory
created: 2026-06-10
updated: 2026-06-10
type: concept
tags: [unknown-tag]
sources: [raw/hermes/source.md]
confidence: medium
contested: false
---

# Agent Memory
""",
    )

    # Then: write boundary에서 바로 고칠 수 있는 issue code가 반환된다.
    assert [issue.code for issue in missing_frontmatter.issues] == ["missing_frontmatter"]
    assert [issue.code for issue in unknown_tag.issues] == ["unknown_tag"]
    assert unknown_tag.issues[0].value == "unknown-tag"


def test_validate_write_rejects_synthesized_page_when_schema_is_missing(
    tmp_path: Path,
) -> None:
    # Given: SCHEMA.md가 아직 없는 vault가 있다.
    vault_root = tmp_path / "vault"
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))

    # When: required frontmatter를 갖춘 synthesized page를 먼저 쓰려고 한다.
    result = schema_service.validate_write(
        "concepts/agent-memory.md",
        """---
title: Agent Memory
created: 2026-06-10
updated: 2026-06-10
type: concept
tags: []
sources: [raw/hermes/source.md]
confidence: medium
contested: false
---

# Agent Memory
""",
    )

    # Then: 기본 type fallback으로 통과시키지 않고 schema 생성부터 요구한다.
    assert [issue.code for issue in result.issues] == ["schema_missing"]
