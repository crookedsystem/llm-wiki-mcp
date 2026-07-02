# Folder placement and subfolder rules

This reference defines **where a page goes**: how to choose a folder when writing, when to
create subfolders inside the five top folders, when to keep a folder flat, and how to relocate a
page that is in the wrong place. Load it when a top folder is getting large, when you are unsure
which folder a new page belongs in, or when a page you read looks misfiled.

The routine write path only needs the one-paragraph rule in `SKILL.md`
("Folder placement rules"). Read this file when you actually have to decide a split, a subfolder
name, or a relocation.

## Core principle: folder = KIND, filename = WHICH, tags/index = TOPIC

Three orthogonal questions, three different mechanisms — never conflate them:

- **Folder** answers *"what kind of knowledge is this?"* A page can live in exactly one folder, so
  folders must key on a **closed, deterministic property** the agent can assign without guessing.
- **Filename** answers *"which specific thing is this?"* — the canonical kebab-case slug.
- **Tags, `index.md`, and `[[wikilinks]]`** answer *"what is this about?"* — the open-ended,
  many-to-many topic layer. This vault auto-maintains `index.md` (grouped by type), which already
  gives you a browsable map, so you do **not** need folders to make topics navigable.

The failure mode this prevents: foldering by open-ended *topic*. Topics overlap and multiply, a
page often fits two of them, and an agent writing a new page cannot reliably pick the right topic
folder — so pages scatter and duplicate. Keep topic grouping in tags/index/links; reserve folders
for closed keys.

Research basis (see `## Research basis` below): PARA, Johnny.Decimal, Zettelkasten/Obsidian
folders-vs-tags consensus, Diátaxis (organize by reader intent, not feature/topic), MediaWiki
namespace-vs-category guidance, and agent-memory KB practice (CoALA, Letta/MemGPT, Karpathy LLM
Wiki) all converge on the same rule: **partition by kind with a closed key; push topical grouping
to links/tags/index; keep the tree shallow.**

## Default: flat

A page's default path is `<type-folder>/<kebab-slug>.md` — flat inside its top folder. Do not
create a subfolder for a page on first appearance. Structure is earned by volume, not declared up
front. Most vaults of a few hundred notes are fine with 1–2 subfolders total; many stay fully flat.

## When to create a subfolder (ALL four must hold)

1. **Volume** — the top folder already holds **more than ~20 pages**. Start *considering* a split
   at 20; by ~30 in one flat folder the split is overdue. (Below 20, flat + `index.md` + tags is
   strictly better.)
2. **Cluster size** — at least one candidate group contains **≥ 5 pages** that clearly belong
   together. Never create a subfolder for fewer than 5 (hard floor 3); a 2–3 page "cluster" stays
   in the parent.
3. **Closed, deterministic key** — the group is defined by a **stable, enumerable key** you can
   assign a *future* page to without guessing. Allowed keys, in priority order:
   - **entity kind** (for `entities/`): `people/`, `products/`, `projects/`, `orgs/`,
     `standards/`, `models/` — a small closed set.
   - **repo / project scope** (for `queries/`, `concepts/`, `comparisons/`): the repository or
     product name, e.g. `queries/fanplus-api/`, `concepts/fanplus-api/`, `queries/proxmox-homelab/`.
     The repo/project name is a deterministic key the agent always knows.
   - **source type** (for `raw/`): `articles/`, `transcripts/`, `assets/`, etc. (already in use).
   - **bounded technical domain** (fallback, mainly `concepts/`): a stable, well-known,
     mutually-exclusive domain such as `kafka/`, `databases/`, `testing/`. Allowed **only** when the
     domain is stable and non-overlapping, every new page's membership is obvious, and you record a
     one-line membership rule (below). Prefer a repo/project key over a topic key whenever both fit.
4. **Mutual exclusivity (hesitation test)** — every current *and* reasonably-expected page maps to
   exactly one group. If any page plausibly fits two candidate folders, **do not split** — keep flat
   and disambiguate with tags/`index.md`/wikilinks. "Fits two folders" means the answer is *zero* new
   folders, not two.

If all four hold, create the subfolder **and relocate every existing sibling that belongs in it in
the same pass** (never leave a half-done split where some Kafka pages are in `concepts/kafka/` and
others are still flat).

## When to keep it flat (any one is enough)

- The top folder has **≤ ~20 pages**.
- There is only **one** real cluster, so splitting would leave a large `misc` residue.
- The only available grouping is an **open-ended or overlapping topic** where an agent would
  hesitate on a new page → use tags + `index.md` sections + wikilinks instead.
- The candidate subfolder would hold **< 5 pages** → keep those pages in the parent.

## Depth cap

- **One** subfolder level inside a top folder. Total depth from the vault root is at most two
  folders: `entities/products/postgresql.md`, `concepts/fanplus-api/ad-rewards-per-placement.md`.
- **Never** nest a second level (`concepts/databases/mysql/innodb/...`). Every methodology studied
  caps practical depth at 2–3 levels; deeper trees cause "treasure-hunt" retrieval and placement
  paralysis.
