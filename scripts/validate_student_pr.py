#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


STUDENT_FILE_RE = re.compile(
    r"^data/students/(?P<username>[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?)\.txt$"
)
CONFERENCE_TALKS_FILE = "students_conference_talks.md"
GENERATED_CONTRIBUTION_LOG_FILE = "students_contribute_log.md"
CONFERENCE_TALK_FORMATS = {"talk", "poster", "workshop", "keynote", "lighttalk"}
CONFERENCE_TABLE_HEADER = "| Date | Name | Conference | Location | Format | Topic |"
CONFERENCE_TABLE_SEPARATOR = "| --- | --- | --- | --- | --- | --- |"

DATE_RE = re.compile(r"^[0-9]{4}\.(0[1-9]|1[0-2])$")
GITHUB_PROFILE_RE = re.compile(
    r"^https://github\.com/[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?/?$"
)
LOCATION_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]*, [A-Za-z][A-Za-z .'-]*$")
MARKDOWN_LINK_RE = re.compile(r"^\[(?P<text>[^\]\n]+)\]\((?P<url>https?://[^\s)]+)\)$")
PERSON_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z.'-]*(?: [A-Za-z][A-Za-z.'-]*)+$")

GITHUB_LINK_RE = re.compile(
    r"^https://github\.com/"
    r"(?P<owner>[A-Za-z0-9_.-]+)/"
    r"(?P<repo>[A-Za-z0-9_.-]+)/"
    r"(?P<kind>pull|issues)/"
    r"(?P<number>[1-9][0-9]*)"
    r"/?$"
)


def fail(message: str, fix: str | None = None) -> None:
    detail = message if fix is None else f"{message}\n\nHow to fix: {fix}"
    annotation = detail.replace("%", "%25").replace("\n", "%0A").replace("\r", "%0D")
    print(f"::error title=Student PR validation failed::{annotation}", file=sys.stderr)
    print(f"Validation failed: {detail}", file=sys.stderr)
    raise SystemExit(1)


def ok(message: str) -> None:
    print(f"OK: {message}")


def split_markdown_table_row(line: str) -> list[str]:
    stripped = line.strip()

    if not stripped.startswith("|") or not stripped.endswith("|"):
        fail(
            f"Invalid markdown table row:\n{line}",
            "Use one table row that starts and ends with `|`.",
        )

    return [cell.strip() for cell in stripped.strip("|").split("|")]


def require_ascii_text(value: str, label: str) -> None:
    if any(ord(ch) < 32 or ord(ch) > 126 for ch in value):
        fail(
            f"{label} must be written in English ASCII text:\n{value}",
            "Rewrite the value using English letters, digits, punctuation, and links only.",
        )


def parse_markdown_link(value: str, label: str) -> tuple[str, str]:
    match = MARKDOWN_LINK_RE.fullmatch(value)

    if match is None:
        fail(
            f"{label} must be a markdown link:\n{value}",
            "Use this format: [Visible text](https://example.com/path)",
        )

    text = match.group("text")
    url = match.group("url")
    require_ascii_text(text, label)
    require_ascii_text(url, f"{label} URL")
    return text, url


def validate_conference_talk_row(row: str, row_number: int) -> None:
    cells = split_markdown_table_row(row)

    if len(cells) != 6:
        fail(
            f"Conference talk row {row_number} must have 6 columns, got {len(cells)}:\n{row}",
            "Use exactly: Date, Name, Conference, Location, Format, Topic.",
        )

    date, name, conference, location, talk_format, topic = cells

    for label, value in [
        ("Date", date),
        ("Name", name),
        ("Conference", conference),
        ("Location", location),
        ("Format", talk_format),
        ("Topic", topic),
    ]:
        require_ascii_text(value, label)

    if DATE_RE.fullmatch(date) is None:
        fail(
            f"Invalid Date in conference talk row {row_number}: {date}",
            "Use `YYYY.MM`, for example `2026.05`.",
        )

    name_text, name_url = parse_markdown_link(name, "Name")

    if PERSON_NAME_RE.fullmatch(name_text) is None:
        fail(
            f"Invalid Name in conference talk row {row_number}: {name_text}",
            "Use the student's name and surname, for example `[Gleb Popov](https://github.com/gleb-pp/)`.",
        )

    if GITHUB_PROFILE_RE.fullmatch(name_url) is None:
        fail(
            f"Invalid GitHub profile link in conference talk row {row_number}: {name_url}",
            "Link the student's name to their GitHub profile.",
        )

    parse_markdown_link(conference, "Conference")

    if location != "online" and LOCATION_RE.fullmatch(location) is None:
        fail(
            f"Invalid Location in conference talk row {row_number}: {location}",
            "Use `online` or `<country>, <city>`, for example `Russia, Moscow`.",
        )

    if talk_format not in CONFERENCE_TALK_FORMATS:
        allowed = " / ".join(sorted(CONFERENCE_TALK_FORMATS))
        fail(
            f"Invalid Format in conference talk row {row_number}: {talk_format}",
            f"Use one of: {allowed}.",
        )

    parse_markdown_link(topic, "Topic")


