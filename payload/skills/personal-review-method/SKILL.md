---
name: personal-review-method
description: The code-review method for the personal dev team (for personal projects; not for work repos that another team handles). Six passes in order — spec match, blast radius, failure paths, derived data, security, conventions — plus money and market-data checks, severity calibration, the targeted re-review mode and a fixed output contract. Loaded by personal-reviewer before every review and by autopilot-reviewer in diff mode (which keeps its own severity, verdict, rounds and output); also usable by any agent asked for a second review of a personal-project diff. Do NOT use for work repos that follow another team's review process.
---

# personal-review-method

Find real defects in a diff, especially defects that do not crash. Read the actual diff (`git diff`, `git status` including untracked files) and the changed files in full; never trust a handoff's description of them.

## Review passes, in order

1. **Spec match:** does each claimed acceptance criterion actually hold in the code? Is anything out of scope included? If `docs/design/<feature-slug>-design.md` exists, are its states, components and copy implemented as designed? In docs-kit mode, also check that the doc work the task's criteria name (for example a section of `docs/design/ARCHITECTURE.md`) is in the diff and follows the project's `project-docs` skill. For a non-trivial diff that changes a code path, also load `scrutinize` and use its intent and simpler-approach questions here.
2. **Blast radius:** search for every caller or consumer of what changed. Does anything rely on the old behavior? Then look where a search for callers stops: data written to a file, database column, cache or network message that another reader parses; readers in another language or service; feature flags and config; the pinned library version or a local patch; timing and ordering. Name the one fact that makes the change safe, and check it.
3. **Failure paths:** async ordering, races, retries, timeouts, empty or missing data, partial failure. Trace what really happens, not what should happen.
4. **Derived data:** is any value cached or computed from a source of truth in a way that can go stale or disagree with it?
5. **Security:** apply every item of "Security checks" below that the diff touches.
6. **Conventions:** the project's `AGENTS.md` or `CLAUDE.md`, plus no abbreviated names.

Apply the project and stack skills the reviewer loaded in passes 1, 3, 5 and 6.

## Security checks

For each item, check only what the diff adds or changes, and trace the input from where it enters to where it is used. A finding names who can trigger it (anyone on the internet, any signed-in user, an admin only) and what they gain.

