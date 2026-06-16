from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CodexConfigResult:
    changed: bool
    reason: str


def add_codex_mcp_server(
    config_path: Path, server_name: str, server_url: str, *, dry_run: bool
) -> CodexConfigResult:
    existing = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    parsed = _parse_toml(existing, config_path)
    servers = _mcp_servers(parsed)

    if server_name in servers:
        existing_url = str(servers[server_name].get("url", ""))
        updated = _replace_codex_server_url(existing, server_name, server_url)
        if dry_run:
            return CodexConfigResult(
                changed=existing_url != server_url,
                reason=(
                    f"[dry-run] would update Codex MCP server '{server_name}' "
                    f"from {existing_url or '<unknown url>'} to {server_url} in {config_path}."
                ),
            )

        config_path.write_text(updated, encoding="utf-8")
        return CodexConfigResult(
            changed=existing_url != server_url,
            reason=(
                f"Updated Codex MCP server '{server_name}' in {config_path} "
                f"from {existing_url or '<unknown url>'} to {server_url}."
            ),
        )

    block = _codex_server_block(server_name, server_url)
    if dry_run:
        return CodexConfigResult(
            changed=True,
            reason=(
                f"[dry-run] would append Codex MCP server '{server_name}' "
                f"to {config_path}:\n{block.rstrip()}"
            ),
        )

    config_path.parent.mkdir(parents=True, exist_ok=True)
    updated = f"{existing.rstrip()}\n\n{block}" if existing.strip() else block
    config_path.write_text(updated, encoding="utf-8")
    return CodexConfigResult(
        changed=True, reason=f"Added Codex MCP server '{server_name}' to {config_path}."
    )


def _parse_toml(content: str, config_path: Path) -> dict[str, Any]:
    if not content.strip():
        return {}
    try:
        parsed = tomllib.loads(content)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Cannot parse existing Codex config {config_path}: {exc}") from exc
    return parsed


def _mcp_servers(parsed: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_servers = parsed.get("mcp_servers", {})
    if not isinstance(raw_servers, dict):
        return {}
    return {name: value for name, value in raw_servers.items() if isinstance(value, dict)}


def _replace_codex_server_url(content: str, server_name: str, server_url: str) -> str:
    table_key = _toml_table_key(server_name)
    table_pattern = re.compile(
        rf"(?ms)^(\[mcp_servers\.{re.escape(table_key)}\]\n)(.*?)(?=^\[|\Z)"
    )
    match = table_pattern.search(content)
    if match is None:
        return f"{content.rstrip()}\n\n{_codex_server_block(server_name, server_url)}"

    header, body = match.group(1), match.group(2)
    url_line = f"url = {json.dumps(server_url)}"
    if re.search(r"(?m)^url\s*=", body):
        updated_body = re.sub(r"(?m)^url\s*=.*$", url_line, body, count=1)
    else:
        updated_body = f"{url_line}\n{body}"
    return f"{content[:match.start()]}{header}{updated_body}{content[match.end():]}"


def _codex_server_block(server_name: str, server_url: str) -> str:
    table_key = _toml_table_key(server_name)
    return f"""[mcp_servers.{table_key}]
url = {json.dumps(server_url)}
startup_timeout_sec = 30
tool_timeout_sec = 120
default_tools_approval_mode = "prompt"
"""


def _toml_table_key(server_name: str) -> str:
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", server_name):
        return server_name
    return json.dumps(server_name)
