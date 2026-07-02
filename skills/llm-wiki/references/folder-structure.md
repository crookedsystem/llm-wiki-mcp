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
to links/tags/index; let the tree deepen only where warrant and a deterministic child key justify
another level.**

## Default: flat

A page's default path is `<type-folder>/<kebab-slug>.md` — flat inside its current folder. Do not
create a subfolder for a page on first appearance. Structure is earned by volume, not declared up
front. New branches start flat; mature branches may deepen recursively when the same split test
keeps passing.

## When to create a subfolder (ALL four must hold)

1. **Volume** — the current folder/node already holds **more than ~15–20 direct pages**. Start
   *considering* a split at 15–20; by ~30 in one flat node the split is overdue. (Below 15–20, flat
   + `index.md` + tags is strictly better.)
2. **Cluster size** — the split yields **at least two** candidate child groups, each with **≥ 5
   pages** that clearly belong together. Never create a subfolder for fewer than 5 (hard floor 3);
   a 2–3 page "cluster" stays in the parent.
3. **Closed, deterministic key** — the group is defined by a **stable, enumerable key** you can
   assign a *future* page to without guessing. Allowed keys, in priority order:
   - **entity kind** (for `entities/`): `people/`, `products/`, `projects/`, `orgs/`,
     `standards/`, `models/` — a small closed set.
   - **repo / project scope** (for `queries/`, `concepts/`, `comparisons/`): the repository or
     product name, e.g. `queries/fanplus-api/`, `concepts/fanplus-api/`, `queries/proxmox-homelab/`.
     The repo/project name is a deterministic key the agent always knows.
   - **source type** (for `raw/`): `articles/`, `transcripts/`, `assets/`, etc. (already in use).
   - **bounded technical domain** (fallback, mainly `concepts/`): a stable, well-known,
     mutually-exclusive domain or subtype such as `kafka/`, `database/`, `testing/`,
     `database/postgresql/`. Allowed **only** when the domain is stable and non-overlapping, every
     new page's membership is obvious, and you record a one-line membership rule (below). Prefer a
     repo/project key over a topic key whenever both fit.
4. **Mutual exclusivity (hesitation test)** — every current *and* reasonably-expected page maps to
   exactly one group. If any page plausibly fits two candidate folders, **do not split** — keep flat
   and disambiguate with tags/`index.md`/wikilinks. "Fits two folders" means the answer is *zero* new
   folders, not two.

If all four hold, create the subfolder **and relocate every existing sibling that belongs in it in
the same pass** (never leave a half-done split where some Kafka pages are in `concepts/kafka/` and
others are still flat).

## When to keep it flat (any one is enough)

- The current folder has **≤ ~15–20 direct pages**.
- There is only **one** real child group, so the "split" would be only a rename and leave a large
  `misc` residue.
- The only available grouping is an **open-ended or overlapping topic** where an agent would
  hesitate on a new page → use tags + `index.md` sections + wikilinks instead.
- The candidate subfolder would hold **< 5 pages** → keep those pages in the parent.

## Recursive subdivision (the node-split model)

Subfoldering is **recursive and not capped at a fixed depth.** Treat every folder as a node with a
soft capacity, exactly like a B-tree/quadtree node: when it overflows and a real closed sub-key has
emerged, split it into keyed child subfolders — then apply the **same** test to each child as *it*
grows. Depth grows only where volume and a genuine distinction warrant it.

```text
concepts/database/                     ← overflowed, split by DBMS (a closed "kind" key)
concepts/database/postgresql/          ← later overflows on its own → split again by subtopic
concepts/database/postgresql/indexing/
concepts/database/postgresql/transactions/
concepts/database/mysql/               ← still small → stays flat (asymmetric depth)
```

The four-part split test from "When to create a subfolder" **re-applies at every level**, plus a
stop rule:

