from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.table import Table

_STATUS_STYLES = {
    "MATCH": "[green]MATCH[/green]",
    "MISMATCH": "[red]MISMATCH[/red]",
    "NOT_FOUND": "[yellow]NOT FOUND[/yellow]",
    "NO_FIX_VERSION": "[yellow]NO FIX VERSION[/yellow]",
}


def render_report(
    data: dict[str, Any],
    jira_base_url: str = "",
    repo: str = "",
    console: Console | None = None,
) -> None:
    console = console or Console()
    tickets = data.get("tickets", [])
    unlinked = data.get("unlinked_commits", [])

    if not tickets and not unlinked:
        console.print("[yellow]No merge activity found in the specified date range.[/yellow]")
        return

    if tickets:
        table = Table(title="Jira Ticket Audit", show_lines=True)
        table.add_column("Jira ID", style="cyan", no_wrap=True)
        table.add_column("Title", max_width=60)
        table.add_column("Fix Version", no_wrap=True)
        table.add_column("Expected", no_wrap=True)
        table.add_column("Status", no_wrap=True)

        for t in tickets:
            jira_id = t.get("jira_id", "?")
            display_id = jira_id
            if jira_base_url:
                url = f"{jira_base_url.rstrip('/')}/browse/{jira_id}"
                display_id = f"[link={url}]{jira_id}[/link]"

            status = t.get("status", "UNKNOWN").upper()
            styled_status = _STATUS_STYLES.get(status, status)

            table.add_row(
                display_id,
                (t.get("title") or "—")[:60],
                t.get("fix_version") or "—",
                t.get("expected_version") or "—",
                styled_status,
            )

        console.print(table)

    if unlinked:
        console.print()
        ut = Table(title="Commits Without Jira ID", show_lines=True)
        ut.add_column("Commit", style="cyan", no_wrap=True)
        ut.add_column("Description", max_width=80)

        for c in unlinked:
            sha = c.get("sha", "?")
            sha_short = sha[:7]
            url = c.get("url", "")
            if not url and repo:
                url = f"https://github.com/{repo}/commit/{sha}"
            display_sha = f"[link={url}]{sha_short}[/link]" if url else sha_short

            ut.add_row(display_sha, (c.get("message") or "—")[:80])

        console.print(ut)

    total = len(tickets)
    matches = sum(1 for t in tickets if t.get("status", "").upper() == "MATCH")
    console.print(
        f"\n[bold]Summary:[/bold] {matches}/{total} tickets match expected fix version. "
        f"{len(unlinked)} commit(s) without Jira ID."
    )
