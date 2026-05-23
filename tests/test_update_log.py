import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import update_log


def make_event(
    *,
    pr_author="octocat",
    pr_number=1,
    base_repo="PyotrAndreev/opensource-log",
    head_repo="octocat/opensource-log",
    head_sha="abc123",
):
    return {
        "pull_request": {
            "number": pr_number,
            "user": {"login": pr_author},
            "base": {
                "repo": {"full_name": base_repo},
            },
            "head": {
                "repo": {"full_name": head_repo},
                "sha": head_sha,
            },
        }
    }


def run_validator(
    monkeypatch,
    *,
    event=None,
    changed_files=None,
    file_content=None,
    linked_author="octocat",
):
    if event is None:
        event = make_event()

    if changed_files is None:
        changed_files = [
            {
                "filename": "data/students/octocat.txt",
                "status": "added",
            }
        ]

    if file_content is None:
        file_content = "https://github.com/python/cpython/pull/123\n"

    monkeypatch.setattr(update_log, "read_event", lambda: event)
    monkeypatch.setattr(update_log, "gh_get_paginated", lambda url: changed_files)
    monkeypatch.setattr(
        update_log,
        "get_pr_file_content",
        lambda head_repo, head_sha, filename: file_content,
    )
    monkeypatch.setattr(
        update_log,
        "get_link_author",
        lambda owner, repo, kind, number: linked_author,
    )

    return update_log.main()


def test_valid_pr_passes(monkeypatch, capsys):
    run_validator(monkeypatch)

    out = capsys.readouterr().out

    assert "All checks passed" in out
    assert "Validated 1 GitHub PR/issue link" in out


def test_filename_must_match_pr_author(monkeypatch):
    event = make_event(pr_author="alice")

    changed_files = [
        {
            "filename": "data/students/bob.txt",
            "status": "added",
        }
    ]

    with pytest.raises(SystemExit) as exc:
        run_validator(
            monkeypatch,
            event=event,
            changed_files=changed_files,
            linked_author="alice",
        )

    assert exc.value.code == 1


def test_link_author_must_match_pr_author(monkeypatch):
    with pytest.raises(SystemExit) as exc:
        run_validator(
            monkeypatch,
            linked_author="someone-else",
        )

    assert exc.value.code == 1


def test_invalid_link_format_fails(monkeypatch):
    with pytest.raises(SystemExit) as exc:
        run_validator(
            monkeypatch,
            file_content="not-a-github-link\n",
        )

    assert exc.value.code == 1


def test_issue_link_is_allowed(monkeypatch, capsys):
    run_validator(
        monkeypatch,
        file_content="https://github.com/python/cpython/issues/123\n",
    )

    out = capsys.readouterr().out

    assert "All checks passed" in out


def test_duplicate_links_fail(monkeypatch):
    link = "https://github.com/python/cpython/pull/123"

    with pytest.raises(SystemExit) as exc:
        run_validator(
            monkeypatch,
            file_content=f"{link}\n{link}\n",
        )

    assert exc.value.code == 1


def test_forbidden_file_change_fails(monkeypatch):
    changed_files = [
        {
            "filename": "README.md",
            "status": "modified",
        }
    ]

    with pytest.raises(SystemExit) as exc:
        run_validator(
            monkeypatch,
            changed_files=changed_files,
        )

    assert exc.value.code == 1


def test_more_than_one_student_file_fails(monkeypatch):
    changed_files = [
        {
            "filename": "data/students/octocat.txt",
            "status": "added",
        },
        {
            "filename": "data/students/alice.txt",
            "status": "added",
        },
    ]

    with pytest.raises(SystemExit) as exc:
        run_validator(
            monkeypatch,
            changed_files=changed_files,
        )

    assert exc.value.code == 1


def test_empty_student_file_fails(monkeypatch):
    with pytest.raises(SystemExit) as exc:
        run_validator(
            monkeypatch,
            file_content="\n\n",
        )

    assert exc.value.code == 1


@pytest.mark.parametrize(
    "filename",
    [
        "data/students/-octocat.txt",
        "data/students/octocat-.txt",
        "data/students/octo_cat.txt",
        "data/students/octocat.md",
        "students/octocat.txt",
        "data/students/octocat/profile.txt",
    ],
)
def test_invalid_student_filename_fails(monkeypatch, filename):
    changed_files = [
        {
            "filename": filename,
            "status": "added",
        }
    ]

    with pytest.raises(SystemExit) as exc:
        run_validator(
            monkeypatch,
            changed_files=changed_files,
        )

    assert exc.value.code == 1
