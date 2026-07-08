# Writing: Document Structure and Summary

Use this reference when composing or restructuring a substantial synthesized note body — deciding section order, writing the `## Summary` section, choosing headings, or judging whether the "summary → visualization → detail" skeleton fits the page. Do not load it for trivial one-line updates or link-hygiene patches.

## Table of Contents

- [Core Rule](#core-rule)
- [Declare the Document Type First](#declare-the-document-type-first)
- [The Default Skeleton](#the-default-skeleton)
- [Summary Rules](#summary-rules)
- [Reading Order vs Writing Order](#reading-order-vs-writing-order)
- [Headings and Hierarchy](#headings-and-hierarchy)
- [Wiki Note Adaptation](#wiki-note-adaptation)

## Core Rule

The primary variable of comprehension is not sentence quality but **information placement order**. Readers decide within roughly 15 seconds whether to keep reading; a conclusion-first layout (BLUF — Bottom Line Up Front, Minto pyramid) is what retains a scanning reader. Sentence and word discipline are second-order tools that make the placement visible.

## Declare the Document Type First

"Summary → visualization → detail" is the **default for report/result-style documents, not a universal law**. Branch the structure by type before writing:

| Type | Structure | Why |
| --- | --- | --- |
| Report / result (most `queries/`, `comparisons/`) | Summary → visualization → detail | Reader wants the verdict; supports scan-and-leave |
| Learning / tutorial | Problem → attempts and failures → worked example → conclusion | Conclusion-first triggers fluency illusion: the reader believes they understood and skips the walkthrough |
| Pure reference (API shapes, error tables) | BLUF + tables + parallel lists, no narrative | Narrative and diagrams slow lookup |

State the intended reader in one sentence when it is not obvious (for example "HTTP는 알지만 SSR은 처음인 독자"). A page that never chose its reader explains too much and too little at once.

## The Default Skeleton

For report-style pages, use this layer order:

| Layer | Role | Size / rule |
| --- | --- | --- |
| 1. Summary | Conclusion: what + so-what | 5–10% of body, ~3 sentences, 1–2 key numbers |
| 2. Complication | Why this was hard / why it matters | 1–2 sentences of minimal context |
| 3. Visualization | Double-checks the conclusion | Only when it passes the 3 gates in `writing-visualization.md` |
| 4. Detail (walkthrough) | Evidence and reproducibility | Why-first, chunked; full code split out, not abbreviated |
| 5. Closing | Return to the opening problem | Outcome recap, wider context |

Detail is **separated, not abbreviated**: keep the core snippet in the body and move full runnable code to a linked raw source or external file. Deleting failure paths and rejected alternatives is over-pruning — they define the boundary conditions of the conclusion and are part of reproducibility.

## Summary Rules

- 3 sentences, 5–10% of the body, directly under the title (in wiki notes: the `## Summary` section).
- First sentence is a problem→outcome hook, not a topic statement: `[문제]가 있었고 [해결]으로 [수치] 개선` beats "이 문서는 ~를 다룬다".
- Include 1–2 concrete numbers when they exist; exclude background, process, and methodology.
- Group supporting arguments into **3 or fewer MECE clusters**; 4+ items must be compressed into higher-level categories.

## Reading Order vs Writing Order

"Summary first" is three different rules — conflating them corrupts the summary:

1. **Reading order** — the conclusion sits at the top. Supported; always apply.
2. **Writing order** — the summary is **extracted last**, after the body and code are final. Writing it first causes drift: the summary promises what the body no longer says. A summary that disagrees with its body is the most dangerous form of misinformation in a knowledge base.
3. **Maintenance order** — headings and first sentences must be strong enough that the summary can be regenerated from them alone. When updating a note body, re-derive the `## Summary` from the updated sections in the same write.

## Headings and Hierarchy

- Headings are problem-posing, not noun labels: `설계`, `구현` ❌ → `OO가 필요한 이유`, `초기 설계의 문제점` ⭕.
- Reading only the headings top-to-bottom must yield `왜 → 어떻게 → 결과`.
- Each paragraph's first sentence is its conclusion (mini-BLUF); heading + first sentences alone should carry the argument.
- Never jump from problem to solution without stating the requirements/constraints (3–4 items) in between.

## Wiki Note Adaptation

The standard note body (`## Summary`, `## Key facts`, `## Relationships`, `## Open questions`, `## Sources`) already implements the skeleton — map layers onto it instead of inventing new sections:

- `## Summary` = layer 1+2 (conclusion + minimal complication). Apply the 3-sentence extraction rule.
- `## Key facts` = layers 3–4. Put a Mermaid diagram or table here only when it passes the visualization gates; keep facts dated and source-backed.
- Long walkthroughs that would push the note past ~200 lines are split into a linked sub-page, mirroring the "separate, don't abbreviate" rule.
- `## Open questions` is where rejected alternatives and unverified boundaries live when they would bloat `Key facts`.
- Pass the same extracted conclusion as the `summary` argument of `kb_write_note` so `index.md` and `log.md` inherit the hook sentence.