1. **Warrant / volume, per node.** Split a node only once it is genuinely full — consider at
   **>~15–20 direct children**, overdue by **~30**. A small node never splits, no matter how deep in
   the tree it sits. (Library "literary warrant": never create a child until items exist to fill it.)
2. **≥2 populated children.** The split must yield **at least two** child folders, each holding
   **≥5 pages** (hard floor 3). One child = a rename, not a split; children of 1–2 pages =
   over-classification, the single most common real-world failure (~91% of catalogs over-split).
   Prune a child back into its parent if it falls below the floor.
3. **One closed, discriminating axis (MECE).** Divide on a **single** stable, objectively-assignable
   key that puts every current *and* future page in exactly one child. The children should need
   *different* handling/attributes — the "is-a / different-attributes" test. Don't re-split on an
   axis that reproduces the same grouping; don't split on a property all pages share.
4. **Type-distinction, not value-distinction (STOP rule).** Keep subdividing while the distinction is
   a *kind* (`postgresql/` vs `mysql/` = different systems with different behavior). **Stop** the
   moment the only remaining distinctions are *values* of a shared attribute (version 14 vs 15, a
   date, a status, a size) — express those with **tags**, never a deeper folder. This is the
   GS1-Brick→attribute and ontology subclass-vs-property boundary.
5. **No skipped levels.** Go exactly one step more specific per level; never jump from a broad node
   straight to a hyper-narrow one (insert the intermediate node instead).

**Breadth before depth.** When a node is large but conceptually *uniform* — no clean sub-axis, pages
differ only by value — **widen it** and lean on tags + `index.md`; do **not** invent an artificial
level. Depth is added only where a real sub-distinction has emerged. This matches the empirical
result that broad-shallow beats narrow-deep *unless* each deeper step carries strong "scent" (a
clear, predictable label).

**Asymmetric depth is correct.** Branches are as deep as their own content warrants and no deeper:
`concepts/database/postgresql/` may nest three levels while `concepts/database/mysql/` stays a flat
folder. Never force uniform depth across siblings (LCC and taxonomy practice both make depth uneven
by design).

**Interior folders are navigation; leaves hold pages.** Once a folder gains children, treat it as a
hub: pages should live in the leaf folders, the interior folder carries its `SCHEMA.md` membership
rule, and the auto-maintained `index.md` stays the map. (Mirrors B-tree interior keys being
navigation-only while leaves hold the data.)

There is **no fixed depth number** — but each level must be *earned* by all five conditions above.
In practice most branches settle at 2–3 levels because warrant runs out (the distinction becomes
value-based) before they go deeper; a branch reaches 4+ only when a genuinely large, kind-structured
domain justifies it. "Earn every level" is the cap, not a hard integer.

## Breadth

Do not cap the number of files per folder at "7±2" — that is a memory-recall limit, not a limit for
a scannable, sorted, searchable list. A flat folder of 15–30 pages, or a subfolder of many pages, is
fine when it is coherent and well labeled. The real constraints are **warrant, information scent,
and deterministic placement**, not raw count alone. Keep total top-level folders at the fixed five
(the ≤10 ceiling everyone recommends).

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
  then bounded, mutually-exclusive domains that clear ≥5: `kafka/` (5), `database/` (9),
  `testing/` (6), `knowledge-base/` (9). Leave true one-offs and fuzzy catch-alls flat rather than
  forcing a `misc` folder. **Then recurse:** once `concepts/database/` itself overflows (>~15–20)
  and its pages cluster by DBMS, split it again → `concepts/database/postgresql/`,
  `concepts/database/mysql/`; if `postgresql/` later overflows on a subtopic axis, split once more
  (`.../postgresql/indexing/`, `.../postgresql/transactions/`). Stop when the remaining distinction
  is a version/value → tag it instead. Branches stay asymmetric (`mysql/` may remain flat).
- **`comparisons/` (9) → keep flat.** Under 20 and heterogeneous; no closed cluster reaches 5.

