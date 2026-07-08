# Writing: Flow and Cohesion

Use this reference when prose feels choppy or disconnected — ordering sentences within a paragraph, wiring paragraphs together, or deciding which connectives to keep. Do not load it for single-bullet edits.

## Table of Contents

- [Core Rule](#core-rule)
- [Given → New Chains](#given--new-chains)
- [Topic Sentences](#topic-sentences)
- [Connective Policy](#connective-policy)
- [Paragraph Completeness](#paragraph-completeness)
- [Section Transitions](#section-transitions)
- [Checklist](#checklist)

## Core Rule

Flow is what saves the reader from re-inferring "what is this sentence about?" at every step. It is built from two mechanisms: information ordering inside sentences (given → new) and explicit logical wiring between them (causal connectives).

## Given → New Chains

Open each sentence with information the reader already holds (the given — usually the grammatical topic/subject) and place new information at the end. The new information of one sentence becomes the given of the next, forming a chain:

- Chained: `이 서버는 노트를 해시로 검증한다. 그 해시가 어긋나면 쓰기를 거부한다. 거부된 쓰기는 재읽기 후에만 재시도할 수 있다.`
- Broken: `이 서버는 노트를 해시로 검증한다. 재읽기 후에만 재시도가 가능한 것이 거부된 쓰기다.`

When a sentence must introduce two new items, split it — one of them has no given to attach to.

## Topic Sentences

- The first sentence of a paragraph is its conclusion (mini-BLUF). A reader skimming heading + first sentences must still get the full argument.
- If the natural draft put the conclusion last (미괄식), reorder during editing rather than rewriting: move the closing sentence to the front and smooth the joins.
- One paragraph = one idea. A second thesis inside a paragraph is a paragraph boundary you missed.

## Connective Policy

Connectives are not decoration; they are typed edges, and the types have different value:

| Type | Examples | Policy |
| --- | --- | --- |
| Causal | 그래서, 따라서, ~때문에, because | **Keep.** Measurably speeds reading and improves recall of the following sentence. |
| Contrastive | 하지만, 그러나, however | Keep where the contrast is real; it marks a turn the reader must not miss. |
| Additive | 그리고, 또한, moreover | Mostly prune. Adds little cohesion; lists do this job better. |

Insert a transition word only where the logical relation is genuinely ambiguous without it. This policy is the pass-2 counterpart of weed cutting in `writing-diction.md` — never bulk-delete connectives.

## Paragraph Completeness

A paragraph is complete when it answers three questions: **What** (the fact/claim), **Why** (why the reader should care), **How** (how it is used or what follows from it). Aim for 3–5 sentences; past ~5 rendered lines, look for the hidden second idea.

## Section Transitions

End a section, or open the next one, with a one-sentence forecast of what comes next (predictable hint): `다음 절에서는 이 해시 검증이 실패하는 두 경우를 다룬다.` This keeps the given→new chain alive across section boundaries, where it most often breaks.

In wiki notes, `## Relationships` bullets serve this role between pages: each bullet states *why* the linked page matters, not just that it exists — that is the causal edge in the graph.

## Checklist

- [ ] Each sentence opens with given information; new information sits at the end.
- [ ] Each paragraph's first sentence states its conclusion; one idea per paragraph.
- [ ] Causal connectives preserved; additive ones pruned deliberately.
- [ ] Every paragraph answers what / why / how in 3–5 sentences.
- [ ] Section transitions forecast the next section in one sentence.
- [ ] `## Relationships` bullets explain the why of each link.
