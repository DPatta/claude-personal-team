---
name: correct
description: Stops a mistake that agents keep repeating by fixing it at the highest level that holds (structure, then a hook, type, lint or check, then a test, and a written rule only as a last resort), proving each new check catches the real past mistake. Use when the user says an agent made the same mistake again ("ทำผิดซ้ำ", "บอกไปแล้ว", "again"), before adding a new rule to Preferences.md, CLAUDE.md, AGENTS.md or an agent file, or on /correct.
---

# correct

Adapted from `/correct` in [pstack](https://github.com/cursor/plugins/tree/main/pstack) by Lauren Tan (MIT License).
- From pstack: grouping mistakes into classes with evidence, fixing at the highest level that works (structure, then types, then a lint or check, then a written rule), proving each check fails on a real past mistake, exceptions with a reason and expiry, and the rule-to-enforcement table.
- Our own: the Claude Code levels (hooks through `update-config`, an agent's `tools:` limit), showing the plan and waiting for the user's go instead of fixing at once, backups, fail-safe hooks, test inputs in scratchpad files, the Thai report, and no commit unless asked.

A written rule is the weakest fix: nothing fails when an agent skips it. This skill moves a repeated mistake into structure that blocks it.

## 1. Collect the mistake classes

- Read the evidence: the user's correction in this session, feedback memories (`~/.claude/projects/*/memory/`), `Preferences.md`, the project's `AGENTS.md` / `CLAUDE.md`, agent files, reverts and fix commits (`git log --grep`), and review findings.
- Group the mistakes into classes, each in one sentence: what the agent does, and what it should do instead.
- A class counts once it has happened **twice**. Cite both occurrences (a date, memory file, commit or transcript). A one-time mistake gets a memory note, not structure.

## 2. Choose the highest level that works

Try each level in order. Stop at the first one that would have blocked both occurrences.

1. **Structure.** Remove the second way of doing the thing: one owner for each piece of state, delete the old API or path, and make the wrong state impossible to represent.
2. **A fence that fails loudly.** In order of preference:
   - A type.
   - A lint or CI check.
   - A git hook.
   - A Claude Code hook: a `PreToolUse` deny or ask, or a `PostToolUse` check. Load the `update-config` skill first.
   - An agent's `tools:` limit.
   The error text must name what to do instead: the file, function, command or skill.
3. **A behavior test** that fails when the mistake comes back.
4. **A written rule** in `Preferences.md`, `CLAUDE.md`, `AGENTS.md` or an agent file. Use it only for judgment calls that no check can decide, and say so in the plan.

For each class, write down the level chosen and why every higher level does not work.

## 3. Plan, then wait

- Show the plan to the user in Thai. List each class with its evidence, the level chosen, the exact files to change and the proof you will run.
- Asking for a plan is not a go. Wait for the user's explicit go before you edit hooks, settings, agents or code (Preferences.md > ก่อนถาม / ก่อนลงมือ).

## 4. Build and prove

- Back up every file before you change it, to `~/.claude/agents-archive/<date>-<topic>/` for `~/.claude` files.
- Prove that each new check **fails on a replay of the real past mistake** and **passes on correct use**.
  - For a hook: pipe a synthetic tool-input JSON through the command. The JSON must match what the past mistake sent.
  - Put test inputs in a file in the scratchpad, not inline in a Bash command. Otherwise the commit and push guards fire on your own test.
- A hook must fail safe. If the check cannot run (missing Python, a crash), it must block or ask, never silently allow.
- An exception to a new check needs a reason, an expiry date and the user's approval, all written next to the exception.

## 5. Keep the enforcement map

The file that holds the rules gets a short table at its end: `Preferences.md` for global rules, `AGENTS.md` for a project.

| Rule | Enforced by | Proof |
|---|---|---|
| <one line> | <hook / lint / type / test path, or "none (judgment)"> | <how it was shown to fail on the past mistake> |

A rule marked `none` is soft. When a soft rule is broken again, run this skill on it.

## 6. Report

Report to the user in Thai:
- For each class: the evidence, the level and why higher levels failed, the files changed, and the proof (command and result).
- The map rows you added or changed.
- Anything left soft, with the reason.

Do not commit unless the user asks. If the change belongs in the `claude-personal-team` repo, offer to run `export-from-mac.sh`.
