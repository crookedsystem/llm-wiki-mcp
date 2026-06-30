# Memory Taxonomy

Use this reference when choosing or changing LLM Wiki memory kinds, prompt cue fields, retrieval behavior, or hook output grouping. Do not load it for ordinary wiki reads unless the task is specifically about memory modeling.

## Table of Contents

- [Design Goal](#design-goal)
- [Memory Kinds](#memory-kinds)
- [Required Cue Fields](#required-cue-fields)
- [Scope Matching](#scope-matching)
- [Retrieval Precedence](#retrieval-precedence)
- [Examples](#examples)

## Design Goal

LLM Wiki memory should store reusable context as scoped, evidence-backed cues rather than broad persona summaries or raw transcripts. The taxonomy separates what kind of knowledge was learned, how durable it is, and when an agent may apply it.

The prompt hook should retrieve memory only when it has a concrete scope match such as a named person, team, repository, service, module, workflow, file path, channel, incident, PR, or explicit memory request.

## Memory Kinds

| Kind | Store | Retrieve when | Avoid |
| --- | --- | --- | --- |
| `working_context` | Active task state, temporary assumptions, current branch/repo state, short handoff notes. | The next turn or same project session needs continuity. | Long-term facts, preferences, or anything that should survive without review. |
| `episodic_event` | Dated events, incidents, decisions, reviews, meetings, user corrections, and outcomes with actor/time/source. | The prompt mentions the actor, artifact, incident, PR, date, or decision lineage. | Transcript dumps or undated anecdotes. |
| `semantic_fact` | Stable domain facts, terminology, architecture relationships, data model facts, and business rules. | The task asks about the same domain/entity or depends on a durable relationship. | Fast-moving state without an updated date or confidence level. |
| `procedural_pattern` | Reusable workflows, commands, tool sequences, test recipes, setup steps, and skill-like routines. | The task repeats the same workflow or toolchain. | One-off command logs that did not generalize. |
| `preference_profile` | Explicit preferences, explicit corrections, and durable feedback-derived interaction rules. | The prompt involves the same person/team/channel or asks for communication style. | Personality inference, mood, intent, demographic guesses, or style learned from a single ambiguous example. |
| `project_convention` | Repo/service/module commands, architecture boundaries, file placement, naming, tests, API contracts, and operational conventions. | Current repo/service/module/path matches the stored scope. | Applying a convention outside its scope because a keyword overlaps. |
| `constraint_policy` | Safety, privacy, legal, compliance, platform, team, or product constraints. | The requested action may violate a constraint or requires gated handling. | Vague caution with no source or decision authority. |
| `failure_prevention` | Neutral prevention cues shaped as trigger -> check -> correction. | The task matches the trigger and the cue can prevent a repeated failure mode. | Blame, raw criticism, or identity-based labels. |
| `prospective_task` | Future commitments, reminders, follow-ups, due dates, event triggers, owners, and expiry. | The prompt, date, repo, actor, or workflow matches the trigger and the item is not expired. | Timeless TODOs without owner, trigger, or review date. |
| `evaluation_feedback` | Review comments, test failures, benchmark results, ratings, and user feedback that should change future behavior. | The agent is doing the same task type, editing the same area, or evaluating quality. | Storing every failed attempt when it has no future prevention value. |
| `provenance_signal` | Source, extraction method, evidence status, confidence, conflict, review date, deletion/update requirements. | The agent must decide whether another memory is trustworthy or stale. | Treating provenance as a task instruction by itself. |

## Required Cue Fields

Each `## Prompt hints` bullet should be compact and parseable:

```markdown
- kind: project_convention; scope: repo:billing-api module:payments; applies when: editing payment retry code; check before acting: existing retry/backoff policy; evidence: repo tests and review feedback; confidence: high; review after: 2026-09-30.
```

Prefer these fields:

- `kind`: one of the memory kinds above.
- `scope`: smallest stable owner, such as `person:...`, `team:...`, `repo:...`, `service:...`, `module:...`, `path:...`, `workflow:...`, or `channel:...`.
- `applies when`: concrete trigger for retrieval.
- one action field: `do`, `avoid`, `check before acting`, or `prevention cue`.
- `evidence`: explicit source status or linked evidence.
- `confidence`: `high`, `medium`, or `low`.
- `review after`: date or horizon for stale memory.

Optional fields:

- `owner`: person or team responsible for a prospective task or policy.
- `expires`: hard expiry date for temporary context.
- `conflicts`: linked cue or source that disagrees.
- `source`: note, PR, issue, file path, meeting note, or raw source path.

## Scope Matching

Use the narrowest matching scope that can safely own the cue:

1. `path` or `module` beats `service`.
2. `service` beats `repo`.
3. `repo` beats `team`.
4. `person` beats generic communication style only when the prompt involves that person or channel.
5. `workflow` beats generic task verbs when the workflow is named or clearly repeated.

Do not retrieve memory from generic verbs alone. Words such as `fix`, `implement`, `update`, `write`, `review`, or `debug` are insufficient without a scoped anchor.

## Retrieval Precedence

When several cues match, prefer:

1. Current system/developer/user instructions over wiki memory.
2. Verified repository state and command output over saved memory.
3. Exact path/module/service/person scope over broad scope.
4. Full-note evidence over snippet-only search results.
5. Higher confidence over lower confidence.
6. Newer or unexpired cues over stale cues.
7. Prevention cues with concrete checks over vague warnings.

When conflict remains, surface the conflict instead of merging the cues into a false certainty.

## Examples

Preference profile:

```markdown
- kind: preference_profile; scope: person:cto-kim channel:PR; applies when: writing a PR reply to CTO Kim; do: lead with decision impact and risk; avoid: generic status narration; evidence: explicit review feedback; confidence: high; review after: 2026-09-30.
```

Project convention:

```markdown
- kind: project_convention; scope: repo:fanplus-api module:queue-workers; applies when: editing queue workers; check before acting: existing retry/backoff and idempotency convention; evidence: repository tests and queue worker docs; confidence: high.
```

Failure prevention:

```markdown
- kind: failure_prevention; scope: api-contracts workflow:response-change; applies when: changing API response shape; prevention cue: compare AS-IS/TO-BE JSON and prepare FE-facing announcement; evidence: repeated review feedback; confidence: high; review after: 2026-09-30.
```

Prospective task:

```markdown
- kind: prospective_task; scope: repo:llm-wiki workflow:release; applies when: preparing next release; do: verify hook docs against current Codex hook schema; owner: repo maintainer; evidence: release checklist; confidence: medium; expires: 2026-08-01.
```