Misplacement fixes the audit found (candidates for the relocation procedure):

- `concepts/embeddings.md` — 0-byte empty stub with no frontmatter → populate or delete.
- `concepts/innodb-update-mvcc-undo-log-source-code.md` — content is an answered investigation
  ("판정 요약" / "답변에 재사용할 짧은 문장") → `queries/` (`type: concept` → `query`).
- `concepts/hermes-agent-project-memory.md` — a personal project/environment memory dump, not a
  reusable concept → `entities/` (or a dedicated memory page).

## Research basis

Research basis comes from two passes: first, 10 agents audited the wiki shape and surveyed 200+
documents for folder-vs-tag placement; then, after the recursive-depth correction, 7 agents reviewed
160+ additional sources specifically on **successive subdivision** (library classification,
Johnny.Decimal expansion, product taxonomies, IA depth/breadth studies, ontology granularity,
filesystem/docs trees, and B-tree/quadtree-style node splitting). Convergent, cross-validated
thresholds:

| Rule | Value | Sources (representative) |
| --- | --- | --- |
| Depth | recursive, no fixed cap — each level earned by warrant; breadth before depth; asymmetric | DDC/LCC literary warrant, B-tree/quadtree node-split, ontology 2-child rule, IA scent |
| Node-split model | folder = node with soft capacity; overflow → split into keyed children; recurse | B-tree/B+-tree, quadtree, R-tree, HTree, burst-trie |
| Stop-deepening rule | stop when the distinction is an attribute *value*, not a *kind* → use tags | GS1 Brick→attribute, Shopify leaf→metafield, ontology subclass-vs-property |
| Top-level folder count | keep the fixed 5 (≤10 ceiling) | large-vault surveys, Johnny.Decimal, PARA |
| Subdivide trigger | current node > ~15–20 direct pages, overdue by ~30, AND ≥2 child groups of ≥5 passing the "different-handling" test | IA depth/breadth, folder-depth best practice, literary warrant |
| Subfolder floor | never < 5 pages (hard floor 3) | IA thin-content floors, Johnny.Decimal |
| Split key | closed/deterministic only (kind, repo/project, source, bounded domain) — never open topic | agent-memory KB, MediaWiki namespaces-vs-categories, Diátaxis |
| Hesitation test | a page fitting two folders → create zero, use tags/links | Zettelkasten, Obsidian folders-vs-tags, PARA |
| Creation timing | just-in-time; never pre-create empty folders | PARA "desire paths", Diátaxis "don't build empty shells" |
| Per-subfolder membership rule | one line, recorded in `SCHEMA.md` | DokuWiki namespace docs, large-vault naming practice |
| Topic navigation without folders | tags + `index.md` + MOC/hub notes | LYT/MOC, digital-garden/Quartz, TiddlyWiki |

Key methodology anchors: Johnny.Decimal (standard shallow grid, plus "expand one area" when a node
needs more levels); PARA (just-in-time folders, no empty structures); DDC/LCC/UDC/Colon
classification (literary warrant, hierarchical force, no skipped specificity levels, facet order);
SKOS/ontology practice (all-and-some/is-a test, no single-child narrower term, subclass-vs-property
boundary); product taxonomies (deepest accurate category, but stop at leaf attributes/metafields);
classic IA (local depth where information scent improves, broad-shallow when scent is weak);
filesystem/docs trees (recursive 30–50 item split bands, README/index at each level); B-tree,
quadtree, R-tree, HTree, and burst-trie node splitting (overflow → keyed children → recurse);
Zettelkasten/Obsidian/MOC practice (topics remain links/tags/hubs, not duplicate folder homes); and
agent-memory KBs — CoALA, Letta/MemGPT labeled blocks, Karpathy's LLM Wiki, "Obsidian-for-AI"
second brains — which route by a schema file rather than by guessing topic folders.
