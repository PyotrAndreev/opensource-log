# Open Source Log

A public record of my students’ contributions to existing open-source projects.

This repository collects verifiable links to real open-source activity made by my students: pull requests (PR), issues.  

## Table of Contents

- [Purpose](#purpose)
- [What Counts as a Contribution](#what-counts-as-a-contribution)
- [How to Add Your Contribution](#how-to-add-your-contribution)
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

## Rules

- Add only your own contributions. Don't work with files of others.
- Add only PR/issuse links to existing big open-source projects.
- Add one contribution link per line.
- Do not edit `students.md` manually. It is generated automatically.

