# Writing: Sentence Structure (Syntax)

Use this reference when drafting or editing note prose at the sentence level — splitting overlong sentences, fixing weak voice, or converting enumerations. Do not load it for document-level ordering (see `writing-document-structure.md`).

## Table of Contents

- [Core Rules](#core-rules)
- [Length: a Ceiling, Not a Floor](#length-a-ceiling-not-a-floor)
- [Subject–Verb Proximity](#subjectverb-proximity)
- [Voice and Verb Strength](#voice-and-verb-strength)
- [Parallelism and Lists](#parallelism-and-lists)
- [Evidence Caveat](#evidence-caveat)
- [Checklist](#checklist)

## Core Rules

- **One sentence = one message.** Split when a subordinate clause introduces a *new* idea; keep it when it merely extends the current one.
- Split signals for Korean: three or more chained connective endings (`~고 / ~며 / ~는데`) in one sentence, or three or more commas.
- Ceiling: roughly **25 words (English) / 40 syllables (Korean)** per sentence. Past that, parsing cost dominates content.

## Length: a Ceiling, Not a Floor

Uniformly short sentences kill rhythm and read as a bullet list wearing prose. Enforce only the ceiling; then **design variance**: place a short declarative sentence as a stop-point after a dense stretch. The optimization target is the distribution of lengths, not the average.

## Subject–Verb Proximity

Keep the subject and its verb close (dependency locality). Move modifiers and inserted clauses out from between them — to the front of the sentence or, for complex qualifying material, to the end (the new-information slot).

- Weak: `이 캐시는, 처음 도입 당시 세 팀이 각각 다른 TTL 정책을 쓰고 있었기 때문에, 자주 무효화되었다.`
- Strong: `처음 도입 당시 세 팀이 각각 다른 TTL 정책을 썼다. 그래서 이 캐시는 자주 무효화되었다.`

## Voice and Verb Strength

- Prefer active voice and positive statements; remove double negation (`~하지 않는 것은 아니다`).
- Undo nominalization: `검증을 수행한다` → `검증한다`; `~에 대한 분석을 진행했다` → `~를 분석했다`.
- Delete weak scaffolding: `there is/are`, `~할 수 있다` when the sentence asserts a fact rather than a capability.
- Start instructions with the verb (imperative), matching how the skill's own checklists are written.

## Parallelism and Lists

- Parallel concepts take parallel grammar: all list items start with a verb, or all are noun phrases — never mixed.
- **Three or more enumerated items in prose become a markdown list or table.** This is also a maintenance rule: adding or removing an item then becomes a one-line diff instead of a sentence rewrite.
- In wiki notes this maps directly onto `## Key facts` bullets: one fact per bullet, parallel form, dated where relevant.

## Evidence Caveat

The 25-word/40-syllable ceiling, given-new ordering, and dependency-locality findings come mostly from English-language corpora. For Korean (agglutinative), treat them as calibrated defaults, not laws — when a Korean sentence reads naturally aloud at 45 syllables, the read-aloud test wins over the counter.

## Checklist

- [ ] No sentence carries two new ideas; connective-ending chains ≤2.
- [ ] Sentences over ~25 words / 40 syllables split, unless the read-aloud test passes.
- [ ] Subject and verb adjacent; inserted clauses relocated.
- [ ] Nominalizations undone; double negation and weak `~할 수 있다` removed.
- [ ] 3+ enumerations converted to a list/table with parallel grammar.
- [ ] Short stop-point sentences placed after dense passages (variance, not uniformity).
