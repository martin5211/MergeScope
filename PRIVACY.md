# Privacy

MergeScope runs entirely on your machine. It does not collect, store, or transmit any telemetry, analytics, or usage data.

## What MergeScope accesses

- **GitHub API** — via MCP server to read merge commits and pull requests from repositories you specify
- **Jira API** — via MCP server to read ticket summaries and fixVersion fields
- **LLM provider** — sends audit prompts and tool results to the configured LLM (Anthropic, AWS Bedrock, GitHub Copilot, or a local server)

All API calls are made directly from your machine using your own credentials. MergeScope never proxies, logs, or stores API responses beyond the current session.

## Credentials

MergeScope reads credentials from environment variables or your Amazon Q / MCP server configuration. It never writes, copies, or transmits credentials anywhere.

## Third-party services

MergeScope has no servers, no accounts, and no backend. The only external calls are the ones you configure (GitHub, Jira, LLM provider).
