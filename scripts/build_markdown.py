#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


STUDENT_DIR = Path("data/students")
STUDENTS_OUTPUT = Path("students.md")
GITHUB_LINK_RE = re.compile(
    r"^https://github\.com/"
    r"(?P<owner>[A-Za-z0-9_.-]+)/"
    r"(?P<repo>[A-Za-z0-9_.-]+)/"
    r"(?P<kind>pull|issues)/"
    r"(?P<number>[1-9][0-9]*)"
    r"/?$"
)
GH_PREFIX_RE = re.compile(r"^gh-\d+:\s*", re.IGNORECASE)


@dataclass(frozen=True)
class ContributionMetadata:
    project_name: str
    project_url: str
    contribution_type: str
    status: str
    topic_title: str
    topic_url: str


@dataclass(frozen=True)
class ContributionRow:
    contributor: str
    contributor_url: str
    project_name: str
    project_url: str
    contribution_type: str
    status: str
    topic_title: str
    topic_url: str


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(1)


def api_url(path: str) -> str:
    base = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    return f"{base}{path}"


def gh_get(url: str) -> Any:
    token = os.environ.get("GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "opensource-log-builder",
    }

    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode("utf-8")
            return json.loads(body) if body else None

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        fail(f"GitHub API request failed: HTTP {e.code}: {url}\n{body}")

    except urllib.error.URLError as e:
        fail(f"GitHub API request failed: {url}\n{e}")


def collect_student_contributions(
    student_dir: Path = STUDENT_DIR,
) -> dict[str, list[str]]:
    contributions: dict[str, list[str]] = {}

    if not student_dir.exists():
        return contributions

    for path in sorted(student_dir.glob("*.txt"), key=lambda p: p.stem.casefold()):
        links = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
        links = [line for line in links if line]

        if links:
            contributions[path.stem] = links

    return contributions


def status_from_github_data(kind: str, data: dict[str, Any]) -> str:
    if kind == "pull" and data.get("merged") is True:
        return "Merged"

    state = data.get("state")

    if not isinstance(state, str) or not state:
        fail("GitHub API response is missing contribution state.")

    return state.capitalize()


def contribution_type_from_kind(kind: str) -> str:
    return "PR" if kind == "pull" else "Issue"


def clean_topic_title(title: str) -> str:
    return GH_PREFIX_RE.sub("", title).strip()


def get_contribution_metadata(link: str) -> ContributionMetadata:
    match = GITHUB_LINK_RE.fullmatch(link)

    if match is None:
        fail(
            "Invalid GitHub contribution link:\n"
            f"{link}\n\n"
            "Allowed formats:\n"
            "https://github.com/OWNER/REPO/pull/123\n"
            "https://github.com/OWNER/REPO/issues/123"
        )

    owner = match.group("owner")
    repo = match.group("repo")
    kind = match.group("kind")
    number = match.group("number")
    endpoint = "pulls" if kind == "pull" else "issues"
    data = gh_get(api_url(f"/repos/{owner}/{repo}/{endpoint}/{number}"))

    if not isinstance(data, dict):
        fail(f"Unexpected GitHub API response for {link}")

    title = data.get("title")

    if not isinstance(title, str) or not title:
        fail(f"GitHub API response is missing title for {link}")

    topic_url = data.get("html_url")

    if not isinstance(topic_url, str) or not topic_url:
        topic_url = link

    return ContributionMetadata(
        project_name=f"{owner}/{repo}",
        project_url=f"https://github.com/{owner}/{repo}",
        contribution_type=contribution_type_from_kind(kind),
        status=status_from_github_data(kind, data),
        topic_title=clean_topic_title(title),
        topic_url=topic_url,
    )


def build_student_rows(
    contributions: dict[str, list[str]],
    metadata_loader: Callable[[str], ContributionMetadata] = get_contribution_metadata,
) -> list[ContributionRow]:
    rows: list[ContributionRow] = []

    for contributor in sorted(contributions, key=str.casefold):
        for link in contributions[contributor]:
            metadata = metadata_loader(link)
            rows.append(
                ContributionRow(
                    contributor=contributor,
                    contributor_url=f"https://github.com/{contributor}",
                    project_name=metadata.project_name,
                    project_url=metadata.project_url,
                    contribution_type=metadata.contribution_type,
                    status=metadata.status,
                    topic_title=metadata.topic_title,
                    topic_url=metadata.topic_url,
                )
            )

    return rows


def escape_markdown_table_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("\n", " ")
    )


def markdown_link(text: str, url: str) -> str:
    return f"[{escape_markdown_table_text(text)}]({url})"


def render_students_md(rows: list[ContributionRow]) -> str:
    lines = [
        "# Student Contributions",
        "",
        "This file is generated from `data/students/*.txt`. Do not edit it manually.",
        "",
    ]

    if not rows:
        lines.append("_No contributions recorded yet._")
        lines.append("")
        return "\n".join(lines)

    lines.extend(
        [
            "| Contributor | Project | Type | Status | Topic |",
            "| --- | --- | --- | --- | --- |",
        ]
    )

    for row in rows:
        lines.append(
            " | ".join(
                [
                    f"| {markdown_link(row.contributor, row.contributor_url)}",
                    markdown_link(row.project_name, row.project_url),
                    escape_markdown_table_text(row.contribution_type),
                    escape_markdown_table_text(row.status),
                    f"{markdown_link(row.topic_title, row.topic_url)} |",
                ]
            )
        )

    lines.append("")
    return "\n".join(lines)


def build_students_md() -> None:
    rows = build_student_rows(collect_student_contributions())
    STUDENTS_OUTPUT.write_text(
        render_students_md(rows),
        encoding="utf-8",
    )


def main() -> None:
    build_students_md()


if __name__ == "__main__":
    main()
