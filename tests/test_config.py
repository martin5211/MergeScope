"""Tests for configuration loading."""

import textwrap
from pathlib import Path

from mergescope.config import MergeScopeConfig, load_config


def test_load_defaults_no_file() -> None:
    cfg = load_config(None)
    assert cfg.repo == ""
    assert cfg.llm.provider == "anthropic"
    assert cfg.mcp.servers["github"].name == "github-mcp-server"
    assert cfg.mcp.servers["jira"].name == "atlassian-mcp-server"


def test_load_from_yaml(tmp_path: Path) -> None:
    yaml_content = textwrap.dedent("""\
        repo: "acme/backend"
        jira_base_url: "https://acme.atlassian.net"
        language: "es"
        response_language: "Spanish"
        llm:
          provider: "bedrock"
          model: "us.anthropic.claude-sonnet-4-20250514-v1:0"
        mcp:
          servers:
            github:
              name: "my-gh-server"
            jira:
              name: "my-jira-server"
    """)
    cfg_file = tmp_path / "test.yaml"
    cfg_file.write_text(yaml_content, encoding="utf-8")

    cfg = load_config(cfg_file)
    assert cfg.repo == "acme/backend"
    assert cfg.jira_base_url == "https://acme.atlassian.net"
    assert cfg.language == "es"
    assert cfg.llm.provider == "bedrock"
    assert cfg.mcp.servers["github"].name == "my-gh-server"
    assert cfg.mcp.servers["jira"].name == "my-jira-server"


def test_env_override(tmp_path: Path, monkeypatch) -> None:
    cfg_file = tmp_path / "test.yaml"
    cfg_file.write_text("repo: original\n", encoding="utf-8")

    monkeypatch.setenv("MERGESCOPE_REPO", "env/repo")
    monkeypatch.setenv("MERGESCOPE_LLM_PROVIDER", "bedrock")

    cfg = load_config(cfg_file)
    assert cfg.repo == "env/repo"
    assert cfg.llm.provider == "bedrock"
