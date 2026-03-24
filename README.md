# MergeScope

[![PyPI](https://img.shields.io/pypi/v/mergescope)](https://pypi.org/project/mergescope/)
[![Build](https://github.com/martin5211/MergeScope/actions/workflows/publish.yml/badge.svg)](https://github.com/martin5211/MergeScope/actions/workflows/publish.yml)
[![Python](https://img.shields.io/pypi/pyversions/mergescope)](https://pypi.org/project/mergescope/)

Audits merged PRs against Jira tickets. Extracts Jira IDs from PR titles, descriptions, branch names, and commit messages, then validates each ticket's fixVersion against your expected release.

Powered by a LangGraph agent that talks to GitHub and Jira through MCP servers. Works standalone or with Amazon Q.

## Install

```bash
uvx mergescope --help
```

Or permanently:

```bash
uv tool install mergescope
```

## Usage

```bash
mergescope \
  -f 2026-03-01 \
  -t 2026-03-31 \
  -v "1.2.0" \
  -r company/backend
```

| Flag | Description |
|---|---|
| `-f`, `--from-date` | Start date (YYYY-MM-DD) |
| `-t`, `--to-date` | End date (YYYY-MM-DD) |
| `-v`, `--fix-version` | Expected Jira fixVersion |
| `-r`, `--repo` | GitHub repo (owner/repo) |
| `-c`, `--config` | Config file (default: `mergescope.yaml`) |
| `--mcp-config` | Amazon Q MCP config path |
| `--llm-provider` | `anthropic`, `bedrock`, `copilot`, or `local` |
| `--llm-model` | Model ID |
| `--llm-base-url` | API base URL (copilot/local) |
| `--language` | Response language (e.g. Spanish) |
| `--verbose` | Debug logging |

### Custom prompts

Override the default prompt in `mergescope.yaml`. Supports `{repo}`, `{from_date}`, `{to_date}`, `{fix_version}`:

```yaml
prompt_template: |
  I need to audit tickets merged between {from_date} and {to_date}.
  The expected fixVersion is {fix_version}.
  Extract Jira IDs from merge commits in {repo} and validate their fixVersion.
```

Works in any language:

```yaml
language: "es"
response_language: "Spanish"
prompt_template: |
  Necesito auditar tickets mergeados entre {from_date} y {to_date}.
  La fixVersion esperada es {fix_version}.
  Extrae los IDs de JIRA desde los merge commits del repositorio {repo}
  y valida su fixVersion.
```

## Configuration

Add a `mergescope.yaml` in your project root:

```yaml
repo: "nice/java-project"
jira_project_prefix: "PROJ"
jira_base_url: "https://company.jira.com"

llm:
  provider: "anthropic"       # anthropic, bedrock, copilot, local
  model: "claude-sonnet-4-6-20250620"

mcp:
  servers:
    github:
      name: "github-mcp-server"
    jira:
      name: "atlassian-mcp-server"
```

### LLM providers

| Provider | Model example | Notes |
|---|---|---|
| `anthropic` | `claude-sonnet-4-6-20250620` | Uses `ANTHROPIC_API_KEY` |
| `bedrock` | `us.anthropic.claude-sonnet-4-20250514-v1:0` | Uses AWS credentials |
| `copilot` | `claude-sonnet-4` | Set `base_url` to Copilot endpoint |
| `local` | `qwen3-8b` | LM Studio, Ollama, or any OpenAI-compatible server |

### MCP servers

Two modes — pick what fits your setup:

**With Amazon Q** (default): just set server names. MergeScope finds them in `~/.aws/amazonq/mcp.json` or `.amazonq/mcp.json`.

**Standalone** (no Amazon Q): define `command`, `args`, and `env` directly:

```yaml
mcp:
  servers:
    github:
      name: "github-mcp-server"
      command: "npx"
      args: ["-y", "@anthropic/github-mcp-server"]
      env:
        GITHUB_TOKEN: "ghp_..."
    jira:
      name: "atlassian-mcp-server"
      command: "npx"
      args: ["-y", "@anthropic/atlassian-mcp-server"]
      env:
        JIRA_API_TOKEN: "..."
        JIRA_URL: "https://company.jira.com"
```

You can mix both — some servers inline, others from Amazon Q.

### Environment variables

`MERGESCOPE_REPO`, `MERGESCOPE_LLM_PROVIDER`, `MERGESCOPE_LLM_MODEL`, `MERGESCOPE_LLM_BASE_URL`, `MERGESCOPE_LLM_API_KEY`, `MERGESCOPE_JIRA_BASE_URL`, `MERGESCOPE_LANGUAGE`

## Requirements

- Python 3.11+
- GitHub and Jira MCP servers (standalone or via Amazon Q)
- An LLM: Anthropic API key, AWS credentials, GitHub Copilot, or a local server

## Development

```bash
git clone https://github.com/martin5211/MergeScope.git
cd MergeScope
uv venv && uv pip install -e .
pytest
```