def validate_conference_talks_content(content: str) -> None:
    lines = content.splitlines()

    try:
        header_index = lines.index(CONFERENCE_TABLE_HEADER)
    except ValueError:
        fail(
            f"{CONFERENCE_TALKS_FILE} must contain the conference talk table header.",
            f"Use exactly: {CONFERENCE_TABLE_HEADER}",
        )

    separator_index = header_index + 1

    if separator_index >= len(lines) or lines[separator_index] != CONFERENCE_TABLE_SEPARATOR:
        fail(
            f"{CONFERENCE_TALKS_FILE} has an invalid markdown table separator.",
            f"Use exactly: {CONFERENCE_TABLE_SEPARATOR}",
        )

    rows = [line for line in lines[separator_index + 1 :] if line.strip()]

    if not rows:
        fail(
            f"{CONFERENCE_TALKS_FILE} must contain at least one conference talk row.",
            "Add one row below the table header.",
        )

    seen: set[str] = set()

    for offset, row in enumerate(rows, start=separator_index + 2):
        if row in seen:
            fail(
                f"Duplicate conference talk row in {CONFERENCE_TALKS_FILE}:\n{row}",
                "Remove the duplicate row.",
            )

        seen.add(row)
        validate_conference_talk_row(row, offset)


def read_event() -> dict[str, Any]:
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path:
        fail(
            "GITHUB_EVENT_PATH is not set.",
            "Run this validator from the GitHub Actions pull request workflow.",
        )

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def api_url(path: str) -> str:
    base = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    return f"{base}{path}"


def gh_get(url: str) -> Any:
    token = os.environ.get("GITHUB_TOKEN")

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "opensource-log-validator",
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
        fail(
            f"GitHub API request failed: HTTP {e.code}: {url}\n{body}",
            "Check that the linked GitHub PR or issue exists and is visible.",
        )

    except urllib.error.URLError as e:
        fail(
            f"GitHub API request failed: {url}\n{e}",
            "Try again later. The validator could not reach the GitHub API.",
        )


def gh_get_paginated(url: str) -> list[Any]:
    items: list[Any] = []
    page = 1
    sep = "&" if "?" in url else "?"

    while True:
        page_url = f"{url}{sep}per_page=100&page={page}"
        chunk = gh_get(page_url)

        if not isinstance(chunk, list):
            fail(
                f"Expected list response from GitHub API: {page_url}",
                "Try again later. The validator received an unexpected GitHub API response.",
            )

        items.extend(chunk)

        if len(chunk) < 100:
            return items

        page += 1


def get_pr_file_content(head_repo: str, head_sha: str, filename: str) -> str:
    encoded_path = urllib.parse.quote(filename, safe="/")
    url = api_url(f"/repos/{head_repo}/contents/{encoded_path}?ref={head_sha}")

    data = gh_get(url)

    if not isinstance(data, dict) or data.get("type") != "file":
        fail(
            f"Cannot read PR file content: {filename}",
            "Make sure the file exists in your PR branch and was pushed to GitHub.",
        )

    raw = data.get("content")
    encoding = data.get("encoding")

    if not isinstance(raw, str) or encoding != "base64":
        fail(
            f"Unexpected content encoding for {filename}",
            "Make sure your student entry is a normal text file.",
        )

    return base64.b64decode(raw).decode("utf-8")


def get_link_author(owner: str, repo: str, kind: str, number: str) -> str:
    endpoint = "pulls" if kind == "pull" else "issues"
    url = api_url(f"/repos/{owner}/{repo}/{endpoint}/{number}")

    data = gh_get(url)

    try:
        login = data["user"]["login"]
    except Exception:
        fail(
            f"Cannot find author of https://github.com/{owner}/{repo}/{kind}/{number}",
            "Use a public GitHub PR or issue URL that exists.",
        )

    if not isinstance(login, str) or not login:
        fail(
            f"Invalid author for https://github.com/{owner}/{repo}/{kind}/{number}",
            "Use a public GitHub PR or issue URL with a visible author.",
        )

    return login


