# Writing: Word Choice (Diction)

Use this reference when drafting or editing note prose — choosing between candidate words, introducing technical terms, or running a wording cleanup pass. Do not load it for structural decisions (see `writing-document-structure.md`) or link hygiene.

## Table of Contents

- [Core Rule](#core-rule)
- [Prefer Short, Familiar Words](#prefer-short-familiar-words)
- [Technical Terms](#technical-terms)
- [One Concept, One Term](#one-concept-one-term)
- [Weed Cutting in Two Passes](#weed-cutting-in-two-passes)
- [Checklist](#checklist)

## Core Rule

Word difficulty is not a taste question; it is a **lexical-access cost** question. Low-frequency, multi-syllable Sino-Korean or Latinate words consume working-memory budget that the reader needs for the actual argument. The goal of plain wording is scan-ability, not character count.

## Prefer Short, Familiar Words

Replace formal register with everyday register when the meaning is identical:

| Avoid | Prefer |
| --- | --- |
| 활용하다 | 쓰다 |
| 진행하다 | 하다 |
| 용이하다 | 쉽다 |
| 제고하다 | 높이다 |
| 금번 / 익일 | 이번 / 다음 날 |
| utilize / commence | use / start |

Also avoid double-passive Korean (`~되어지다`), Japanese-derived bureaucratic phrasing, and fashionable slang that a non-developer would not recognize (Toss "Universal Words": would a parent understand it?).

## Technical Terms

- Define every jargon term with **one sentence at first appearance**, or link the existing wiki page that defines it: `[[concepts/expertise-reversal|expertise reversal]]`.
- If a paragraph contains **more than 3 undefined terms**, rewrite the paragraph — the intended reader does not exist for it. (Google's framing: a good document = knowledge the reader needs − knowledge the reader already has.)
- Spell out an acronym at first use with the abbreviation in parentheses; use the short form afterward.

## One Concept, One Term

- One concept = one term across the page and, ideally, across the vault: never alternate `유저`/`사용자` or `노트`/`페이지` for style.
- Synonym variation breaks `kb_search_notes` retrieval, grep, alias matching, and future translation — six months later the two words read as two different concepts.
- The vault-level term registry is `SCHEMA.md`'s tag taxonomy plus entity aliases; check them before coining a new term for something that already has a page.

## Weed Cutting in Two Passes

Weeds are words whose deletion changes nothing for the reader. Cut them in two separated passes, because a single aggressive pass destroys cohesion:

1. **Pass 1 (safe):** delete adverbs, redundancies, and hedges — `정말`, `사실`, `기본적으로`, `앞으로`, `~것 같다`, `~할 수 있게 되었습니다`; collapse duplicated pairs (`미리 예방` → `예방`, `다시 재설정` → `재설정`).
2. **Pass 2 (protect cohesion):** review connectives **individually**. Causal connectives (`그래서`, `따라서`, because) measurably speed up reading and recall — they are structure, not weeds. Additive connectives (`그리고`, `또한`) contribute little and may go. Never run a blanket delete over connectives.

The deletion test is reader-relative: not "does the author need this word?" but "does the reader's understanding lose anything without it?" Failure paths, trade-offs, and why-explanations are **not** weeds.

## Checklist

- [ ] Every jargon term defined or wikilinked at first appearance; ≤3 undefined terms per paragraph.
- [ ] No synonym alternation for the same concept; aliases checked against existing pages.
- [ ] Pass 1 weeds removed (adverbs, hedges, duplicated pairs).
- [ ] Pass 2 done separately: causal connectives kept, additive ones pruned deliberately.
- [ ] Formal-register words downgraded to everyday equivalents where meaning is unchanged.
