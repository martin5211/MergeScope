import asyncio
import json
from unittest.mock import AsyncMock, patch

from mergescope.mcp_server import server, audit_merges


def test_audit_merges_tool_registered():
    tools = server._tool_manager._tools
    assert "audit_merges" in tools


def test_audit_merges_calls_execute_audit():
    mock_result = {"tickets": [{"jira_id": "PROJ-1"}], "unlinked_commits": []}

    with patch("mergescope.mcp_server.load_config") as mock_cfg, \
         patch("mergescope.cli.execute_audit", new_callable=AsyncMock, return_value=mock_result):
        mock_cfg.return_value.repo = ""
        result = asyncio.run(audit_merges(
            repo="org/repo",
            from_date="2026-01-01",
            to_date="2026-03-25",
            fix_version="1.0",
        ))

    data = json.loads(result)
    assert data["tickets"][0]["jira_id"] == "PROJ-1"


def test_audit_merges_returns_error_on_failure():
    with patch("mergescope.mcp_server.load_config") as mock_cfg, \
         patch("mergescope.cli.execute_audit", new_callable=AsyncMock, side_effect=RuntimeError("boom")):
        mock_cfg.return_value.repo = ""
        result = asyncio.run(audit_merges(
            repo="org/repo",
            from_date="2026-01-01",
            to_date="2026-03-25",
            fix_version="1.0",
        ))

    data = json.loads(result)
    assert "boom" in data["error"]
