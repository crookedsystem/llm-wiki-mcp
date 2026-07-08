# Writing Research Map

Use this reference when justifying or changing the writing guidance in the `writing-*` references — adding or removing a rule, resolving a conflict between rules, or answering why the policy exists. Do not load it during ordinary note writing; the operational rules live in the four topic references plus `writing-document-structure.md`.

## Table of Contents

- [Corpus Summary](#corpus-summary)
- [Research Axes](#research-axes)
- [Supported Beliefs](#supported-beliefs)
- [Refuted Beliefs](#refuted-beliefs)
- [Resolved Trade-offs](#resolved-trade-offs)
- [Toss Technical Writing Findings](#toss-technical-writing-findings)
- [Representative References](#representative-references)
- [When to Update This Map](#when-to-update-this-map)

## Corpus Summary

The writing references were derived from a multi-agent research pass (2026-07): 24 research tracks (8 Toss-focused deep reads plus 16 broad dimensions), 712 reviewed sources, followed by a 10-persona two-round adversarial debate and a synthesis pass. The personas were: minimalist, structuralist, visualization advocate, reader-empathy, accuracy-rigor, cognitive-science empiricist, storyteller, Toss-style advocate, practicing developer, and contrarian critic.

The 16 broad dimensions: diction, syntax, cohesion, document structure (pyramid/BLUF), visualization, cognitive science of reading, plain language, technical-writing standards, summary/TL;DR craft, code explanation (worked examples), reader-centered writing, editing/revision, information hierarchy/typography, examples and analogy, narrative structure, and canonical writing literature.

## Research Axes

Cognitive-science work locates comprehension cost in working memory: lexical access (word frequency), parsing (sentence length, dependency distance), and re-inference (missing given→new chains, absent causal wiring). Placement research (F-shaped scanning, serial-position effect, ~15-second abandonment) shows information order dominates sentence polish.

Technical-writing standards (Google, Microsoft, plain-language guidelines) converge on: audience = needed knowledge − held knowledge; active voice; verb-first instructions; defined jargon; parallel lists.

Instructional research adds the worked-example effect and its inversion (expertise reversal): novices need full walkthroughs, experts are slowed by them — which motivates "separate, don't abbreviate" for detail sections, and problem-first ordering for tutorials (conclusion-first triggers fluency illusion in learners).

## Supported Beliefs

1. Conclusion-first (BLUF/pyramid) layout is the primary comprehension lever for report-style documents.
2. The "summary → visualization → detail" skeleton is sound **as the default for report/result documents**; no debate persona rejected the skeleton itself.
3. Weed cutting (adverbs, hedges, duplications) raises signal-to-noise with no measured downside.
4. Detail sections should be dual-tracked by expertise: full walkthrough available, core snippet in the body.

## Refuted Beliefs

1. "Shorter is always better" — uniform brevity kills rhythm; enforce a ceiling, design variance.
2. "All connectives are weeds" — causal connectives measurably aid reading speed and recall; only additive ones are default-prunable.
3. "More visualization is better / every document gets a diagram slot" — visualization is conditional (three gates); screenshots are stale-content debt.
4. "Failure paths and rejected alternatives are clutter" — they define the applicability boundary of the conclusion; deleting them over-generalizes it.
5. "Write the summary first" — summary is a reading-order rule, not a writing-order rule; extract it last or it drifts from the body.
6. "Toss does it, so it's correct" — Toss metrics are descriptive statistics, not causal evidence; adopt the reproducibility method, not the brand habit.

## Resolved Trade-offs

| Tension | Resolution |
| --- | --- |
| Conclusion-first vs narrative hook | Write the summary's first sentence as a problem→outcome hook: reveals the conclusion and keeps tension |
| Completeness vs density of detail | Separate, don't abbreviate: core snippet inline, full code linked |
| Diagram placement (one slot vs layered) | Role-based placement, each instance individually gated |
| Conclusion-first universality | Branch by document type: reports yes; tutorials problem-first; references tables-only |

## Toss Technical Writing Findings

Toss's eight writing principles (weed cutting, remove empty sentences, focus on key message, easy to speak, predictable hint, suggest over force, universal words, find hidden emotion) derive from five core values (clear, concise, casual, respect, emotional). The deeper finding is organizational: Toss systematizes writing — error-message washing → templates → design components, principle-based AI review bots on PRs, and a single-source knowledge platform — so quality comes from reproducible systems rather than individual skill. That is the pattern this skill copies by encoding writing policy into references instead of relying on per-session judgment.

Toss article skeleton observed across their engineering blog: definition → concrete org-scale numbers → problem → 3–4 requirements → attempts and limits → final solution → quantified outcome; problem-posing headings; one accent color per chart; numbers restated in prose.

## Representative References

- Toss: [8 writing principles](https://toss.tech/article/8-writing-principles-of-toss), [error-message system](https://toss.tech/article/introducing-toss-error-message-system), [technical writing role](https://toss.tech/article/technical-writing-1), [toss/technical-writing (GitHub)](https://github.com/toss/technical-writing)
- Standards: [Google developer documentation style guide](https://developers.google.com/style/highlights) and [tech writing course](https://developers.google.com/tech-writing), [Microsoft writing style guide](https://learn.microsoft.com/en-us/style-guide/top-10-tips-style-voice), [plainlanguage.gov](https://www.plainlanguage.gov), [Write the Docs principles](https://www.writethedocs.org/guide/writing/docs-principles/)
- Cognition: worked-example effect and expertise reversal (Sweller et al.), [BLUF](https://en.wikipedia.org/wiki/BLUF_(communication)), Minto pyramid, [NN/g F-shaped pattern](https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content/), Pinker on the curse of knowledge
- Craft: Strunk & White *The Elements of Style*, Zinsser *On Writing Well*, Orwell *Politics and the English Language*, 국립국어원 공공언어 바로 쓰기

## When to Update This Map

- A writing rule in the topic references is challenged by newer evidence — record the change and its source here.
- Korean-specific readability research lands that recalibrates the English-corpus defaults (25 words/40 syllables, given-new, dependency locality); these are flagged as approximations in `writing-sentence-structure.md`.
- The vault's note-body pattern in `SKILL.md` changes shape, invalidating the wiki-adaptation sections of the topic references.
