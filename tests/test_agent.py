import pytest
from langchain_core.messages import SystemMessage, HumanMessage

from mergescope.agent import parse_agent_output, build_prompt
from mergescope.config import MergeScopeConfig


def test_parse_valid_json():
    raw = '{"tickets": [], "unlinked_commits": []}'
    assert parse_agent_output(raw) == {"tickets": [], "unlinked_commits": []}


def test_parse_json_with_markdown_fences():
    raw = '```json\n{"tickets": [{"jira_id": "X-1"}]}\n```'
    result = parse_agent_output(raw)
    assert result["tickets"][0]["jira_id"] == "X-1"


def test_parse_json_with_bare_fences():
    raw = '```\n{"tickets": []}\n```'
    assert parse_agent_output(raw) == {"tickets": []}


def test_parse_invalid_json_raises():
    with pytest.raises(ValueError, match="valid JSON"):
        parse_agent_output("not json at all")


def test_parse_json_with_surrounding_whitespace():
    raw = '  \n  {"tickets": []}  \n  '
    assert parse_agent_output(raw) == {"tickets": []}


def test_build_prompt_returns_system_and_human():
    cfg = MergeScopeConfig(repo="company/app")
    msgs = build_prompt(cfg, "company/app", "2025-01-01", "2025-01-31", "1.0")
    assert len(msgs) == 2
    assert isinstance(msgs[0], SystemMessage)
    assert isinstance(msgs[1], HumanMessage)
    assert "company/app" in msgs[1].content
    assert "2025-01-01" in msgs[1].content
    assert "1.0" in msgs[1].content


def test_build_prompt_custom_template():
    cfg = MergeScopeConfig(
        prompt_template="Audit {repo} from {from_date} to {to_date} for {fix_version}",
    )
    msgs = build_prompt(cfg, "org/repo", "2025-03-01", "2025-03-31", "2.0")
    assert msgs[1].content == "Audit org/repo from 2025-03-01 to 2025-03-31 for 2.0"


def test_build_prompt_language_instruction():
    cfg = MergeScopeConfig(response_language="Spanish")
    msgs = build_prompt(cfg, "r", "d1", "d2", "v")
    assert "Spanish" in msgs[0].content