def main() -> None:
    event = read_event()

    pr = event.get("pull_request")
    if not isinstance(pr, dict):
        fail(
            "This workflow must run on a pull_request_target event.",
            "Open or update a pull request instead of running this validator directly.",
        )

    pr_number = pr.get("number")
    pr_author = pr.get("user", {}).get("login")
    base_repo = pr.get("base", {}).get("repo", {}).get("full_name")
    head_repo = pr.get("head", {}).get("repo", {}).get("full_name")
    head_sha = pr.get("head", {}).get("sha")

    if not all(
        isinstance(x, str) and x for x in [pr_author, base_repo, head_repo, head_sha]
    ):
        fail(
            "Cannot read PR metadata from GitHub event payload.",
            "Close and reopen the pull request, or ask a maintainer to rerun checks.",
        )

    if not isinstance(pr_number, int):
        fail(
            "Cannot read PR number from GitHub event payload.",
            "Close and reopen the pull request, or ask a maintainer to rerun checks.",
        )

    files_url = api_url(f"/repos/{base_repo}/pulls/{pr_number}/files")
    changed_files = gh_get_paginated(files_url)

    if not changed_files:
        fail(
            "PR has no changed files.",
            "Add or modify exactly one file: data/students/<your-github-username>.txt",
        )

    student_files: list[dict[str, Any]] = []
    conference_talk_files: list[dict[str, Any]] = []
    forbidden: list[str] = []

    for f in changed_files:
        filename = f.get("filename")
        status = f.get("status")

        if not isinstance(filename, str) or not isinstance(status, str):
            fail(
                "Malformed changed-file data from GitHub API.",
                "Ask a maintainer to rerun checks.",
            )

        if STUDENT_FILE_RE.fullmatch(filename) and status in {"added", "modified"}:
            student_files.append(f)
        elif filename == CONFERENCE_TALKS_FILE and status in {"added", "modified"}:
            conference_talk_files.append(f)
        else:
            forbidden.append(f"{filename} ({status})")

    if forbidden:
        fail(
            "This PR may only add/modify one student contribution file or the "
            "conference talks table.\n"
            + "\n".join(f"Forbidden: {x}" for x in forbidden),
            "Keep either data/students/<your-github-username>.txt or "
            f"{CONFERENCE_TALKS_FILE}. Do not edit generated files such as "
            f"{GENERATED_CONTRIBUTION_LOG_FILE}.",
        )

    if len(student_files) == 1 and not conference_talk_files:
        filename = student_files[0]["filename"]

    elif len(conference_talk_files) == 1 and not student_files:
        filename = conference_talk_files[0]["filename"]
        content = get_pr_file_content(head_repo, head_sha, filename)
        validate_conference_talks_content(content)
        ok(f"Validated conference talk table: {filename}")
        ok("All checks passed.")
        return

    else:
        fail(
            "This PR must use exactly one accepted student update format.",
            "Either update data/students/<your-github-username>.txt with GitHub PR/issue links, "
            f"or update {CONFERENCE_TALKS_FILE} with conference talk rows.",
        )

    m = STUDENT_FILE_RE.fullmatch(filename)

    if m is None:
        fail(
            f"Invalid student filename: {filename}",
            "Use exactly this path format: data/students/<your-github-username>.txt",
        )

    file_username = m.group("username")

    if file_username.lower() != pr_author.lower():
        fail(
            "Filename username does not match current PR author.\n"
            f"File: {filename}\n"
            f"Filename user: {file_username}\n"
            f"PR author: {pr_author}",
            f"Rename the file to data/students/{pr_author}.txt",
        )

    content = get_pr_file_content(head_repo, head_sha, filename)
    lines = [line.strip() for line in content.splitlines() if line.strip()]

    if not lines:
        fail(
            f"{filename} must contain at least one GitHub PR/issue link.",
            "Add one link per line, for example https://github.com/OWNER/REPO/pull/123",
        )

    seen: set[str] = set()

    for line in lines:
        if line in seen:
            fail(
                f"Duplicate link in {filename}: {line}",
                "Remove the duplicate line. Each contribution link should appear once.",
            )

        seen.add(line)

        lm = GITHUB_LINK_RE.fullmatch(line)

        if not lm:
            fail(
                f"Invalid link format in {filename}:\n{line}\n\n"
                "Allowed formats:\n"
                "https://github.com/OWNER/REPO/pull/123\n"
                "https://github.com/OWNER/REPO/issues/123",
                "Replace the line with a full GitHub pull request or issue URL.",
            )

        owner = lm.group("owner")
        repo = lm.group("repo")
        kind = lm.group("kind")
        number = lm.group("number")

        linked_author = get_link_author(owner, repo, kind, number)

        if linked_author.lower() != pr_author.lower():
            item = "issue" if kind == "issues" else "pull request"

            fail(
                f"Linked {item} author does not match current PR author.\n"
                f"Link: {line}\n"
                f"Link author: {linked_author}\n"
                f"PR author: {pr_author}",
                "Use only PR or issue links that you opened from your GitHub account.",
            )

    ok(f"PR author matches filename: {pr_author} == {filename}")
    ok(f"Validated {len(lines)} GitHub PR/issue link(s).")
    ok("All checks passed.")


if __name__ == "__main__":
    main()
