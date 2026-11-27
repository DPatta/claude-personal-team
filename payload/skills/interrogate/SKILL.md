---
name: interrogate
description: Adversarial review where only proven findings survive. Parallel subagents, each in its own git worktree with a copy of the change, try to break it, and a finding is kept only if the session reruns its command and the output shows a failure that breaks the change's intent. Reports only, never fixes. Use on /interrogate, when the user asks to try to break a change ("ลองหาทางทำให้พัง", "ลองโจมตีโค้ดนี้"), or when the personal-dev-team PM wants proof-backed review of a risky diff (money, trading, auth, concurrency, data deletion, migrations) after the reviewer passes and before QA.
---

# interrogate

Adapted from `/interrogate` in [pstack](https://github.com/cursor/plugins/tree/main/pstack) by Lauren Tan (MIT License).
- From pstack: adversaries in separate worktrees with a copy of the change, the "Break this change" brief, keeping only findings whose rerun shows a failure that breaks the intent, and reporting without fixing.
- Our own: pstack uses adversaries from different model vendors. Here every adversary runs on the same model, so each one gets a different **angle** instead. Also ours: packaging the change as a patch, the safety limits, severity from `personal-review-method`, the hand-off to the PM's review loop, and worktree cleanup.

## 1. Frame

- **Scope:** by default, the uncommitted change against `HEAD`. If the user names a branch, use `<base>...<branch>`.
- **Intent:** write two sentences, the goal of the change and the promise it makes ("after this, X always holds"). A failure only counts if it breaks this intent.
- **Angles:** pick 2 or 3 angles that fit the change, one per adversary:
  - inputs and boundaries (empty, huge, malformed, unicode, negative, zero)
  - ordering and repetition (retries, duplicate events, concurrent calls, restart halfway)
  - state and data (stale caches, partial writes, migrations, what another reader parses)
  - security (who may call it, injection, leaked data)
  - money and market data (rounding, timezones, look-ahead, idempotency of orders and ledgers)
- **Package the change** for the worktrees, which start from `HEAD` without your uncommitted work. Run these in the main checkout:
  - `git diff HEAD --binary > <scratchpad>/interrogate/change.patch`
  - `git ls-files --others --exclude-standard`, then copy those untracked files into `<scratchpad>/interrogate/untracked/`. Keep their paths. Never copy `.env` or other secret files.

## 2. Fan out

Spawn all adversaries in **one message**. Each is an `Agent` call with `subagent_type: "general-purpose"` and `isolation: "worktree"`. Each brief contains:

- the intent, its own angle, the patch path and the untracked folder
- the setup: apply the patch with `git apply`, copy the untracked files in, install dependencies only from the existing lockfile
- the task, verbatim: "Break this change. Prove each finding by running a command against the real code in your worktree, and paste the command and its output. Leave out anything you did not run. No findings is a valid result."
- the limits:
  - Write tests or scripts only inside your worktree.
  - Never edit the main checkout, and never commit or push.
  - No real signals to processes you did not start, and no deleting shared data (Preferences.md > Safety).
  - No paid or rate-limited APIs.
  - Never read `.env` contents.
  - If a hook blocks you, report it and do not work around it.
- the report format: for each finding, the file:line, the command, the key output lines, and one sentence on how it breaks the intent. Also the worktree path.

## 3. Verify every finding yourself

- Rerun each finding's command in that adversary's worktree.
- Keep a finding only if your own output shows the failure **and** the failure breaks the intent from step 1.
- Merge findings that share a root cause.
- Rate severity with the rules in `personal-review-method`. A contrived input that nobody would really produce is at most `[Medium]`.

## 4. Report

Write the report in Thai, with technical terms in English. Do not apply any fix.

```
## Interrogate: <change>
- Intent: <goal> / <promise>
- Angles: <list>
- Verified findings:
  - [High/Medium/Low] file_path:line_number: <how it breaks the intent>. Command: `<cmd>` → <key output lines>
- Dropped: <count>, one line each: <finding> → not reproduced / does not break the intent / contrived
- Worktrees: <paths, removed or kept>
```

## 5. Hand off and clean up

- When the PM runs this skill, verified `[High]` findings follow the bounded review loop in `personal-dev-team`. Everything else is a deferred item.
- Remove only the worktrees this run created, with `git worktree remove <path>`, after the report. Keep a worktree only if the user wants to look at a reproduction, and say which one.
