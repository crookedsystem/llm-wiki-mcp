# Memory Write Policy

Use this reference when deciding whether to create, update, merge, delete, or ignore LLM Wiki memory. Use it when changing stop-hook behavior, prompt hint write rules, no-store rules, review horizons, or privacy-sensitive memory handling.

## Table of Contents

- [Write Decision Flow](#write-decision-flow)
- [Durability Thresholds](#durability-thresholds)
- [No-Store Rules](#no-store-rules)
- [Update and Merge Rules](#update-and-merge-rules)
- [Provenance and Review Horizons](#provenance-and-review-horizons)
- [Stop-Hook Capture Rules](#stop-hook-capture-rules)
- [Prompt Cue Quality Bar](#prompt-cue-quality-bar)

## Write Decision Flow

Before storing memory, answer these questions in order:

1. Is this useful for a future task, not only the current reply?
2. Is there a stable scope owner: person, team, repo, service, module, path, workflow, concept, incident, PR, or decision?
3. Is the source explicit enough to cite or summarize without inventing evidence?
4. Can it be represented as a short cue rather than a transcript dump?
5. Does the cue have an action effect: do, avoid, check, prevention cue, constraint, reminder, or retrieval target?
6. Is there a review date, expiry, or reason it is durable?
7. Have duplicate or broader notes been checked with `kb_context(mode="prewrite")` and, when needed, `kb_search_notes`?

If any answer is no, do not store it as prompt-time memory. It may still belong in a normal query or concept note if it is a substantial synthesis.

## Durability Thresholds

| Memory kind | Minimum threshold |
| --- | --- |
| `working_context` | Needed for the next turn or handoff; must expire or be reviewed soon. |
| `episodic_event` | Actor, time, artifact, and outcome are known. |
| `semantic_fact` | Supported by repository state, source material, or explicit user confirmation. |
| `procedural_pattern` | Repeated, documented, or proven during the task. |
| `preference_profile` | Explicit preference, explicit correction, or durable feedback pattern. |
| `project_convention` | Confirmed by repo docs/code/tests, repeated local practice, review feedback, or explicit user decision. |
| `constraint_policy` | Has clear authority, source, or explicit user/team requirement. |
| `failure_prevention` | Two observed occurrences, or one explicit correction with clear future prevention value. |
| `prospective_task` | Has owner plus due date, review date, expiry, or event trigger. |
| `evaluation_feedback` | Changes future behavior for a task type, code area, or quality gate. |
| `provenance_signal` | Clarifies source, confidence, conflict, validity window, or deletion/update requirement for another memory. |

## No-Store Rules

Do not store:

- private transcript text wholesale;
- secrets, credentials, tokens, private keys, unrevealed personal data, or sensitive legal/medical/financial data unless the user explicitly asks for a durable vault note and the vault policy allows it;
- inferred personality, mood, intent, competence, seniority, nationality, gender, health, or other sensitive traits;
- preferences inferred from a single ambiguous message;
- broad rules with no scope, such as "the user likes concise answers" unless explicitly stated and scoped;
- temporary repo state without expiry, such as an uncommitted branch detail that will go stale;
- negative labels about a person or team;
- raw blame; convert recurring mistakes into neutral prevention cues;
- facts that could change quickly unless the note includes date, source, confidence, and review horizon.

## Update and Merge Rules

Prefer updating an existing scoped note over creating a parallel memory page.

Use this order:

1. Run `kb_context(query=<anchor>, mode="prewrite")` for the named person/project/module/workflow/concept.
2. Run `kb_search_notes` for exact aliases when duplicate risk exists.
3. If an existing page owns the scope, read it with `kb_read_note`.
4. Merge the new cue into the existing `## Prompt hints` section.
5. Remove or revise stale conflicting cue text only when the new evidence clearly supersedes it.
6. Preserve old facts as dated history when they remain useful as `episodic_event` or provenance.
7. Write with `if_hash` from the full note read.

Create a new page only when no existing anchor owns the scope and the memory meets creation thresholds.

## Provenance and Review Horizons

Every durable cue should carry enough provenance for a future agent to decide whether to trust it:

- `evidence`: explicit user instruction, review feedback, repo docs, tests, command output, source note, issue, PR, or raw source path.
- `confidence`: high for explicit or verified sources, medium for repeated but indirect evidence, low for candidate cues.
- `review after`: date when a cue should be revalidated.
- `expires`: hard expiry for short-lived working context or prospective tasks.
- `conflicts`: note or cue with a competing claim.

Suggested review horizons:

- `working_context`: hours to days.
- `prospective_task`: due date or event trigger, plus expiry.
- `project_convention`: next major release, migration, or 30-90 days when the repo is active.
- `preference_profile`: 60-180 days unless explicitly long-lived.
- `constraint_policy`: policy review date or source expiration.
- `semantic_fact`: when source volatility is medium or high.

## Stop-Hook Capture Rules

The stop hook may propose writes only for durable changes:

- Capture `episodic_event` for decisions, incidents, review outcomes, and explicit corrections with actor/time/source.
- Capture `semantic_fact` only after evidence exists; include dates for volatile facts.
- Capture `procedural_pattern` for workflows, command sequences, and tool recipes proven by the task.
- Capture `preference_profile` only from explicit preference, explicit correction, or durable feedback pattern.
- Capture `project_convention` from repo docs/code/tests, repeated local practice, review feedback, or explicit decision.
- Capture `constraint_policy` from explicit user/team/platform/safety/privacy/legal constraints.
- Capture `failure_prevention` as trigger -> check -> correction, never as blame.
- Capture `prospective_task` only with owner and trigger/due/review/expiry.
- Capture `evaluation_feedback` when it changes future behavior or quality gates.
- Capture `provenance_signal` when trust, conflict, expiry, or deletion/update requirements matter.

If no durable memory exists, the stop hook should write nothing.

## Prompt Cue Quality Bar

A prompt cue is ready only when it is:

- scoped to a smallest stable anchor;
- actionable;
- evidence-backed;
- confidence-labeled;
- reviewable or expiring;
- short enough to inject without summarization;
- neutral in tone;
- linked to existing wiki pages when possible.

Weak cue:

```markdown
- kind: preference_profile; scope: user; do: be direct.
```

Better cue:

```markdown
- kind: preference_profile; scope: person:workspace-owner channel:code-review; applies when: summarizing review findings; do: lead with concrete file/line risks before summaries; evidence: explicit instruction in code review workflow; confidence: high; review after: 2026-09-30.
```
