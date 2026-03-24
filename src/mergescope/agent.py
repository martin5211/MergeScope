from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import MessagesState, StateGraph, START
from langgraph.prebuilt import ToolNode, tools_condition

from mergescope.config import MergeScopeConfig

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are MergeScope, an audit agent that cross-references GitHub merge activity with Jira tickets.

You have access to GitHub and Jira tools via MCP servers. Use the available tools to complete the audit.

## Instructions

1. **Fetch merge activity**: Use the GitHub tools to list merged pull requests (or merge commits) in the given repository and date range. Get enough detail: PR title, body/description, branch name, commit messages, and commit SHAs.

2. **Extract Jira IDs**: From EACH pull request, look for Jira ticket IDs in ALL of these places:
   - PR title
   - PR body / description (both short and long)
   - Branch name (e.g. `feat/PROJ-123-something`, `PROJ-456`, `bugfix/proj-789`)
   - Individual commit messages
   Jira IDs follow the pattern: 2+ letters, a hyphen, then digits (e.g. PROJ-123, AB-1). They may appear in brackets [PROJ-123], lowercase, or mixed case. Normalize all to UPPERCASE and deduplicate.

3. **Validate in Jira**: For each unique Jira ID found, use the Jira/Atlassian tools to fetch:
   - The ticket summary (title)
   - The fixVersion field
   Compare fixVersion against the expected version provided.

4. **Return structured JSON** with this exact schema:
```json
{{
  "tickets": [
    {{
      "jira_id": "PROJ-123",
      "title": "Ticket summary from Jira",
      "fix_version": "actual fixVersion or null",
      "expected_version": "the expected version",
      "status": "MATCH | MISMATCH | NOT_FOUND | NO_FIX_VERSION"
    }}
  ],
  "unlinked_commits": [
    {{
      "sha": "full commit SHA",
      "message": "first line of commit message",
      "url": "https://github.com/owner/repo/commit/SHA"
    }}
  ]
}}
```

Status rules:
- `MATCH`: fixVersion equals expected version
- `MISMATCH`: fixVersion exists but differs from expected
- `NOT_FOUND`: Jira ticket does not exist or lookup failed
- `NO_FIX_VERSION`: ticket exists but has no fixVersion set

Include in `unlinked_commits` every merge commit or squash commit that has NO Jira ID anywhere (title, body, branch, message).

{language_instruction}

Respond ONLY with the JSON object. No markdown fences, no explanation.\
"""


def _build_system_prompt(config: MergeScopeConfig) -> str:
    lang = config.response_language
    if lang and lang.lower() != "english":
        instruction = f"Write all ticket titles and the JSON string values in {lang} if the source is in that language, otherwise keep the original language."
    else:
        instruction = ""
    return SYSTEM_PROMPT.format(language_instruction=instruction)


_PROVIDERS = ("anthropic", "bedrock", "copilot", "local")


def _create_llm(config: MergeScopeConfig):
    provider = config.llm.provider.lower()
    model_id = config.llm.model
    base_url = config.llm.base_url or None
    api_key = config.llm.api_key or None

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model_id)

    if provider == "bedrock":
        from langchain_aws import ChatBedrock
        return ChatBedrock(model_id=model_id)

    if provider == "copilot":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_id,
            base_url=base_url or "https://api.githubcopilot.com",
            api_key=api_key or None,
        )

    if provider == "local":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_id,
            base_url=base_url or "http://localhost:1234/v1",
            api_key=api_key or "lm-studio",
        )

    raise ValueError(
        f"Unsupported LLM provider: '{provider}'. "
        f"Choose from: {', '.join(_PROVIDERS)}"
    )


def build_agent(tools: list, config: MergeScopeConfig):
    model = _create_llm(config)
    model_with_tools = model.bind_tools(tools)

    async def call_model(state: MessagesState) -> dict:
        response = await model_with_tools.ainvoke(state["messages"])
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("call_model", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "call_model")
    graph.add_conditional_edges("call_model", tools_condition)
    graph.add_edge("tools", "call_model")

    return graph.compile()


def build_prompt(config: MergeScopeConfig, repo: str, from_date: str, to_date: str, fix_version: str) -> list:
    system = _build_system_prompt(config)
    human = config.prompt_template.format(
        repo=repo,
        from_date=from_date,
        to_date=to_date,
        fix_version=fix_version,
    )
    return [
        SystemMessage(content=system),
        HumanMessage(content=human),
    ]


def parse_agent_output(content: str) -> dict[str, Any]:
    text = content.strip()
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse agent output as JSON: %s", exc)
        logger.debug("Raw output:\n%s", content)
        raise ValueError(
            "Agent did not return valid JSON. Raw output logged at DEBUG level."
        ) from exc
