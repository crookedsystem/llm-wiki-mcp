# Delete Note Maintenance

## Test Case Decision
- [x] Integration/contract: `kb_delete_note(dry_run=false, confirm=preview.confirmation_phrase)` for an indexed note -> target file removed, `log.md` records delete, and `index.md` no longer contains the deleted slug — Decision: Required
- [x] Regression: `kb_delete_note(dry_run=true)` -> target, `log.md`, and `index.md` remain unchanged — Decision: Required

### Open Test Questions
- [x] 불확실성 없음

## Business Goal
폐기한 wiki note를 안전하게 삭제할 때 삭제 사실이 audit log에 남고, navigation index에서 stale entry가 자동으로 제거되도록 한다.

## Scope
- **In Scope**: 실제 삭제 시 `log.md` delete entry 추가, `index.md` target entry 제거, 기존 dry-run/confirmation/backlink cleanup 계약 유지, MCP/문서 계약 갱신.
- **Out of Scope**: 휴지통/복구 기능, reference cleanup 자동 승인, Git push 자동화, 운영 파일(`SCHEMA.md`, `index.md`, `log.md`) 삭제 정책 확장.

## Codebase Analysis Summary
이미 `kb_delete_note` MCP tool, `VaultDeleteService`, 삭제 DTO/result가 존재한다. 현재 삭제는 target 및 명시된 backlink cleanup 파일만 쓰고, `log.md`/`index.md`를 유지보수하지 않는다. `VaultWriteService`는 write 경로에서 `VaultLogService.append_entry`와 `VaultIndexService.upsert_entry`를 사용해 operational note를 갱신한다.

### Relevant Files
| File | Role | Action |
|------|------|--------|
| `src/vault/service/vault_delete_service.py` | 삭제 transaction owner | Modify |
| `src/vault/service/vault_index_service.py` | `index.md` body editor | Modify |
| `src/vault/service/vault_log_service.py` | `log.md` entry renderer | Modify |
| `tests/vault/infrastructure/mcp_tool/test_mcp_server.py` | MCP behavior tests | Modify |
| `skills/llm-wiki/SKILL.md` | Agent delete policy docs | Modify |
| `README*.md` | User-facing docs | Modify if necessary |

### Conventions to Follow
| Convention | Source | Rule |
|-----------|--------|------|
| Pydantic frozen models | existing service/result files | small typed value objects, explicit fields |
| Operational note editing | `VaultWriteService` | parse existing note, edit body, write with provenance |
| Tests | existing pytest files | Korean test names and Given/When/Then comments |

## Architecture Decisions
| Decision | Choice | Rationale | Alternatives |
|----------|--------|-----------|--------------|
| Delete log action | Extend `WriteAction` to include `delete` | Reuses current log rendering and keeps audit format consistent | Separate delete log service |
| Index removal | Add `VaultIndexService.remove_entry` | Reuses existing slug parsing and operational note rendering | Regex replace in delete service |
| Timestamp source | Current UTC time at deletion | Delete command has no user-supplied updated time; audit needs execution time | Add request field, but this expands public API |

## API Contracts

### MCP `kb_delete_note`
- Request: existing `note_path`, `reference_cleanup_paths?`, `dry_run?`, `confirm?`
- Dry-run response: unchanged preview contract and no file writes.
- Delete response: target deleted; approved references updated; `log.md` and `index.md` maintained as side effects.

## Data Models

### `DeleteNoteResult`
No response shape change planned. `updated_paths` may include operational files after actual deletion.

## Implementation Todos

### Todo 1: Add RED tests for delete maintenance
- **Priority**: 1
- **Dependencies**: none
- **Goal**: Pin the new observable MCP behavior.
- **Work**:
  - Extend `tests/vault/infrastructure/mcp_tool/test_mcp_server.py` to assert actual delete writes `log.md` and removes the target from `index.md`.
  - Add/extend dry-run assertion that operational files are unchanged.
- **Convention Notes**: Assert on file-visible outcomes, not private methods.
- **Verification**: `uv run pytest tests/vault/infrastructure/mcp_tool/test_mcp_server.py -k delete`
- **Exit Criteria**: Tests fail before implementation for missing log/index maintenance.
- **Status**: completed

### Todo 2: Implement delete-side log/index maintenance
- **Priority**: 2
- **Dependencies**: Todo 1
- **Goal**: Actual delete keeps operational notes consistent.
- **Work**:
  - Extend `VaultLogService` action labels to render delete entries.
  - Add `VaultIndexService.remove_entry(existing, slug, updated)` that removes only the entry whose first wikilink target matches the slug.
  - Update `VaultDeleteService` to snapshot/update operational files only for non-dry-run non-operational deleted notes, using current UTC timestamp and provenance operation `delete_note`.