- A second level is considered **only** if a subfolder itself passes all four split tests again on a
  closed key, and only after deliberate review — the default answer is no. When tempted to go
  deeper, add a `[[wikilink]]`/tag or an `index.md` section instead.

## Breadth

Do not cap the number of files per folder at "7±2" — that is a memory-recall limit, not a limit for
a scannable, sorted, searchable list. A flat folder of 15–30 pages, or a subfolder of many pages, is
fine. The real constraints are **depth** and **theme-coherence**, not raw count. Keep total
top-level folders at the fixed five (the ≤10 ceiling everyone recommends).

## Naming and membership rules

- **kebab-case, lowercase.** Plural for entity-kind buckets (`people/`, `products/`); the
  repo/project name verbatim for scope buckets (`fanplus-api/`); the domain word for domain buckets
  (`kafka/`).
- No spaces, no `.` in folder names, no numeric prefixes (this vault sorts via `index.md`, not the
  filesystem).
- **Every subfolder gets a one-line "what belongs here" membership rule recorded in `SCHEMA.md`'s
  Folder model.** This is what keeps placement deterministic for the next write — an agent reads the
  rule and routes without guessing. A subfolder without a written membership rule is an
  anti-pattern; add the rule or dissolve the folder.

## Subfolders never change `type`

Subfoldering is a navigation refinement, not a reclassification. `entities/products/postgresql.md`
is still `type: entity`; `concepts/kafka/kafka-replication-isr-acks.md` is still `type: concept`.
The path→type agreement in `SKILL.md` is enforced at the **top folder** level:

- `raw/**` → `raw`
- `entities/**` → `entity`
- `concepts/**` → `concept` or `summary`
- `comparisons/**` → `comparison`
- `queries/**` → `query` or `summary`

## Placement algorithm for every write

Run this before every `kb_write_note`, new or update:

1. **Pick the top folder from `type`** (the kind of knowledge). This is mandatory and unambiguous.
2. **Match an existing subfolder.** Check `SCHEMA.md`'s Folder model for a subfolder whose
   membership rule this page satisfies (its repo/project, its entity kind, its bounded domain, its
   source type). If one matches → write to `<top>/<subfolder>/<slug>.md`.
3. **Otherwise write flat** at `<top>/<slug>.md`.
4. **Do not invent a new subfolder for a single page.** Creating a subfolder is a deliberate reorg
   that requires the four split tests to already pass on the *existing* flat siblings — never a side
   effect of one write. If you notice the trigger is now met (e.g. this is the 6th flat
   `concepts/` page about `fanplus-api` and `concepts/` is well over 20), do the split as its own
   step: create the folder, relocate the siblings, record the membership rule, then write the new
   page into it.
5. **On update, keep the page's current path** unless it violates the placement rules — then
   relocate it (next section). A path change is never a silent side effect of a content update.

## Relocating a misplaced page ("폴더 위치가 이상하면 수정")

When reading or prewriting you find a page whose location breaks the rules, fix it. A location is
wrong when:

- (a) its `type` disagrees with its top folder (e.g. a `type: query` page sitting in `concepts/`, or
  a page whose content is really an answered investigation but is filed as a concept);
- (b) it sits flat while it clearly belongs in an existing subfolder, or sits in a subfolder it does
  not match; or
- (c) it is under the wrong repo/kind/domain subfolder.

MCP has no move operation, so **relocation = write-new-then-delete-old**. This is a **sanctioned,
narrowly-scoped exception** to the delete policy: the knowledge survives at the corrected path and
nothing is destroyed. It is distinct from content deletion, which still requires an explicit user
request.

Procedure:

1. `kb_read_note(old_path)` → full structured body/fields + current `content_hash`.
2. Determine the correct path from the placement rules. If the correct **top folder** differs, the
   `type` must change to match it (e.g. `concept` → `query`).
3. `kb_write_note(new_path, …)` with the same content: fix `type` if the top folder changed, set
   `updated` to now, keep the original `created`, pass **no** `if_hash` (this is a new page). Confirm
   the write succeeded.
4. **Repair inbound links.** Find pages that link `[[old_path]]` via `kb_context` /
   `kb_search_notes`, and patch each to `[[new_path]]` with `kb_read_note` + `kb_write_note(if_hash=…)`.
   Preserve the alias text.
5. `kb_delete_note(old_path, dry_run=true)` to preview, then
   `kb_delete_note(old_path, dry_run=false, confirm=<confirmation_phrase>)` to remove the stale
   original. `index.md` and `log.md` update automatically on both the new write and the delete.

Guardrails:

- **Clear violation only.** Relocate only on an evidenced rule break (type≠folder, or an unambiguous
  closed-key mismatch). If placement is merely debatable, leave the page and record it as an open
  question — do not churn stable paths.
- **Deliberate work only.** Never relocate from a prompt hook or an automatic/background pass. Do it
  during explicit write or maintenance work.
