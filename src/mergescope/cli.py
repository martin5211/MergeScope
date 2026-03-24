from __future__ import annotations

import argparse
import asyncio
import logging
import sys

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


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mergescope",
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


def _apply_cli_overrides(cfg: MergeScopeConfig, args: argparse.Namespace) -> MergeScopeConfig:
    if args.repo:
        cfg.repo = args.repo
    if args.mcp_config:
        cfg.mcp.config_path = args.mcp_config
    if args.llm_provider:
        cfg.llm.provider = args.llm_provider
    if args.llm_model:
        cfg.llm.model = args.llm_model
    if args.language:
        cfg.response_language = args.language
    if args.llm_base_url:
        cfg.llm.base_url = args.llm_base_url
    return cfg


async def run_audit(
    cfg: MergeScopeConfig,
    from_date: str,
    to_date: str,
    fix_version: str,
) -> None:
    if not cfg.repo:
        console.print("[red]Error:[/red] No repository specified. Use --repo or set repo in config.")
        sys.exit(1)

    out = Console()

    try:
        client = create_mcp_client(cfg)
    except (McpConfigNotFoundError, McpServerNotFoundError) as exc:
        console.print(f"[red]MCP Error:[/red] {exc}")
        sys.exit(1)

    async with client:
        tools = client.get_tools()
        if not tools:
            console.print("[red]Error:[/red] No MCP tools available. Check your Amazon Q MCP configuration.")
            sys.exit(1)

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
            console.print(f"[red]Error:[/red] Audit failed after {MAX_RETRIES + 1} attempts. Last error: {last_error}")
            sys.exit(1)

        render_report(data, jira_base_url=cfg.jira_base_url, repo=cfg.repo, console=out)


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

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