- **Who may call it:** every new or changed route, API handler, server action, webhook or job checks that the caller is signed in where it must be, and that the caller owns or may access the specific record (object-level checks, not only "is logged in"). Middleware or route matchers really cover the new path. Webhooks verify the sender's signature.
- **Injection:** user input reaching raw SQL or string-built queries, shell commands, file paths (`../`), `eval` or dynamic `require`/`import`, regular expressions built from input, or template rendering.
- **Browser output:** input rendered as HTML (`dangerouslySetInnerHTML`, `innerHTML`, `v-html`, markdown without sanitising), links built from input (`javascript:` URLs), open redirects to a URL taken from the request.
- **Outgoing requests:** a server fetching a URL or host taken from input (SSRF), without an allowlist.
- **Secrets:** secrets in code, tests, logs, error responses or the client bundle (for example a server key behind `NEXT_PUBLIC_`/`VITE_`), and `.env` files not ignored. Never print a secret's value in the review: name the file, line and kind only.
- **Data exposure:** responses that return more fields than the screen needs (password hashes, tokens, other users' data), and personal data written to logs or analytics.
- **Sessions and browser rules:** cookies without `HttpOnly`/`Secure`/`SameSite`; state-changing requests with cookie auth and no CSRF defence; CORS that reflects any origin together with credentials; tokens kept in `localStorage` when a cookie would do.
- **Abuse limits:** sign-in, sign-up, password reset, OTP, paid API calls and AI calls without rate limits or size limits; uploads without type and size checks.
- **New dependencies:** a new package in a manifest or lockfile — check its exact name for typosquatting, install scripts, maintenance and known vulnerabilities (run the project's audit command if it has one, for example `npm audit`).
- **AI features:** untrusted text (user input, web pages, files, emails) placed in a prompt for a model that can call tools or reach data it should not (prompt injection); model output rendered as HTML or run as code; provider keys in client code.

Severity for security: exploitable by anyone on the internet without signing in, or leaking secrets or other users' data, is **High**. Needing a signed-in user to harm only their own data is at most **Medium**. A project-wide check (not a diff) uses the `personal-security-audit` skill instead.

## Money and market data

If the diff touches money, prices or market data, also check for:

- Binary float used for money, or rounding applied at the wrong step
- Timezone errors, exchange holidays or half days ignored, and naive timestamps
- Mixing adjusted and unadjusted prices across a split or dividend
- Look-ahead bias: a backtest using data not yet available at that bar, including same-bar close fills
- Off-by-one errors in rolling windows, and survivorship bias in the symbol list
- Stale or missing data treated as a valid price, and provider rate limits ignored
- An order, fill or ledger write that gives a different result when a retry, restart or duplicate event runs it twice (no idempotency key, no upsert, no check of current state)
- A backtest, return or performance number claimed without the run count, the spread and what limits it

## Severity

- **High:** wrong results, data loss, a security issue, or an acceptance criterion not met
- **Medium:** a real bug in a less common path
- **Low:** maintainability only

Report only what you verified in the code, each with `file_path:line_number` and a concrete failing scenario. Do not pad the list. If the diff is clean, say so.

Give each finding its evidence level: `read` (you read the code at file:line), `traced` (you walked the failure path step by step) or `ran` (you ran a command or test that shows the failure). Run it when that is cheap and safe (a unit test, a script in a scratch folder; never real signals or shared data, Preferences.md > Safety). A `[High]` needs at least `traced`.

`[High]` needs a scenario a real person would plausibly produce. A contrived input that nobody types or sends (deeply nested shell quoting, hand-crafted edge forms found only by fuzzing) is `[Medium]` at most and goes under `Follow-ups`, however wrong the result looks. The Verdict is `FAIL` only when there is at least one `[High]`.

## Re-review mode — when the dispatch says `MODE: re-review`

The PM sends a re-review after a fix round. It is a targeted check, not a new full review: a fresh full pass every round always finds something new and keeps the fix loop spinning.

- **Scope:** the findings listed in the dispatch, the files the developer changed in this fix round, and the callers of anything whose behavior the fix changed. Do not re-run the full passes over the rest of the diff.
- **For each listed finding,** state `FIXED` or `NOT FIXED` with `file_path:line_number`.
- **`[High]` is allowed only** for a listed finding that is not fixed, or for a defect the fix itself introduced. Anything else you notice goes under `Follow-ups`. The PM records it; it does not start another round.

## Output contract (the final message)

```
## Review: <feature>
- Verdict: PASS / FAIL
- Acceptance criteria verified: <numbers>
- Mode: full / re-review
- Re-checked (re-review only): <finding> FIXED / NOT FIXED at file_path:line_number
- Findings (blocking):
  - [High] file_path:line_number: <defect>. Scenario: <inputs → wrong result>. Evidence: traced/ran <how>. Escalate: yes/no
- Follow-ups (not blocking):
  - [Medium/Low] file_path:line_number: <defect>. Scenario: <inputs → wrong result>. Evidence: read/traced/ran
- Test gaps: <acceptance criteria numbers or changed behavior with no automated test in the diff or existing suite, or none> (the PM uses this to decide whether to dispatch the Tester; it is not a blocking finding)
- Checked and clean: <passes with nothing to report>
- Skills loaded: <every skill you invoked or read>
```

Flag anything architectural as `Escalate: yes` so the PM can send it to `personal-architect`.

## Credits

Some rules in this file are adapted from [pstack](https://github.com/cursor/plugins/tree/main/pstack) by Lauren Tan (MIT License):

- Blast radius "look where a search for callers stops" and "name the one fact that makes the change safe": from pstack `blast-radius`.
- The evidence levels `read` / `traced` / `ran`: condensed from the "How sure are you" list in pstack `blast-radius`.
- Money checks on retries and duplicate events: our trading version of pstack `principle-make-operations-idempotent`.
- Numbers that need the run count, the spread and what limits them: our trading version of pstack `principle-explain-the-number`.
- Our own: the rule that `[High]` needs at least `traced`, the `Evidence` field in the output, and the Safety limits on running checks.

Everything else in this file is our own.
