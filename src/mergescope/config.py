from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class McpServerConfig:
    name: str
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)

    @property
    def is_inline(self) -> bool:
        return bool(self.command)


@dataclass
class McpConfig:
    config_path: str = ""
    servers: dict[str, McpServerConfig] = field(default_factory=lambda: {
        "github": McpServerConfig(name="github-mcp-server"),
        "jira": McpServerConfig(name="atlassian-mcp-server"),
    })


@dataclass
class LlmConfig:
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6-20250620"
    base_url: str = ""
    api_key: str = ""


@dataclass
class MergeScopeConfig:
    repo: str = ""
    jira_project_prefix: str = ""
    jira_base_url: str = ""
    date_format: str = "%Y-%m-%d"
    language: str = "en"
    response_language: str = "English"
    prompt_template: str = (
        "Audit repository {repo} for merge commits between {from_date} and {to_date}. "
        "The expected fix version is {fix_version}."
    )
    llm: LlmConfig = field(default_factory=LlmConfig)
    mcp: McpConfig = field(default_factory=McpConfig)


def load_config(path: str | Path | None = None) -> MergeScopeConfig:
    raw: dict = {}
    if path:
        p = Path(path).expanduser()
        if p.exists():
            try:
                raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as exc:
                raise ValueError(f"Invalid YAML in {p}: {exc}") from exc

    cfg = MergeScopeConfig(
        repo=raw.get("repo", ""),
        jira_project_prefix=raw.get("jira_project_prefix", ""),
        jira_base_url=raw.get("jira_base_url", ""),
        date_format=raw.get("date_format", "%Y-%m-%d"),
        language=raw.get("language", "en"),
        response_language=raw.get("response_language", "English"),
        prompt_template=raw.get("prompt_template", MergeScopeConfig.prompt_template),
    )

    llm_raw = raw.get("llm", {})
    cfg.llm = LlmConfig(
        provider=llm_raw.get("provider", "anthropic"),
        model=llm_raw.get("model", "claude-sonnet-4-6-20250620"),
        base_url=llm_raw.get("base_url", ""),
        api_key=llm_raw.get("api_key", ""),
    )

    mcp_raw = raw.get("mcp", {})
    cfg.mcp = McpConfig(config_path=mcp_raw.get("config_path", ""))
    servers_raw = mcp_raw.get("servers", {})
    if servers_raw:
        # Merge over defaults so undefined roles are kept
        for role, srv in servers_raw.items():
            cfg.mcp.servers[role] = McpServerConfig(
                name=srv.get("name", ""),
                command=srv.get("command", ""),
                args=srv.get("args", []),
                env=srv.get("env", {}),
            )

    if env_repo := os.environ.get("MERGESCOPE_REPO"):
        cfg.repo = env_repo
    if env_provider := os.environ.get("MERGESCOPE_LLM_PROVIDER"):
        cfg.llm.provider = env_provider
    if env_model := os.environ.get("MERGESCOPE_LLM_MODEL"):
        cfg.llm.model = env_model
    if env_jira_url := os.environ.get("MERGESCOPE_JIRA_BASE_URL"):
        cfg.jira_base_url = env_jira_url
    if env_lang := os.environ.get("MERGESCOPE_LANGUAGE"):
        cfg.language = env_lang
    if env_base_url := os.environ.get("MERGESCOPE_LLM_BASE_URL"):
        cfg.llm.base_url = env_base_url
    if env_api_key := os.environ.get("MERGESCOPE_LLM_API_KEY"):
        cfg.llm.api_key = env_api_key

    return cfg