- **Convention Notes**: Reuse existing `OperationalNote`, `LogEntry`, and index slug matching behavior.
- **Verification**: `uv run pytest tests/vault/infrastructure/mcp_tool/test_mcp_server.py -k delete`
- **Exit Criteria**: Delete tests pass and dry-run remains side-effect free.
- **Status**: completed

### Todo 3: Update documentation and run QA
- **Priority**: 3
- **Dependencies**: Todo 2
- **Goal**: Public instructions match the new delete tool behavior.
- **Work**:
  - Update `skills/llm-wiki/SKILL.md` delete policy.
  - Update README language where it describes delete tool side effects.
  - Run targeted and broad checks.
- **Convention Notes**: Keep docs concise and avoid changing unrelated sections.
- **Verification**: `uv run pytest tests/vault/infrastructure/mcp_tool/test_mcp_server.py -k delete`; `uv run pytest`; `uv run ruff check .`; `uv run ruff format --check .`; `uv run mypy src tests`
- **Exit Criteria**: Required checks pass or environment blocker is recorded.
- **Status**: completed

## Verification Strategy
- Narrow: `uv run pytest tests/vault/infrastructure/mcp_tool/test_mcp_server.py -k delete`
- Feature/broad: `uv run pytest`
- Quality: `uv run ruff check .`
- Format: `uv run ruff format --check .`
- Types: `uv run mypy src tests`

## Approval Record
- User approval source: "폐기한 note를 삭제하기 위한 도구를 추가해줘..."
- Approved scope: delete tool behavior plus log/index auto-maintenance.
- Out-of-scope items: commit, push, PR, deploy, destructive vault data action outside tests.

## Role Routing
| Todo | Owner | Dependencies | Parallelizable | Context allowed | Context forbidden |
|------|-------|--------------|----------------|-----------------|-------------------|
| Todo 1 | backend | none | no | MCP tests and delete contract | frontend/UI |
| Todo 2 | backend | Todo 1 | no | delete/write/index/log services | unrelated services |
| Todo 3 | qa | Todo 2 | no | docs and command output | implementation changes beyond failing evidence |

## QA Matrix
| Gate | Command/artifact | Required | Expected evidence | Owner |
|------|------------------|----------|-------------------|-------|
| Narrow | `uv run pytest tests/vault/infrastructure/mcp_tool/test_mcp_server.py -k delete` | yes | exit 0 | backend |
| Full tests | `uv run pytest` | yes | exit 0 | qa |
| Lint | `uv run ruff check .` | yes | exit 0 | qa |
| Typecheck | `uv run mypy src tests` | yes | exit 0 | qa |

## Test Case Plan
| # | Task/Todo | Target behavior | Scenario | Design method | Input | Expected | Priority |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Delete maintenance | Actual delete updates operational notes | Indexed concept delete | State transition | confirmed `dry_run=false` | target gone, log has delete, index lacks slug | 필수 |
| 2 | Delete safety | Dry-run is read-only | Preview delete | Regression/error guessing | default `dry_run=true` | target/log/index unchanged | 필수 |

## External Research Log
| Question | Skill used | Source-backed conclusion | Plan impact |
|----------|------------|--------------------------|-------------|
| none | not used | local code defines behavior | no external dependency |

## Cross-boundary Contracts
| Contract | Producer | Consumer | Success path | Guard/error path |
|----------|----------|----------|--------------|------------------|
| `kb_delete_note` side effects | MCP tool/delete service | Agent clients/vault users | delete maintains log/index automatically | dry-run and bad confirm perform no writes |

## Halt Conditions
- Scope drift: automatic reference cleanup without explicit paths, trash/archive feature request, API shape expansion.
- Product decision: deletion of root operational files.
- Security/data decision: destructive operation outside tmp test vault.
- Missing command/env: `uv` or test dependencies unavailable.

## Progress Tracking
- Total Todos: 3
- Completed: 3
- Status: Execution complete

## Change Log
- 2026-06-30: Plan created
- 2026-06-30: Todo 1 completed; RED tests fail on missing delete action and log/index maintenance.
- 2026-06-30: Todo 2 completed; narrow delete/log/index tests pass.
- 2026-06-30: Todo 3 completed; docs updated and QA gates passed.
