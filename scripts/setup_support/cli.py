from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import TextIO

from setup_support.config import (
    DEFAULT_SERVER_NAMES,
    ResolvedConfig,
    repo_root_from_script,
    resolve_config,
)
from setup_support.installers import install_agent

AGENTS = tuple(DEFAULT_SERVER_NAMES)
STOP_HOOK_WARNING = (
    "Warning: installing the LLM Wiki Stop hook may prevent you from receiving "
    "the LLM response correctly."
)
STOP_HOOK_PROMPT = "Install LLM Wiki Stop hook? Type Y or N only: "
STOP_HOOK_RETRY = "Please type exactly Y or N."
STOP_HOOK_DRY_RUN_SKIP = (
    "[dry-run] skip interactive Stop hook prompt; Stop hook is not included in dry-run plan."
)


class StopHookPromptError(RuntimeError):
    """Raised when setup cannot collect the required Stop-hook Y/N choice."""


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = repo_root_from_script(__file__)
    status = 0
    stop_hook_choice: bool | None = None
    for agent in selected_agents(args.agent):
        config = resolve_config(
            agent=agent,
            repo_root=repo_root,
            env_file=Path(args.env_file) if args.env_file else None,
            server_name=args.server_name,
            server_url=args.server_url,
            dry_run=args.dry_run,
            claude_scope=args.scope,
            codex_config_path=args.config,
            install_hooks=args.install_hooks,
            claude_settings_path=args.claude_settings,
        )
        if config.install_hooks:
            if stop_hook_choice is None:
                if config.dry_run:
                    print(STOP_HOOK_DRY_RUN_SKIP)
                    stop_hook_choice = False
                else:
                    try:
                        stop_hook_choice = prompt_stop_hook_install()
                    except StopHookPromptError as exc:
                        print(str(exc), file=sys.stderr)
                        return 2
            config = replace(config, install_stop_hook=stop_hook_choice)
        print(f"== {agent} ==")
        print(f"Using env file: {config.env_file}")
        print(f"Resolved MCP server: {config.server_name} -> {config.server_url}")
        result = _install_agent_fail_open(agent, config)
        if result != 0:
            status = result
    return status


def _install_agent_fail_open(agent: str, config: ResolvedConfig) -> int:
    try:
        return install_agent(config)
    except subprocess.CalledProcessError as exc:
        _print_install_error(
            agent,
            f"command {exc.cmd!r} exited with status {exc.returncode}",
            exc.stderr,
        )
        return exc.returncode or 1
    except OSError as exc:
        _print_install_error(agent, str(exc))
        return 1


def _print_install_error(agent: str, message: str, detail: str | None = None) -> None:
    print(f"{agent} install failed: {message}", file=sys.stderr)
    if detail and detail.strip():
        print(detail.strip(), file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Install LLM Wiki MCP and skill configuration for Hermes/Hermess, "
            "Claude Code, and Codex."
        ),
    )
    parser.add_argument(
        "--agent",
        choices=AGENTS,
        action="append",
        help="agent integration to configure; repeatable, defaults to all agents",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print actions without writing files or changing configs",
    )
    parser.add_argument("--env-file", help="dotenv file to read; defaults to the repository .env")
    parser.add_argument(
        "--server-url", help="override LLM_WIKI_MCP_URL / KB_HOST+KB_PORT+KB_MCP_PATH"
    )
    parser.add_argument("--server-name", help="override LLM_WIKI_MCP_SERVER_NAME")
    parser.add_argument("--scope", help="Claude MCP scope; defaults to CLAUDE_MCP_SCOPE or user")
    parser.add_argument(
        "--config", help="Codex config path; defaults to CODEX_CONFIG_PATH or ~/.codex/config.toml"
    )
    parser.add_argument(
        "--no-hooks",
        dest="install_hooks",
        action="store_false",
        default=None,
        help="skip installing all LLM Wiki hook scaffolds",
    )
    parser.add_argument(
        "--claude-settings",
        help=(
            "Claude settings JSON path for hook merge; defaults to "
            "CLAUDE_SETTINGS_PATH or ~/.claude/settings.json"
        ),
    )
    return parser


def prompt_stop_hook_install(
    *,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> bool:
    input_stream = sys.stdin if input_stream is None else input_stream
    output_stream = sys.stdout if output_stream is None else output_stream
    if not input_stream.isatty():
        raise StopHookPromptError(
            "Stop hook install requires interactive Y/N input; installation did not run."
        )

    print(STOP_HOOK_WARNING, file=output_stream)
    while True:
        print(STOP_HOOK_PROMPT, end="", file=output_stream, flush=True)
        raw_choice = input_stream.readline()
        if raw_choice == "":
            raise StopHookPromptError(
                "Stop hook install prompt ended before Y/N input; installation did not run."
            )
        choice = raw_choice.strip()
        if choice == "Y":
            return True
        if choice == "N":
            return False
        print(STOP_HOOK_RETRY, file=output_stream)


def selected_agents(requested_agents: list[str] | None) -> list[str]:
    if requested_agents is None:
        return list(AGENTS)
    return list(dict.fromkeys(requested_agents))


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
