import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import validate_student_pr


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

    monkeypatch.setattr(validate_student_pr, "read_event", lambda: event)
    monkeypatch.setattr(validate_student_pr, "gh_get_paginated", lambda url: changed_files)
    monkeypatch.setattr(
        validate_student_pr,
        "get_pr_file_content",
        lambda head_repo, head_sha, filename: file_content,
    )
    monkeypatch.setattr(
        validate_student_pr,
        "get_link_author",
        lambda owner, repo, kind, number: linked_author,
    )

    return validate_student_pr.main()


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


def test_failure_message_includes_specific_fix(monkeypatch, capsys):
    event = make_event(pr_author="alice")
    changed_files = [
        {
            "filename": "data/students/bob.txt",
            "status": "added",
        }
    ]

    with pytest.raises(SystemExit):
        run_validator(
            monkeypatch,
            event=event,
            changed_files=changed_files,
            linked_author="alice",
        )

    err = capsys.readouterr().err

    assert "::error title=Student PR validation failed::" in err
    assert "Filename username does not match current PR author." in err
    assert "How to fix: Rename the file to data/students/alice.txt" in err


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


def test_generated_contribution_log_change_fails(monkeypatch):
    changed_files = [
        {
            "filename": "students_contribute_log.md",
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


def test_conference_talks_file_passes(monkeypatch, capsys):
    content = "\n".join(
        [
            "# Student Conference Talks",
            "",
            "| Date | Name | Conference | Location | Format | Topic |",
            "| --- | --- | --- | --- | --- | --- |",
            "| 2026.05 | [Gleb Popov](https://github.com/gleb-pp/) | [PythonDays](https://example.com/python-days) | online | talk | [Generators in CPython](https://github.com/gleb-pp/pygen-research) |",
            "",
        ]
    )

    run_validator(
        monkeypatch,
        changed_files=[
            {
                "filename": "students_conference_talks.md",
                "status": "modified",
            }
        ],
        file_content=content,
    )

    out = capsys.readouterr().out

    assert "Validated conference talk table" in out
    assert "All checks passed" in out


@pytest.mark.parametrize(
    "row",
    [
        "| 2026-05 | [Gleb Popov](https://github.com/gleb-pp/) | [PythonDays](https://example.com) | online | talk | [Topic](https://example.com/topic) |",
        "| 2026.05 | Gleb Popov | [PythonDays](https://example.com) | online | talk | [Topic](https://example.com/topic) |",
        "| 2026.05 | [Gleb Popov](https://example.com/gleb) | [PythonDays](https://example.com) | online | talk | [Topic](https://example.com/topic) |",
        "| 2026.05 | [Gleb Popov](https://github.com/gleb-pp/) | [PythonDays](https://example.com) | somewhere | talk | [Topic](https://example.com/topic) |",
        "| 2026.05 | [Gleb Popov](https://github.com/gleb-pp/) | [PythonDays](https://example.com) | online | lecture | [Topic](https://example.com/topic) |",
        "| 2026.05 | [Gleb Popov](https://github.com/gleb-pp/) | [PythonDays](https://example.com) | online | talk | Тема |",
    ],
)
def test_invalid_conference_talk_row_fails(monkeypatch, row):
    content = "\n".join(
        [
            "# Student Conference Talks",
            "",
            "| Date | Name | Conference | Location | Format | Topic |",
            "| --- | --- | --- | --- | --- | --- |",
            row,
            "",
        ]
    )

    with pytest.raises(SystemExit) as exc:
        run_validator(
            monkeypatch,
            changed_files=[
                {
                    "filename": "students_conference_talks.md",
                    "status": "modified",
                }
            ],
            file_content=content,
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
