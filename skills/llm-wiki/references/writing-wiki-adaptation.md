# Writing: Wiki Note Adaptation

Use this reference when composing or substantially rewriting a synthesized note body. It maps the shared writing rules onto the vault's note shape; it does not restate them. The canonical writing rules live in the shared writing references installed by the prompt repository (`uv run scripts/init_ai_configs.py` copies them to every agent's skills root):

- `~/.claude/skills/_shared/writing/document-structure.md` — document-type branching, summary → visualization → detail skeleton, summary extraction rules
- `~/.claude/skills/_shared/writing/diction.md` — word choice, jargon definitions, one-concept-one-term, two-pass weed cutting
- `~/.claude/skills/_shared/writing/sentence-structure.md` — one sentence = one message, the 40-syllable ceiling, subject–verb proximity
- `~/.claude/skills/_shared/writing/flow.md` — given→new chains, topic sentences, connective policy
- `~/.claude/skills/_shared/writing/visualization.md` — the three gates for diagrams/tables, code snippet explanation
- `~/.claude/skills/_shared/writing/research-map.md` — research basis; load only when changing the rules themselves

If that directory is missing on this machine, do not block the write: apply the always-on defaults in `SKILL.md`'s "Bundled writing references" section and continue.

## Mapping the skeleton onto a note body

The standard note body (`## Summary`, `## Key facts`, `## Relationships`, `## Open questions`, `## Sources`) already implements the report-style skeleton — map layers onto it instead of inventing new sections:

- `## Summary` = conclusion + minimal complication. Apply the extraction rule: write it **after** the rest of the body is final, ~3 sentences, first sentence as a problem→outcome hook. Pass the same extracted conclusion as the `summary` argument of `kb_write_note` so `index.md` and `log.md` inherit the hook sentence.
- `## Key facts` = visualization + detail layers. A Mermaid diagram or markdown table goes here only when it passes the three gates; keep facts dated, source-backed, and one per bullet in parallel grammar.
- `## Relationships` bullets are causal edges: state *why* each linked page matters, not just that it exists.
- `## Open questions` is where rejected alternatives and unverified boundaries live when they would bloat `Key facts`.

## Wiki-specific rules

- Long walkthroughs that would push a note past ~200 lines are split into a linked sub-page — the vault's version of "separate, don't abbreviate".
- Mermaid blocks are the only sanctioned diagram format for synthesized pages (they render in Obsidian/Quartz and diff as text). Store immutable original images under `raw/` and link them; never embed meaning-bearing screenshots in synthesized pages.
- Jargon definition can be a wikilink instead of an inline sentence when the defining page exists: `[[concepts/expertise-reversal|expertise reversal]]` satisfies first-use definition.
- `comparisons/` pages should usually lead with a markdown table, not a diagram — parallel facts are the table's home turf.
- Document-type branching maps to page types: `queries/` and `comparisons/` are report-style (conclusion first); a tutorial-style walkthrough saved as a `query` may keep problem-first ordering inside `## Key facts` while `## Summary` still states the conclusion for scanners.
