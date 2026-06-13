from common.model import FrozenModel
from vault.service.command.context_command import ContextMode
from vault.service.result.context_result import EntityGuidance


class ContextSectionSpec(FrozenModel):
    name: str
    purpose: str
    query_terms: tuple[str, ...]
    quota: int
    path_prefix: str | None = None
    explicit_paths: tuple[str, ...] = ()


SECTION_SPECS_BY_MODE: dict[ContextMode, tuple[ContextSectionSpec, ...]] = {
    "prompt": (
        ContextSectionSpec(
            name="orientation",
            purpose="Vault schema, index, and recent log orientation before answering or coding.",
            query_terms=("SCHEMA", "index", "log"),
            quota=3,
            explicit_paths=("SCHEMA.md", "index.md", "log.md"),
        ),
        ContextSectionSpec(
            name="entity_candidates",
            purpose="Existing entity anchors that may own or scope the requested knowledge.",
            query_terms=("project", "repository", "service", "api", "standard"),
            quota=3,
            path_prefix="entities",
        ),
        ContextSectionSpec(
            name="project_context",
            purpose="Project or repository context that should constrain the answer.",
            query_terms=("project-context", "repository", "service"),
            quota=3,
        ),
        ContextSectionSpec(
            name="code_conventions",
            purpose="Code conventions and development style that should guide implementation.",
            query_terms=("code-style", "naming-convention", "development style", "maintainability"),
            quota=3,
        ),
        ContextSectionSpec(
            name="domain_rules",
            purpose="Domain rules and architecture constraints related to the request.",
            query_terms=("domain-rule", "domain rules", "architecture", "module"),
            quota=3,
        ),
        ContextSectionSpec(
            name="direct_matches",
            purpose="Highest scoring direct matches for the original prompt.",
            query_terms=(),
            quota=50,
        ),
    ),
    "prewrite": (
        ContextSectionSpec(
            name="orientation",
            purpose="Schema/index/log pages needed before writing durable wiki knowledge.",
            query_terms=("SCHEMA", "index", "log"),
            quota=3,
            explicit_paths=("SCHEMA.md", "index.md", "log.md"),
        ),
        ContextSectionSpec(
            name="entity_candidates",
            purpose="Existing entity pages to update or link before creating new entities.",
            query_terms=("project", "repository", "service", "api", "standard"),
            quota=4,
            path_prefix="entities",
        ),
        ContextSectionSpec(
            name="direct_matches",
            purpose="Potential duplicate or related pages for the knowledge being written.",
            query_terms=(),
            quota=5,
        ),
        ContextSectionSpec(
            name="domain_rules",
            purpose="Domain rules that should be linked from the new or updated note.",
            query_terms=("domain-rule", "domain rules", "architecture", "module"),
            quota=3,
        ),
        ContextSectionSpec(
            name="code_conventions",
            purpose="Code conventions and development style worth linking when relevant.",
            query_terms=("code-style", "naming-convention", "development style", "maintainability"),
            quota=2,
        ),
    ),
    "stop": (
        ContextSectionSpec(
            name="orientation",
            purpose="Schema/index/log pages needed for a safe end-of-turn wiki update.",
            query_terms=("SCHEMA", "index", "log"),
            quota=3,
            explicit_paths=("SCHEMA.md", "index.md", "log.md"),
        ),
        ContextSectionSpec(
            name="entity_candidates",
            purpose="Entity anchors that should receive links or updates after this turn.",
            query_terms=("project", "repository", "service", "api", "standard"),
            quota=4,
            path_prefix="entities",
        ),
        ContextSectionSpec(
            name="direct_matches",
            purpose="Existing pages likely to absorb this turn's durable knowledge.",
            query_terms=(),
            quota=5,
        ),
        ContextSectionSpec(
            name="relationship_targets",
            purpose="Related concepts/entities for wikilinks and relationship updates.",
            query_terms=("relationship", "related", "concept", "entity", "open question"),
            quota=3,
        ),
    ),
}

USAGE_BY_MODE: dict[ContextMode, tuple[str, ...]] = {
    "prompt": (
        "Use this context as orientation before answering or editing code.",
        "Prefer project/entity/domain rule sections over generic direct matches "
        "when they conflict.",
        "Do not update existing notes from snippets alone; fetch full content before writing.",
    ),
    "prewrite": (
        "Use this context to avoid duplicate wiki pages before kb_write_note.",
        "If an entity candidate matches the subject, update/link it instead of creating "
        "a parallel page.",
        "Create an entity only for a named project, service, API, standard, product, "
        "organization, or stable module boundary.",
    ),
    "stop": (
        "Use this context only if the turn produced durable wiki-worthy knowledge.",
        "Prefer updating existing entity/concept/query pages over creating new pages.",
        "Append index/log changes only when a durable wiki write is actually made.",
    ),
}

ENTITY_GUIDANCE = EntityGuidance(
    criteria=[
        "Create an entity for a named project, repository, service, product, API, "
        "protocol, dataset, standard, organization, person, or stable module boundary.",
        "Do not create an entity for broad ideas, qualities, techniques, or one-off "
        "mentions; use concept, query, or tags instead.",
        "Prefer an entity when the subject can be the stable subject/object of "
        "relationships across multiple notes.",
        "For code work, project/service/module entities should anchor related code "
        "conventions, development style, and domain rules.",
    ],
    preferred_paths=[
        "entities/{project-or-repository}.md",
        "entities/{service-or-api}.md",
        "entities/{stable-module-boundary}.md",
    ],
    prewrite_checks=[
        "prewrite: search entities/ for the exact name, aliases, and repository slug "
        "before creating a new entity.",
        "prewrite: link new concept/query pages to the matching entity when scope is "
        "project-specific.",
        "prewrite: if only a broad practice is involved, create or update a concept page "
        "instead of an entity.",
    ],
)
