# Open Source Log

[students.md](https://github.com/PyotrAndreev/opensource-log/blob/main/students.md) -- a public record of my students’ contributions to existing open-source projects.

This repository collects verifiable links to real open-source activity made by my students: pull requests (PR), issues.  

## Table of Contents

- [Purpose](#purpose)
- [What Counts as a Contribution](#what-counts-as-a-contribution)
- [How to Add Your Contribution](#how-to-add-your-contribution)
- [How Your PR Is Checked](#how-your-pr-is-checked)
- [Rules](#rules)

## Purpose

This repository demonstrates that students can have a meaningful impact on open source when they receive the right support.  

## What Counts as a Contribution

Good examples:
- **Pull** request to an existing big open-source repository
- **Issue** with a clear bug report or feature proposal

## How to Add Your Contribution
Students with open-source contributions are welcome to submit a PRs through the following steps (Linux):

1. Fork this repository & clone:
```bash
gh repo fork PyotrAndreev/opensource-log --clone
cd opensource-log
```

2. Create a file named: `data/students/<your-github-username>.txt`
3. Put your open-source contribution links inside that file. Valid format:
```text
https://github.com/owner/repository/pull/123
https://github.com/owner/repository/issues/123
```

4. Commit & Push your change:
```bash
git add *
git commit -m "PR from <surname> <given name>"
git push
```
5. Open a pull request from your local fork:
```bash
gh pr create \
  --repo PyotrAndreev/opensource-log \
  --base main \
  --title "Add my contribution link" \
  --body ""
```

The contribution log is updated automatically from `data/students/*`.

If this is your 1st time using **GitHub CLI**, run:
```bash
gh auth login
```

## How Your PR Is Checked

When you open a pull request, GitHub automatically runs the `Validate student PR` check.

The check must pass before your pull request can be merged. If something is wrong, GitHub will show a failed check with a specific error message and a `How to fix:` instruction.

The validator checks that:

- You changed exactly one file.
- The file is named `data/students/<your-github-username>.txt`.
- The filename matches your GitHub username.
- The file contains at least one contribution link.
- Each line is a GitHub pull request or issue link.
- Each linked pull request or issue was opened by your GitHub account.
- There are no duplicate links.
- You did not edit generated files such as `students.md`.

After your pull request is merged, `students.md` is rebuilt automatically. It shows your contribution, project, type, current status, and topic.

## Rules

- Add only your own contributions. Don't work with files of others.
- Add only PR/issuse links to existing big open-source projects.
- Add one contribution link per line.
- Do not edit `students.md` manually. It is generated automatically after your PR is merged.
- If the validation check fails, read the `How to fix:` message and update your PR.
