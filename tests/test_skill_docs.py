from pathlib import Path


def _project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("project root not found")


PROJECT_ROOT = _project_root()
SKILL = PROJECT_ROOT / "skills" / "llm-wiki" / "SKILL.md"
PUSH_SKILL = PROJECT_ROOT / "skills" / "llm-wiki-push" / "SKILL.md"


def test_llm_wiki_skill_embeds_content_modeling_guidance() -> None:
    content = SKILL.read_text(encoding="utf-8")

    required_fragments = [
        "## Content model and page types",
        "| `entity` | `entities/` |",
        "| `concept` | `concepts/` |",
        "## SCHEMA.md bootstrap",
        "## index.md structure",
        "## log.md structure",
        "## Concrete examples",
    ]

    for fragment in required_fragments:
        assert fragment in content


def test_llm_wiki_skill_requires_in_body_obsidian_wikilinks() -> None:
    content = SKILL.read_text(encoding="utf-8")

    required_fragments = [
        "## Internal wikilink discipline",
        "replace bare in-body mentions with Obsidian wikilinks",
        "[[entities/kim-yongseok|김용석]]",
        "Do not rely on tags, sources, titles, or index entries to create graph edges",
    ]

    for fragment in required_fragments:
        assert fragment in content


def test_llm_wiki_skill_explains_hash_and_hook_rules() -> None:
    content = SKILL.read_text(encoding="utf-8")

    provenance_trailer = (
        "<!-- kb-provenance: source_hash=<sha256-of-content-before-trailer>; "
        "operation=write_note; actor=llm-wiki -->"
    )
    required_fragments = [
        provenance_trailer,
        "For the next update, pass `content_hash` as `if_hash`, not `source_hash`.",
        "MCP-only mode",
        "UserPromptSubmit",
        "Stop",
        "Hook-driven always-on usage",
    ]

    for fragment in required_fragments:
        assert fragment in content


def test_llm_wiki_skill_defines_prompt_time_context_kinds() -> None:
    content = SKILL.read_text(encoding="utf-8")

    required_fragments = [
        "### Prompt hints section",
        "kind: preference_profile",
        "kind: project_convention",
        "kind: procedural_pattern",
        "kind: failure_prevention",
        "### Prompt-time memory kinds",
        "### Context-loader retrieval pipeline",
        "### Stop-hook memory capture",
        "Treat hook-injected wiki memory as advisory context",
    ]

    for fragment in required_fragments:
        assert fragment in content


def test_llm_wiki_skill_links_memory_reference_files() -> None:
    content = SKILL.read_text(encoding="utf-8")
    references = {
        "references/memory-taxonomy.md": [
            "# Memory Taxonomy",
            "`working_context`",
            "`preference_profile`",
            "Retrieval Precedence",
        ],
        "references/memory-write-policy.md": [
            "# Memory Write Policy",
            "No-Store Rules",
            "Durability Thresholds",
            "failure_prevention",
        ],
        "references/memory-research-map.md": [
            "# Memory Research Map",
            "500 reviewed references",
            "10 independent research tracks",
            "Representative References",
        ],
    }

    for relative_path, required_fragments in references.items():
        assert relative_path in content

        reference_path = SKILL.parent / relative_path
        assert reference_path.exists()

        reference_content = reference_path.read_text(encoding="utf-8")
        for fragment in required_fragments:
            assert fragment in reference_content


def test_llm_wiki_push_skill_requires_explicit_push_request() -> None:
    content = PUSH_SKILL.read_text(encoding="utf-8")

    required_fragments = [
        "name: llm-wiki-push",
        "Do not call `kb_push_vault()` unless the user explicitly asks",
        "normal wiki writes never push without a direct user request",
        "YYYY-MM-DD HH:MM - vault sync",
        "Do not pass remote, branch, commit message, or interval options.",
    ]

    for fragment in required_fragments:
        assert fragment in content


def test_docs_do_not_keep_legacy_personal_kb_names() -> None:
    legacy_fragments = [
        "personal-kb-mcp",
        "personal-kb",
        "personal_kb",
        "Personal KB",
        "KB MCP",
    ]
    scan_roots = [
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "README.ko.md",
        PROJECT_ROOT / "README.zh.md",
        PROJECT_ROOT / "README.ja.md",
        PROJECT_ROOT / "skills",
        PROJECT_ROOT / "mcp",
        PROJECT_ROOT / "scripts",
    ]
    text_suffixes = {".json", ".md", ".py", ".sh", ".toml", ".yaml", ".yml"}

    files: list[Path] = []
    for root in scan_roots:
        if root.is_file():
            files.append(root)
            continue
        files.extend(path for path in root.rglob("*") if path.suffix in text_suffixes)

    for path in files:
        content = path.read_text(encoding="utf-8")
        for fragment in legacy_fragments:
            assert fragment not in content, (
                f"{fragment!r} found in {path.relative_to(PROJECT_ROOT)}"
            )
