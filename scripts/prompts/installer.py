"""Content templates rendered by the hook installer.

`HOOK_SCRIPT_TEMPLATE` is the generated bash wrapper; `HOOKS_README_TEMPLATE` is
the operator-facing README. Both use `.format` placeholders for runtime values.
Literal shell braces are escaped as `{{` / `}}`.
"""

from __future__ import annotations

from typing import Final

SKILL_HINT_CAT_BLOCK: Final = """\
cat << 'SKILL_HINT'
Skill activation: if the wiki context above is relevant to the current task, call Skill("llm-wiki") BEFORE responding to load the full wiki management workflow (search, write, update notes). Relevant signals — 기술 결정, CTO 논의, API 설계, 아키텍처, 팀 논의, Slack 대화, 번역, 폴링, fanplus-api, 스크럼, PM, 기획, 결정사항, 회의록, 코드 컨벤션, 프로젝트 비즈니스 룰, wiki, KB, vault, Obsidian, 저장해줘, 기억해줘, 찾아줘, 검색해줘, 정리해줘.
SKILL_HINT
"""

HOOK_SCRIPT_TEMPLATE: Final = """#!/usr/bin/env bash
set -euo pipefail

if [ -z "${{LLM_WIKI_MCP_SERVER_NAME:-}}" ]; then
  LLM_WIKI_MCP_SERVER_NAME={server_name}
fi
if [ -z "${{LLM_WIKI_MCP_URL:-}}" ]; then
  LLM_WIKI_MCP_URL={server_url}
fi
export LLM_WIKI_MCP_SERVER_NAME LLM_WIKI_MCP_URL

LLM_WIKI_HOOK_HELPER={helper}

# Fail open: a hook must never break the agent loop. If the helper checkout was
# moved or removed (e.g. an ephemeral git worktree deleted after install) or `uv`
# is not on PATH, exit quietly instead of erroring on every prompt/stop.
if [ ! -f "$LLM_WIKI_HOOK_HELPER" ]; then
  exit 0
fi
if ! command -v uv >/dev/null 2>&1; then
  exit 0
fi

uv --project {repo_root} run python "$LLM_WIKI_HOOK_HELPER" {mode} \\
  --server-name "$LLM_WIKI_MCP_SERVER_NAME" \\
  --server-url "$LLM_WIKI_MCP_URL"{extra} "$@" || true
{skill_hint}"""

HOOKS_README_TEMPLATE: Final = """# LLM Wiki agent hooks

Installed by `uv run python scripts/main.py --agent {agent}` from:

`{repo_root}`

## Commands

- User input context loader: `{context_hook}`
{stop_hook_section}

The context hook queries `{server_name}` at `{server_url}` with `kb_search_notes`
and prints a compact orientation block.

{stop_hook_description}

Claude Code user-level setup is merged into `{claude_settings_path}` when `--agent claude`
is used. Codex shares Claude Code's hook JSON schema (UserPromptSubmit/Stop, decision=block),
so `--agent codex` merges equivalent entries into `~/.codex/hooks.json` automatically.

Hermes/Hermess exposes only finalize-style session hooks (no Claude-style Stop re-prompt), so
wire these scripts into a Hermes plugin/wrapper or finalize hook for an out-of-loop update pass.
"""
