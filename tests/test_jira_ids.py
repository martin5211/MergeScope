"""Tests for Jira ID extraction."""

import pytest

from mergescope.jira_ids import extract_jira_ids


@pytest.mark.parametrize(
    "text, expected",
    [
        ("[PROJ-123] fix login", ["PROJ-123"]),
        ("PROJ-123 fix login", ["PROJ-123"]),
        ("proj-123 fix login", ["PROJ-123"]),
        ("Proj-123 and PROJ-456", ["PROJ-123", "PROJ-456"]),
        ("[PROJ-123][PROJ-456] both", ["PROJ-123", "PROJ-456"]),
        ("Merge PR: PROJ-123, AB-1", ["PROJ-123", "AB-1"]),
        ("no ticket here", []),
        ("PROJ-123 PROJ-123 dup", ["PROJ-123"]),
        ("feat/PROJ-123-branch-name", ["PROJ-123"]),
        ("bugfix/proj-456-fix-thing", ["PROJ-456"]),
        ("PROJ-789-some-description", ["PROJ-789"]),
        ("release/1.0.0", []),
        ("AB2-99 not valid A-1", ["AB2-99"]),  # A-1 is too short for a Jira project key
        ("", []),
        ("[ABC-1] and [DEF-22] and ghi-333", ["ABC-1", "DEF-22", "GHI-333"]),
        ("Merge pull request #42 from user/TEAM-100-add-feature", ["TEAM-100"]),
    ],
)
def test_extract_jira_ids(text: str, expected: list[str]) -> None:
    assert extract_jira_ids(text) == expected


def test_extract_with_project_prefix() -> None:
    text = "PROJ-1 OTHER-2 proj-3"
    assert extract_jira_ids(text, project_prefix="PROJ") == ["PROJ-1", "PROJ-3"]


def test_extract_with_prefix_no_match() -> None:
    assert extract_jira_ids("OTHER-5", project_prefix="PROJ") == []
