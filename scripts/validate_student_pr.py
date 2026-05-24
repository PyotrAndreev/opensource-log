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
        else:
            forbidden.append(f"{filename} ({status})")

    if forbidden:
        fail(
            "This PR may only add/modify one file under "
            "data/students/<github-username>.txt.\n"
            + "\n".join(f"Forbidden: {x}" for x in forbidden),
            "Remove changes to all other files. Keep only your own student file.",
        )

    if len(student_files) != 1:
        fail(
            "This PR must add/modify exactly one student file: "
            "data/students/<github-username>.txt",
            "Create one file named data/students/<your-github-username>.txt and put your links there.",
        )

    filename = student_files[0]["filename"]
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
