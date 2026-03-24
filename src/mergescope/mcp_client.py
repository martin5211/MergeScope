from __future__ import annotations

import json
import logging
from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient

from mergescope.config import McpServerConfig, MergeScopeConfig

logger = logging.getLogger(__name__)

_AMAZONQ_SEARCH_PATHS = [
    ".amazonq/mcp.json",
    ".amazonq/default.json",
    "~/.aws/amazonq/mcp.json",
    "~/.aws/amazonq/default.json",
]


class McpConfigNotFoundError(Exception):
    pass


class McpServerNotFoundError(Exception):
    pass


def _find_amazon_q_configs(explicit_path: str = "") -> list[Path]:
    if explicit_path:
        p = Path(explicit_path).expanduser()
        if p.exists():
            return [p]
        raise McpConfigNotFoundError(
            f"Explicit MCP config not found: {p}\n"
            "Check the path in --mcp-config or mergescope.yaml mcp.config_path"
        )

    found: list[Path] = []
    for rel in _AMAZONQ_SEARCH_PATHS:
        p = Path(rel).expanduser()
        if p.exists():
            found.append(p)
    return found


def _load_merged_amazonq_config(paths: list[Path]) -> dict:
    merged: dict = {}
    for p in reversed(paths):
        raw = json.loads(p.read_text(encoding="utf-8"))
        servers = raw.get("mcpServers", {})
        merged.update(servers)
        logger.debug("Loaded %d servers from %s", len(servers), p)
    return merged


def _build_connection(srv_cfg: McpServerConfig, role: str, amazonq_servers: dict) -> dict:
    # Inline takes priority over Amazon Q
    if srv_cfg.is_inline:
        logger.info("Using inline MCP server: %s (%s)", srv_cfg.name or role, role)
        return {
            "transport": "stdio",
            "command": srv_cfg.command,
            "args": srv_cfg.args,
            "env": srv_cfg.env or None,
        }

    server_name = srv_cfg.name
    if server_name not in amazonq_servers:
        raise McpServerNotFoundError(
            f"MCP server '{server_name}' (role: {role}) not found.\n"
            "Either define it inline in mergescope.yaml with command/args/env,\n"
            "or ensure it exists in your Amazon Q MCP configuration.\n"
            + (f"Available Amazon Q servers: {', '.join(amazonq_servers.keys())}"
               if amazonq_servers else "No Amazon Q config found.")
        )
    server_def = amazonq_servers[server_name]
    logger.info("Using Amazon Q MCP server: %s (%s)", server_name, role)
    return {
        "transport": "stdio",
        "command": server_def["command"],
        "args": server_def.get("args", []),
        "env": server_def.get("env"),
    }


def create_mcp_client(config: MergeScopeConfig) -> MultiServerMCPClient:
    all_inline = all(srv.is_inline for srv in config.mcp.servers.values())

    amazonq_servers: dict = {}
    if not all_inline:
        paths = _find_amazon_q_configs(config.mcp.config_path)
        if paths:
            amazonq_servers = _load_merged_amazonq_config(paths)
        else:
            needs_amazonq = [
                role for role, srv in config.mcp.servers.items() if not srv.is_inline
            ]
            if needs_amazonq:
                raise McpConfigNotFoundError(
                    f"Servers {needs_amazonq} need Amazon Q config, but none was found.\n"
                    "Searched:\n"
                    + "\n".join(f"  - {p}" for p in _AMAZONQ_SEARCH_PATHS)
                    + "\nEither define servers inline in mergescope.yaml (with command/args/env)\n"
                    "or install and configure Amazon Q Developer CLI."
                )

    connections: dict = {}
    for role, srv_cfg in config.mcp.servers.items():
        conn = _build_connection(srv_cfg, role, amazonq_servers)
        connections[srv_cfg.name or role] = conn

    return MultiServerMCPClient(connections)
