import re

_JIRA_ID_RE = re.compile(
    r"\[?"
    r"([A-Z][A-Z0-9]+-\d+)"
    r"\]?",
    re.IGNORECASE,
)


def extract_jira_ids(text: str, project_prefix: str | None = None) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for match in _JIRA_ID_RE.findall(text):
        normalized = match.upper()
        if project_prefix and not normalized.startswith(project_prefix.upper() + "-"):
            continue
        if normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result
