from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import Any

from rich.console import Console

from mergescope import __version__
from mergescope.agent import build_agent, build_prompt, parse_agent_output
from mergescope.config import MergeScopeConfig, load_config
from mergescope.mcp_client import (
    McpConfigNotFoundError,
    McpServerNotFoundError,
    create_mcp_client,
)
from mergescope.report import render_report

logger = logging.getLogger("mergescope")
console = Console(stderr=True)

MAX_RETRIES = 2


async def execute_audit(
    cfg: MergeScopeConfig,
    from_date: str,
    to_date: str,
    fix_version: str,
) -> dict[str, Any]:
    client = create_mcp_client(cfg)
    tools = await client.get_tools()
    if not tools:
        raise RuntimeError("No MCP tools available. Check your MCP configuration.")

    logger.info("Loaded %d MCP tools", len(tools))
    agent = build_agent(tools, cfg)
    messages = build_prompt(cfg, cfg.repo, from_date, to_date, fix_version)

    data = None
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            console.print(f"[dim]Running audit (attempt {attempt + 1})...[/dim]")
            result = await agent.ainvoke(
                {"messages": messages},
                config={"recursion_limit": 50},
            )
            final_content = result["messages"][-1].content
            data = parse_agent_output(final_content)
            break
        except ValueError:
            last_error = "Agent returned invalid JSON"
            if attempt < MAX_RETRIES:
                from langchain_core.messages import HumanMessage
                messages = result["messages"] + [
                    HumanMessage(content="Your response was not valid JSON. Return ONLY the JSON object, no markdown fences or extra text.")
                ]
                logger.warning("Retrying: %s", last_error)
        except Exception as exc:
            last_error = str(exc)
            if attempt < MAX_RETRIES:
                logger.warning("Attempt %d failed: %s. Retrying...", attempt + 1, exc)
                await asyncio.sleep(2 ** attempt)

    if data is None:
        raise RuntimeError(
            f"Audit failed after {MAX_RETRIES + 1} attempts. Last error: {last_error}"
        )

    return data


async def run_audit(
    cfg: MergeScopeConfig,
    from_date: str,
    to_date: str,
    fix_version: str,
) -> None:
    if not cfg.repo:
        console.print("[red]Error:[/red] No repository specified. Use --repo or set repo in config.")
        sys.exit(1)

    try:
        data = await execute_audit(cfg, from_date, to_date, fix_version)
    except (McpConfigNotFoundError, McpServerNotFoundError) as exc:
        console.print(f"[red]MCP Error:[/red] {exc}")
        sys.exit(1)
    except RuntimeError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(1)

    out = Console()
    render_report(data, jira_base_url=cfg.jira_base_url, repo=cfg.repo, console=out)


_SUBCOMMANDS = {"audit", "serve"}


def _build_audit_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mergescope audit",
        description="Audit merged PRs against Jira tickets using LangGraph + MCP",
    )
    p.add_argument("-f", "--from-date", required=True, help="Start date (YYYY-MM-DD)")
    p.add_argument("-t", "--to-date", required=True, help="End date (YYYY-MM-DD)")
    p.add_argument("-v", "--fix-version", required=True, help="Expected Jira fixVersion")
    p.add_argument("-r", "--repo", help="GitHub repo (owner/repo)")
    p.add_argument("-c", "--config", default="mergescope.yaml", help="Config file path")
    p.add_argument("--mcp-config", help="Amazon Q MCP config path (overrides config file)")
    p.add_argument("--llm-provider", help="LLM provider: anthropic, bedrock, copilot, local")
    p.add_argument("--llm-model", help="LLM model ID")
    p.add_argument("--llm-base-url", help="LLM API base URL (for copilot/local providers)")
    p.add_argument("--language", help="Response language (e.g. English, Spanish)")
    p.add_argument("--verbose", action="store_true", help="Enable debug logging")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _build_serve_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mergescope serve",
        description="Start MergeScope MCP server (stdio transport)",
    )
    p.add_argument("-c", "--config", default="mergescope.yaml", help="Config file path")
    p.add_argument("--verbose", action="store_true", help="Enable debug logging")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _apply_cli_overrides(cfg: MergeScopeConfig, args: argparse.Namespace) -> MergeScopeConfig:
    if args.repo:
        cfg.repo = args.repo
    if getattr(args, "mcp_config", None):
        cfg.mcp.config_path = args.mcp_config
    if getattr(args, "llm_provider", None):
        cfg.llm.provider = args.llm_provider
    if getattr(args, "llm_model", None):
        cfg.llm.model = args.llm_model
    if getattr(args, "language", None):
        cfg.response_language = args.language
    if getattr(args, "llm_base_url", None):
        cfg.llm.base_url = args.llm_base_url
    return cfg


def main() -> None:
    # detect subcommand; default to audit for backwards compat
    argv = sys.argv[1:]
    command = argv[0] if argv and argv[0] in _SUBCOMMANDS else "audit"
    rest = argv[1:] if argv and argv[0] in _SUBCOMMANDS else argv

    if command == "serve":
        args = _build_serve_parser().parse_args(rest)
        logging.basicConfig(
            level=logging.DEBUG if args.verbose else logging.WARNING,
            format="%(name)s %(levelname)s: %(message)s",
        )
        from mergescope.mcp_server import run_serve
        run_serve(args.config, args.verbose)
        return

    args = _build_audit_parser().parse_args(rest)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(name)s %(levelname)s: %(message)s",
    )
    cfg = load_config(args.config)
    cfg = _apply_cli_overrides(cfg, args)
    try:
        asyncio.run(run_audit(cfg, args.from_date, args.to_date, args.fix_version))
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")
        sys.exit(130)