- **Ambiguity → ask.** For a genuinely borderline case, ask the user before moving.
- **No mass reorg by stealth.** Fixing one misplaced page is not license to re-fold the whole vault.
  A full re-foldering (e.g. splitting a 50-page flat `concepts/` into domain subfolders) is a
  separate, explicitly user-approved batch, because it is many destructive `delete` operations and
  many link repairs against a live, possibly shared vault.

## Worked example: applying the rules to this vault

A 10-agent audit of the vault (≈146 pages) found the synthesized folders **flat**: `concepts/` ~58,
`queries/` ~34, `entities/` 16, `comparisons/` 9 (`raw/` was already subdivided into
`articles/ transcripts/ assets/ hermes/`). Applying the rules above yields this **target** structure
(illustrative — execute only as a user-approved batch reorg, not automatically):

- **`entities/` (16) → split now.** Passes on the closed *entity-kind* key:
  - `entities/products/` — anki, apache-kafka, notion, obsidian, postgresql, proxmox-ve, quartz, tmux (8)
  - `entities/projects/` — fanplus-api, fanplus-old-api, fanplus-old-cms, llm-wiki-mcp, techtaurant (5)
  - keep flat until they reach 5: `people/` (kim-yongseok, rookedsysc = 2), `orgs/` (fanplus = 1).
- **`queries/` (34) → split now**, by *repo/project or bounded domain* key:
  `proxmox-homelab/` (6), `llm-wiki-mcp/` (5), `techtaurant/` (3), plus larger bounded clusters as
  they cohere. Keep genuine one-offs flat. Do **not** collapse everything named "llm-wiki" into one
  folder — separate the MCP *code* from the KB *pattern* from *publishing*, because those are
  different artifacts.
- **`concepts/` (58) → split now.** Prefer the repo key `concepts/fanplus-api/` (~11 pages) first;
  then bounded, mutually-exclusive domains that clear ≥5: `kafka/` (5), `databases/` (9),
  `testing/` (6), `knowledge-base/` (9). Leave true one-offs and fuzzy catch-alls flat rather than
  forcing a `misc` folder.
- **`comparisons/` (9) → keep flat.** Under 20 and heterogeneous; no closed cluster reaches 5.

Misplacement fixes the audit found (candidates for the relocation procedure):

- `concepts/embeddings.md` — 0-byte empty stub with no frontmatter → populate or delete.
- `concepts/innodb-update-mvcc-undo-log-source-code.md` — content is an answered investigation
  ("판정 요약" / "답변에 재사용할 짧은 문장") → `queries/` (`type: concept` → `query`).
- `concepts/hermes-agent-project-memory.md` — a personal project/environment memory dump, not a
  reusable concept → `entities/` (or a dedicated memory page).

## Research basis

Ten subagents reviewed 200+ documents (the ~146-page live vault plus 200+ external sources across
six methodology tracks). Convergent, cross-validated thresholds:

| Rule | Value | Sources (representative) |
| --- | --- | --- |
| Max depth inside a top folder | 1 subfolder level (2 total from root); hard cap 3 | PARA, Johnny.Decimal, Quartz, MediaWiki subpages, NN/g flat-vs-deep |
| Top-level folder count | keep the fixed 5 (≤10 ceiling) | large-vault surveys, Johnny.Decimal, PARA |
| Subdivide trigger | > ~20 pages AND ≥2 clusters of ≥5 passing the "different-handling" test | IA card-sort standardization, folder-depth best practice |
| Subfolder floor | never < 5 pages (hard floor 3) | IA thin-content floors, Johnny.Decimal |
| Split key | closed/deterministic only (kind, repo/project, source, bounded domain) — never open topic | agent-memory KB, MediaWiki namespaces-vs-categories, Diátaxis |
| Hesitation test | a page fitting two folders → create zero, use tags/links | Zettelkasten, Obsidian folders-vs-tags, PARA |
| Creation timing | just-in-time; never pre-create empty folders | PARA "desire paths", Diátaxis "don't build empty shells" |
| Per-subfolder membership rule | one line, recorded in `SCHEMA.md` | DokuWiki namespace docs, large-vault naming practice |
| Topic navigation without folders | tags + `index.md` + MOC/hub notes | LYT/MOC, digital-garden/Quartz, TiddlyWiki |

Key methodology anchors: Johnny.Decimal (hard numeric caps: ≤10 per level, 3-level depth);
PARA (fixed top folders, flat, actionability over topic, just-in-time, horizontal archiving over
nesting); Zettelkasten + Obsidian "folders vs tags vs links" (a note lives in one folder but
unlimited tags/links → topics belong to tags/links; hesitation test); Diátaxis (organize by
reader/agent intent, never pre-build empty category shells); MOC/LYT + Quartz/digital-garden
(hub/index notes replace topic folders; `index.md` is the map); classic IA (broad-and-shallow beats
narrow-and-deep; card-sort agreement thresholds; the "different-fields" attribute test; facets over
deeper hierarchy); and agent-memory KBs — CoALA, Letta/MemGPT labeled blocks, Karpathy's LLM Wiki,
"Obsidian-for-AI" second brains — which all partition by *kind of knowledge* with a small fixed
write surface and route by a schema file rather than by inferring topic folders.
