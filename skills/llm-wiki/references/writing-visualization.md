# Writing: Visualization

Use this reference when considering a diagram, table, or code block inside a note body — deciding whether to add one at all, and how to design it if so. Do not load it for text-only edits.

## Table of Contents

- [Core Rule](#core-rule)
- [The Three Gates](#the-three-gates)
- [Design Rules](#design-rules)
- [Code Snippets as Visualization](#code-snippets-as-visualization)
- [Honesty](#honesty)
- [Wiki Note Adaptation](#wiki-note-adaptation)
- [Checklist](#checklist)

## Core Rule

"A picture beats a thousand words" is false as stated. A **designed** picture beats text **only when it passes three gates**; otherwise text plus explicit numbers is clearer and cheaper to maintain. A diagram earns its place by removing reconstruction cost — the reader no longer has to simulate an ordered interaction (auth → request → render) in their head — and by double-checking the prose.

## The Three Gates

Skip the visualization unless all three pass:

| Gate | Question | Pass condition |
| --- | --- | --- |
| 1. Contrast | Is there a real before/after, trend, or ordered interaction? | If nothing is being compared or sequenced, do not draw it |
| 2. Maintainability | Will it update together with the content? | Text-based formats only (Mermaid, markdown tables). Screenshots/PNGs rot into stale-content debt |
| 3. Honesty | Could it mislead? | Axes start at 0; a highlighted gain is accompanied by the metric that got worse, if one exists |

## Design Rules

- **One diagram = one question.** If explaining it needs 5+ bullets, split it.
- Place the diagram **immediately after** the paragraph that motivates it; that preceding sentence is its caption. Do not open a section with an unexplained figure.
- Emphasize **one metric only**, with accent styling covering ≤5–10% of the figure; everything else stays neutral.
- Label arrows with their **role** (`인증`, `데이터 요청`), never bare `A → B`.
- Boxes name the role before the technology: `캐시 서버(Redis)`, not `Redis`.
- Numbers live in **both** the figure and the prose (`5배 개선`, `36분 단축`) — if the figure goes stale, the fact survives in text, and the reader can verify one against the other.
- Never encode meaning in color alone; pair it with a text label (accessibility, and Mermaid themes vary by renderer).

## Code Snippets as Visualization

- Precede every snippet with a one-line **why-first** statement: what problem this code answers, before what it does.
- Chunk snippets over ~20 lines into `설정 → 핵심 로직 → 결과 처리` with a sentence between chunks.
- Comment the **why**, never the what; a line whose purpose is obvious carries no comment.
- In before/after diffs, every changed hunk gets a "왜 바꿨나" note — a diff without reasons does not transfer.
- Keep only the core snippet in the note; full runnable code belongs in a linked `raw/` asset or repository path (separate, don't abbreviate).

## Honesty

Single-metric highlighting plus a truncated axis is the grammar of cherry-picking — misleading without lying. The emphasis you add hides the editorial choice you made. Counter it structurally: next to the improved metric, state what regressed or what it cost (`빌드 36분 단축, 캐시 디스크 2.1GB 증가`). If nothing regressed, say so explicitly.

## Wiki Note Adaptation

- Mermaid blocks render in Obsidian/Quartz; they are the only sanctioned diagram format for synthesized pages. Store immutable original images under `raw/` and link them instead of embedding meaning-bearing screenshots in synthesized pages.
- Markdown tables are the preferred visualization for parallel facts (comparisons, option matrices) — `comparisons/` pages should usually lead with a table, not a diagram.
- A diagram counts toward the ~200-line split threshold like any other content; a page carrying three diagrams is usually three pages.

## Checklist

- [ ] All three gates pass (contrast exists / text-based format / honest axes and trade-off shown).
- [ ] One question per diagram; motivating sentence directly above it.
- [ ] One accent metric; roles on arrows and boxes.
- [ ] Numbers duplicated in prose next to the figure.
- [ ] Snippets: why-first line, ≤20-line chunks, why-only comments, full code linked not pasted.
- [ ] No color-only meaning; regressed metrics stated alongside gains.
