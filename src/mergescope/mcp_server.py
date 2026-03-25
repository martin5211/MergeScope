from __future__ import annotations

import json
import logging

from mcp.server.fastmcp import FastMCP

from mergescope.config import load_config

logger = logging.getLogger(__name__)

server = FastMCP("mergescope")

_config_path: str = "mergescope.yaml"


@server.tool()
async def audit_merges(
    repo: str,
    from_date: str,
    to_date: str,
    fix_version: str,
) -> str:
    from mergescope.cli import execute_audit

    cfg = load_config(_config_path)
    cfg.repo = repo

    try:
        data = await execute_audit(cfg, from_date, to_date, fix_version)
        return json.dumps(data, indent=2)
    except Exception as exc:
        logger.error("audit_merges failed: %s", exc)
        return json.dumps({"error": str(exc)})


def run_serve(config_path: str = "mergescope.yaml", verbose: bool = False) -> None:
    global _config_path
    _config_path = config_path

    if verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(name)s %(levelname)s: %(message)s",
        )

    server.run(transport="stdio")
