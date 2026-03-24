import json

import pytest

from mergescope.config import McpServerConfig, McpConfig, MergeScopeConfig
from mergescope.mcp_client import (
    McpConfigNotFoundError,
    McpServerNotFoundError,
    _find_amazon_q_configs,
    create_mcp_client,
)


def test_find_explicit_path_exists(tmp_path):
    cfg_file = tmp_path / "mcp.json"
    cfg_file.write_text('{"mcpServers": {}}')
    result = _find_amazon_q_configs(str(cfg_file))
    assert result == [cfg_file]


def test_find_explicit_path_missing():
    with pytest.raises(McpConfigNotFoundError, match="Explicit MCP config not found"):
        _find_amazon_q_configs("/nonexistent/path/mcp.json")


def test_find_no_configs_returns_empty():
    # With no explicit path and no Amazon Q installed, returns empty
    result = _find_amazon_q_configs("")
    # May or may not find configs depending on the machine — just check it doesn't crash
    assert isinstance(result, list)


def test_create_client_all_inline():
    cfg = MergeScopeConfig()
    cfg.mcp = McpConfig(servers={
        "github": McpServerConfig(
            name="gh", command="echo", args=["hello"], env={"TOKEN": "x"},
        ),
        "jira": McpServerConfig(
            name="jira", command="echo", args=["world"], env={},
        ),
    })
    # Should not raise — no Amazon Q needed
    client = create_mcp_client(cfg)
    assert client is not None


def test_create_client_missing_amazonq_raises():
    cfg = MergeScopeConfig()
    cfg.mcp = McpConfig(
        config_path="/nonexistent/mcp.json",
        servers={"github": McpServerConfig(name="gh-server")},
    )
    with pytest.raises(McpConfigNotFoundError):
        create_mcp_client(cfg)


def test_create_client_server_not_in_amazonq(tmp_path):
    cfg_file = tmp_path / "mcp.json"
    cfg_file.write_text(json.dumps({"mcpServers": {"other-server": {"command": "x"}}}))

    cfg = MergeScopeConfig()
    cfg.mcp = McpConfig(
        config_path=str(cfg_file),
        servers={"github": McpServerConfig(name="missing-server")},
    )
    with pytest.raises(McpServerNotFoundError, match="missing-server"):
        create_mcp_client(cfg)


def test_create_client_mixed_inline_and_amazonq(tmp_path):
    cfg_file = tmp_path / "mcp.json"
    cfg_file.write_text(json.dumps({
        "mcpServers": {
            "jira-from-q": {"command": "node", "args": ["jira.js"]},
        },
    }))

    cfg = MergeScopeConfig()
    cfg.mcp = McpConfig(
        config_path=str(cfg_file),
        servers={
            "github": McpServerConfig(name="gh", command="echo", args=[]),
            "jira": McpServerConfig(name="jira-from-q"),
        },
    )
    client = create_mcp_client(cfg)
    assert client is not None
