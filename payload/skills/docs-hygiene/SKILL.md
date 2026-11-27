---
name: docs-hygiene
description: Use when a project's docs have grown until agents slow down, lose track or loop (many specs and plans, long decision logs, rules scattered over many files, a CLAUDE.md that keeps growing), or when the user asks to audit, clean up, condense or reorganise docs, or to keep them from growing back. Measures first, gives each kind of doc one job, condenses without losing rulings, moves files with link rewrites, adds a STATUS file and a docs layout test, and sets writing rules for docs. For the owner's personal projects; not for work repos that have their own team unless the owner says so. Not for setting up a new project (project-kickoff / project-adopt) or writing long manuals (docs-architect).
---

# Docs hygiene

Agents fail on the sum of locally correct steps: each spec, plan and log entry was fine, together they bury the
current state. This skill audits the docs, cuts them back to one source per topic and adds a test so they stay small.

Plan ≠ go. Steps 1 and 2 only read and report. Ask the owner before moving, condensing or deleting anything.

## 1. Measure (read-only)

Report numbers, not impressions:
- Size per folder and the 15 largest files, docs against code: `du -sh docs/* | sort -h`,
  `git ls-files -z '*.md' | xargs -0 wc -c | sort -n | tail -15`.
- Inbound links per doc, so nothing linked is moved blindly: `git grep -n '<file-name>.md'` per candidate.
- Broken links today: `python3 ~/.claude/skills/docs-hygiene/scripts/check_links.py .` (save the output as the
  baseline).
- Duplication: the same topic written in several files (grep key terms; compare headings).
- Where work loops: commits per area, `git log --since='1 month ago' --name-only --format= | cut -d/ -f1-2 | sort |
  uniq -c | sort -n`. One area far ahead of the rest usually means a design problem, not a docs one; say so.
- Rules: how many files hold agent rules, and any rule that contradicts config (e.g. a port the rules forbid in a
  launch config, a test command that no longer exists).
- Paperwork per task: how many files a small change produced (spec + plan + log is the usual bloat), and which
  plugin or skill forces it.

## 2. Propose a layout

One job per kind of doc, one source of truth per topic. Other places link to the source; they never copy it.

| Kind | Job | Read |
|---|---|---|
| `STATUS.md` | Now / Next / Parked, under ~60 lines | first, every task |
| specs | what will be built; front matter `status: active` or `done` | for that work |
| decisions | why; owner rulings | when the topic comes up |
| knowledge / reference | how the code works; the source of truth | per part touched |
| archive | history | only when asked or linked |

Size the paperwork to the task: no spec for a small change. A spec is one short file whose Tasks section is the
plan; no separate plan file. If a workflow plugin forces spec + plan + log for every task, propose dropping it for
this project. Show the owner the layout, the moves and the numbers, and wait for a yes.

## 3. Condense, don't delete

Per oversized file:
1. Copy the full file to `archive/` (same relative path).
2. Rewrite the live file as rulings, current values, traps and open items only, following the writing rules below.
3. Keep every heading that something links to, verbatim, so anchors still resolve.
4. Add `Full record: [archive](...)` at the top.
5. Owner rulings must survive with the same meaning: count "owner" (and the project's ruling words) before and
   after, and list any ruling that was merged.
6. Run `check_links.py` and diff against the baseline.

## 4. Move with path rewrites

One pass per batch: `git mv`, then rewrite absolute and relative paths in every tracked text file (docs, skills,
tests, config, code comments). Diff the broken-link output before and after; fix only the new breaks and report
old ones separately.

## 5. Keep the aggregate visible

- `STATUS.md` is updated in the same change as the work.
- "Done means closed": rulings go into the source doc, the spec gets `status: done`, STATUS is updated. Put this in
  the project's task procedure (a project skill), not only in prose.
- CLAUDE.md stays short (~80 lines): hard rules and pointers. Procedures go to project skills loaded on demand, each
  rule with its reason and the real mistake behind it.

## 6. Enforce with a test

Add a docs layout test to the project's own test runner; template: `references/docs-layout.test.ts` (Vitest; port
it to the project's language). It fails on: a forbidden folder coming back, unknown entries at the docs root, a
decisions file over a cap, STATUS over its cap or missing Now/Next/Parked, a spec without status, a new spec over
its cap, CLAUDE.md over its cap. Defaults: decisions 32 KB, STATUS 60 lines, new spec 150 lines, CLAUDE.md 80
lines. They are judgement calls; set them with the owner from the step 1 numbers. Apply the spec cap from a date so
old specs do not fail.

## 7. Merging with a branch that still uses the old layout

Dry-run first: `git merge-tree --write-tree <ours> <theirs>`. The other branch keeps writing to old paths: on each
merge rewrite paths again, fold new log sections into the condensed file (rename detection sends them to the
archive copy), then re-run the test and `check_links.py`.

## 8. Outside review

The model inside a long task loop does not see the aggregate. After each spec reaches done, suggest a
fresh-context session that runs steps 1–2 only (audit, no work).

## Writing rules for docs

Apply when condensing and to every doc written afterwards:
- Lead with the answer, the current value or the ruling; reasons after, only as much as needed.
- One recommended option, not a survey. Rejected options get one line in decisions, if any.
- Do not repeat what another doc owns: link to it.
- Cut sentences that add no information (restating the heading, "this section describes").
- Lists or tables for lists; paragraphs only for reasoning.
- Each rule carries its reason in one line; history and dated stories go to archive.
- Short goals and summaries: one or two sentences.
