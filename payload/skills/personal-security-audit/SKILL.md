---
name: personal-security-audit
description: Project-wide security audit for the personal dev team (for personal projects; not for work repos that another team handles) — checks the whole project, not one diff, for ways it could be hacked or leak data. Maps the attack surface and a short threat model, then checks secrets, authentication and access rules, injection, browser and session rules, outgoing requests, dependencies, configuration and deployment, data protection, AI features and money or trading logic, and returns a ranked report with attack scenarios. Run by personal-reviewer with `MODE: security-audit` when the user asks for a security check ("ตรวจ security", "กันโดน hack"), before a project first goes public, or after it adds sign-in, payments, uploads or AI features. Read-only; never attacks a live system. Do NOT use for work repos that another team handles.
---

# personal-security-audit

Find the ways a real attacker could break into this project, misuse it, or read data they should not, and rank them by real risk. It is an audit of the whole project at its current state, not a review of one diff.

## Ground rules

- **Read-only.** Never edit project files. The report goes in your final message; the PM files it.
- **Never read a secret's value.** Check whether secret files exist, are ignored and are tracked, by name only (`git ls-files`, `git check-ignore`). Secret-file guards block reads on purpose; do not work around them. In the report, name the file, line and kind of secret, and mask any value (`sk-…abcd` at most).
- **Never attack a live system.** No requests to production URLs, third-party services or anyone else's machine; no brute force, scanning or load. Static reading and local commands only. A check against a local dev server (`localhost`) is allowed only when the PM's dispatch says so, and only with requests that change no data.
- **Evidence or nothing.** Every finding cites `file_path:line_number` (or the command and its output) and an attack scenario a real attacker would plausibly run. Mark anything you could not confirm as `Unconfirmed`, never as a finding.
- **Stay in scope.** Audit the project folder the PM names. Note issues in other systems (hosting dashboard settings, DNS, provider consoles) under "Needs a manual check", because you cannot see them.

## Step 1 — Map the attack surface

Read `AGENTS.md`/`CLAUDE.md`, the manifests, the deployment config and the entry points. Write down:

- **Entry points:** every HTTP route and API handler, server actions, webhooks, scheduled jobs, CLI commands, file uploads, WebSocket or realtime channels, and admin screens.
- **Assets:** what an attacker would want — user accounts and personal data, API keys and tokens, money or trading actions, paid API quota (AI, market data), the database.
- **Trust boundaries:** where data comes from outside (browser, webhook sender, third-party API, uploaded file, model output) and where it crosses into something privileged (database, shell, file system, another service, a model with tools).
- **Actors:** anyone on the internet, a signed-in user, another tenant's user, an admin, a compromised dependency.

Keep this to a short table. It drives every later step: each step checks the entry points and boundaries that apply.

## Step 2 — Checks

Use the "Security checks" list in `personal-review-method` as the per-item checklist, applied to the whole project instead of a diff. In addition:

1. **Secrets and history:** run `bash ~/.claude/hooks/run-python.sh ~/.claude/hooks/secret-scan/pre_push_guard.py audit --repo <project>` (long timeout; it can take minutes). It covers tracked `.env` and key files, secret-looking strings and personal information in the current files, and the same in every old commit, marked pushed or local only. Read its findings and report commit and file only. Then check by reading what it cannot: secrets the regex misses, and server secrets reaching client code through public env prefixes.
2. **Authentication:** how sign-in works (library, session or JWT), password hashing algorithm, JWT signature and algorithm checks, session expiry and logout, password reset and email-change flows, account enumeration in error messages, rate limits on sign-in and reset.
3. **Access rules:** for each entry point from Step 1, is there a check that the caller may do this to this specific record? List entry points with no check. For Supabase or Firebase, check that row-level security or security rules are on for every table or collection the client can reach.
4. **Injection and unsafe sinks:** search the whole codebase for raw queries, shell execution, `eval`, dynamic imports, path joins with input, HTML injection and unsafe deserialisation, then trace each hit back to see whether outside input reaches it.
5. **Dependencies and supply chain:** run the project's audit command (`npm audit`, `pnpm audit`, `bun audit`, `pip-audit`, `cargo audit` — whichever fits the lockfile) and report High and Critical items that are reachable in production code; a missing or ignored lockfile; install scripts; unpinned GitHub Actions; packages abandoned for years.
6. **Configuration and deployment:** security headers (CSP, HSTS, `X-Frame-Options` or `frame-ancestors`, `X-Content-Type-Options`); CORS; debug mode, verbose errors or stack traces in production; public source maps; default or weak credentials; database or admin panels reachable from the internet; containers running as root; ports exposed beyond need; CI secrets available to pull requests from forks.
7. **Data protection:** personal data in logs, analytics or error trackers; data kept with no reason or no deletion path; backups; encryption of especially sensitive fields.
8. **AI features:** prompt injection paths (untrusted text into a model that has tools or private data), what the model's tools can reach, model output used as HTML, SQL or shell, provider keys in client code, and limits that stop one user from spending the whole AI budget.
9. **Money and trading:** real orders only behind explicit confirmation and server-side checks; broker or exchange keys with the narrowest scope (read-only where possible); idempotency for payments and orders, so a retry cannot charge or trade twice; payment webhooks verified; amounts and prices computed on the server, never trusted from the client.

## Step 3 — Rate and report

Severity:

- **Critical:** anyone on the internet can, without signing in, take over accounts, read or change other users' data, run code on the server, move money or place trades, or obtain a live secret.
- **High:** the same harm but needing a signed-in user or a condition an attacker can easily arrange; or a live secret in git history.
- **Medium:** real weakness with limited impact or hard preconditions (missing headers, weak rate limits, verbose errors).
- **Low:** hardening only.

A scenario nobody would plausibly run is at most Low. Do not pad; if an area is clean, say so under "Checked and clean".

## Output contract (the final message)

```
## Security audit: <project> (<date>, commit <short hash>)
- Overall: <one line: the biggest risk, or "no Critical or High found">
- Attack surface: <the Step 1 table, short>
- Findings:
  - [Critical|High|Medium|Low] <title> — file_path:line_number
    Attacker: <who> · Scenario: <steps → what they gain> · Fix: <smallest fix that closes it>
- Unconfirmed (could not verify): <item and what would confirm it / none>
- Needs a manual check: <hosting, DNS, provider console settings to look at / none>
- Checked and clean: <checks with nothing to report>
- Commands run: <command → result summary>
- Skills loaded: <every skill you invoked or read>
```
