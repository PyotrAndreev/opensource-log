import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_markdown


def test_collect_student_contributions_uses_non_empty_lines_and_sorts_files(tmp_path):
    student_dir = tmp_path / "data" / "students"
    student_dir.mkdir(parents=True)
    (student_dir / "bob.txt").write_text("\nhttps://example.com/b\n\n", encoding="utf-8")
    (student_dir / "Alice.txt").write_text("https://example.com/a\n", encoding="utf-8")
    (student_dir / "empty.txt").write_text("\n", encoding="utf-8")

    assert build_markdown.collect_student_contributions(student_dir) == {
        "Alice": ["https://example.com/a"],
        "bob": ["https://example.com/b"],
    }


def test_render_students_md():
    rendered = build_markdown.render_students_md(
        [
            build_markdown.ContributionRow(
                contributor="Alice",
                contributor_url="https://github.com/Alice",
                project_name="owner/repo",
                project_url="https://github.com/owner/repo",
                contribution_type="PR",
                status="Merged",
                topic_title="Fix parser table",
                topic_url="https://github.com/owner/repo/pull/1",
            ),
            build_markdown.ContributionRow(
                contributor="bob",
                contributor_url="https://github.com/bob",
                project_name="org/tool",
                project_url="https://github.com/org/tool",
                contribution_type="Issue",
                status="Open",
                topic_title="Bug with | in title",
                topic_url="https://github.com/org/tool/issues/2",
            ),
        ]
    )

    assert rendered == "\n".join(
        [
            "# Student Contribution Log",
            "",
            "This file is generated from `data/students/*.txt`. Do not edit it manually.",
            "",
            "| Contributor | Project | Type | Status | Topic |",
            "| --- | --- | --- | --- | --- |",
            "| [Alice](https://github.com/Alice) | [owner/repo](https://github.com/owner/repo) | PR | Merged | [Fix parser table](https://github.com/owner/repo/pull/1) |",
            "| [bob](https://github.com/bob) | [org/tool](https://github.com/org/tool) | Issue | Open | [Bug with \\| in title](https://github.com/org/tool/issues/2) |",
            "",
        ]
    )


def test_render_empty_students_md():
    assert build_markdown.render_students_md([]) == "\n".join(
        [
            "# Student Contribution Log",
            "",
            "This file is generated from `data/students/*.txt`. Do not edit it manually.",
            "",
            "_No contributions recorded yet._",
            "",
        ]
    )


def test_build_student_rows_fetches_metadata_for_every_link():
    loaded_links = []

    def load_metadata(link):
        loaded_links.append(link)
        return build_markdown.ContributionMetadata(
            project_name="owner/repo",
            project_url="https://github.com/owner/repo",
            contribution_type="Issue",
            status="Closed",
            topic_title=f"Topic for {link.rsplit('/', 1)[-1]}",
            topic_url=link,
        )

    rows = build_markdown.build_student_rows(
        {
            "bob": ["https://github.com/owner/repo/issues/2"],
            "Alice": ["https://github.com/owner/repo/pull/1"],
        },
        metadata_loader=load_metadata,
    )

    assert loaded_links == [
        "https://github.com/owner/repo/pull/1",
        "https://github.com/owner/repo/issues/2",
    ]
    assert rows == [
        build_markdown.ContributionRow(
            contributor="Alice",
            contributor_url="https://github.com/Alice",
            project_name="owner/repo",
            project_url="https://github.com/owner/repo",
            contribution_type="Issue",
            status="Closed",
            topic_title="Topic for 1",
            topic_url="https://github.com/owner/repo/pull/1",
        ),
        build_markdown.ContributionRow(
            contributor="bob",
            contributor_url="https://github.com/bob",
            project_name="owner/repo",
            project_url="https://github.com/owner/repo",
            contribution_type="Issue",
            status="Closed",
            topic_title="Topic for 2",
            topic_url="https://github.com/owner/repo/issues/2",
        ),
    ]


def test_status_from_github_data_marks_merged_pull_request():
    assert build_markdown.status_from_github_data(
        "pull",
        {"state": "closed", "merged": True},
    ) == "Merged"


def test_status_from_github_data_uses_state_for_open_issue():
    assert build_markdown.status_from_github_data(
        "issues",
        {"state": "open"},
    ) == "Open"


def test_contribution_type_from_kind():
    assert build_markdown.contribution_type_from_kind("pull") == "PR"
    assert build_markdown.contribution_type_from_kind("issues") == "Issue"


def test_clean_topic_title_removes_leading_gh_reference():
    assert (
        build_markdown.clean_topic_title(
            "gh-69619: Clarify whitespace definition in str.strip docs"
        )
        == "Clarify whitespace definition in str.strip docs"
    )
