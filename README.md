# claude-personal-team

A portable copy of my Claude Code **personal dev team**, so it works the same on macOS and Windows.

**Use it with the Claude Code CLI** (`claude` in a terminal: Terminal on macOS, Git Bash or PowerShell on Windows). Everything here was built and tested there. It has not been tried in the Claude Desktop app or the IDE extensions. They read the same `~/.claude` folder, so it may work, but the hooks, the commit and push prompts, and the installer's checks are unverified there.

## What is inside `payload/`

| Folder | Contents |
|---|---|
| `agents/` | `personal-advisor`, `-architect`, `-designer`, `-developer`, `-qa`, `-reviewer`, `-tester`, plus `security-secret-scanner` (reviews outgoing commits when the push guard blocks) |
| `skills/` | Team skills `personal-dev-team`, `personal-review-method`, `personal-security-audit`, `correct` (moves a repeated agent mistake into a hook or check), `interrogate` (adversarial review where only proven findings survive), plus the role skills the agents load: `brainstorming`, `ui-ux-pro-max` |
| `hooks/` | `agent-memory-only` (keeps read-only agents out of project files), `commit-ask-guard` (asks before any commit, shows the message and files), `run-python.sh` (finds Python 3 on any OS), `gitnexus-reindex.sh` (reindexes a repo without leaving a `.gitignore` change), `secret-scan/` (blocks `git push`, `gh repo create --push`, `gh pr create` and repo-writing `gh api` calls until the outgoing commits are scanned for secrets and personal information and approved by `security-secret-scanner`; see [Personal information check](#personal-information-check)) |
| `bin/` | `worktree-fingerprint.sh` (proves a read-only agent changed nothing) |
| `Preferences.md` | Global rules the agents refer to (`Preferences.md > Git`, `> Safety`) |

`Preferences.md > Git` also sets the commit message format: `<type>: <emoji> <short lowercase subject>` (feat 🎸, fix 🐛, docs ✏️, style 💄, refactor 💡, perf ⚡️, test 💍, chore 🤖, ci 🎡, release 🏹), a short body, then the `Co-Authored-By` trailer. It is a personal preference, not a requirement. To use another format, edit that one rule; the PM skill only points to it.

Installed by `install.sh` only when the tool is already present (see [rtk and GitNexus](#rtk-and-gitnexus)): the rtk hook and `RTK.md`, and the GitNexus MCP server.

Not included, install separately: Claude in Chrome, the Figma plugin, and built-in skills such as `dataviz` and `artifact-design`.

The agents also use the role skills `debug-mantra`, `scrutinize` and `motion` when they are installed. Their sources publish no license that allows redistribution, so they are not bundled; install them from the sources listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). The agents work without them.

## Language exception

My usual rule is that everything committed to git is written in English. This repo is an exception: it mirrors my live `~/.claude` setup byte for byte, so a few files keep their Thai text. These are `Preferences.md` (my rules, written in Thai), the Thai approval prompt in `hooks/commit-ask-guard.*`, the Thai trigger phrases in `skills/personal-security-audit`, `skills/correct` and `skills/interrogate` (plus a Thai heading name that `correct` cites from `Preferences.md`), and the Thai report template in `agents/security-secret-scanner.md`. Commit messages and this README stay in English.

## Install on Windows

Requirements: Claude Code, Git for Windows (Git Bash) and Python 3.8+ (`winget install Python.Python.3.12`).

Optional, install before running `install.sh` so it can set them up: rtk (`winget install rtk-ai.rtk`) and GitNexus (Node.js 22.18+, then `npm install -g gitnexus`).

```bash
# in Git Bash
git clone <this repo> ~/claude-personal-team
cd ~/claude-personal-team
bash install.sh
```

The installer backs up anything it replaces to `~/.claude/backups/personal-team-<timestamp>/`, copies the files, adds `@Preferences.md` to `~/.claude/CLAUDE.md`, registers the commit guard in `~/.claude/settings.json`, then runs a self-test of every hook. If rtk is installed it runs `rtk init -g`; if GitNexus is installed it registers the GitNexus MCP server at user scope. Re-running it is safe.

Then restart Claude Code. Optionally install `project-docs-kit` (see [project-docs-kit (optional)](#project-docs-kit-optional)).

## Install on macOS (another Mac)

Requirements: Claude Code, git and Python 3.8+. Both come with the Xcode Command Line Tools (`xcode-select --install`); `brew install python@3.12` also works.

Optional, install before running `install.sh`: rtk (`brew install rtk`) and GitNexus (Node.js 22.18+, then `npm install -g gitnexus`).

```bash
# in Terminal
git clone <this repo> ~/claude-personal-team
cd ~/claude-personal-team
bash install.sh
```

It does the same steps as on Windows. macOS ships bash 3.2, and the installer and hooks are tested with it.

Do not run `install.sh` on the source Mac, the one where you edit `~/.claude` and run `export-from-mac.sh`. It would replace your live files and skill symlinks with the exported copies. `export-from-mac.sh` creates `~/.claude/.personal-team-source`, and `install.sh` stops when that file exists. Pass `--force` only if you really mean to install there.

## Update

The Mac is the source of truth.

1. On the Mac, edit files in `~/.claude`, then run `bash export-from-mac.sh` and commit.
2. On Windows or another Mac, `git pull` and `bash install.sh`.

## Windows notes

- Claude Code runs hooks in Git Bash on Windows, so the `.sh` hooks work as on macOS. `.gitattributes` keeps LF line endings, because CRLF breaks bash scripts.
- On Windows Claude Code may run commands through its PowerShell tool instead of Bash. The commit guard therefore matches `Bash|PowerShell`.
- Hook paths arrive as `C:\...`. `agent-memory-only.py` normalises them and compares case-insensitively.
- If Python is missing, the hooks fail safe: read-only agents cannot write, commit-like commands always ask, and push-like commands are denied.
- Without `rtk` (usual on Windows), `security-secret-scanner` uses plain `git` for raw output.

## Personal information check

The push guard also blocks personal information, in every repo, public or private:

- Built in: your home path (`/Users/<you>`, `/home/<you>`, `C:\Users\<you>`) and your global `git config user.email`, unless it is a GitHub noreply address.
- Your own list in `~/.claude/secret-scan-private-terms.txt`: your employer, private project names, your real email. `install.sh` creates it once from `hooks/secret-scan/private-terms.example.txt` and never overwrites it. It stays outside every repo, so the names in it are never published. The template has examples only, so until you fill it in, the guard checks just your home path and email.

One regular expression per line, case-insensitive. Add `;; allow-remote=<text>,<text>` to allow a term in repos whose every remote URL contains one of those texts, for example your employer's name inside your employer's own repos:

```
ExampleCorp ;; allow-remote=github.com/examplecorp/,github.com:examplecorp/
you@example\.com
```

The check runs only on pushes Claude runs (it is a Claude Code hook); a `git push` you type in a terminal is not checked. A match blocks the push the same way a secret does. `security-secret-scanner` also reads the diff for what a list cannot catch, such as other people's names and dated stories about past incidents. To push anyway, check the finding and use `SECRET_SCAN_ACK=1` as for any other false positive.

## How the team learns (memory)

Each `personal-*` agent has `memory: user` in its frontmatter, so it keeps its own folder at `~/.claude/agent-memory/<agent>/`:

| File | Holds |
|---|---|
| `MEMORY.md` | Index of the other files, read first |
| `general.md` | Lessons that hold in any project |
| `<project-folder>.md` | Lessons for one project, for example `my-app.md` |

**The loop**

1. Before work, the agent reads `MEMORY.md` and the file for the current project. A memory that names a file, function or command is checked against the code before the agent relies on it.
2. During work, it saves what is worth keeping, and each role saves something different:
   - Developer: findings sent back on its work, and setup or build steps that took effort to work out.
   - Reviewer: defect patterns seen more than once, and false alarms you rejected (so it does not raise them again).
   - QA: how to start the app and reach each screen, and checks it could not run.
   - Architect and designer: your decisions, rejections and visual choices.
3. Agents never save what the repo already records (`AGENTS.md`, specs, git history), one-off task state, secrets or personal data. Read-only agents can write only inside their memory folder; the `agent-memory-only` hook enforces it.
4. Every handoff ends with a `Memory:` line. The PM lists these in its final Thai report.
5. A lesson that proves true in more than one run gets promoted. The PM proposes moving it into the agent file as a rule, applies it only on your yes, then removes it from memory. If the same mistake still comes back, the `correct` skill turns it into a hook or check.

**What you do**

- Correct an agent in plain words when it gets something wrong. The correction lands in memory, and after it repeats, in a rule.
- Answer the PM's promotion proposals at the end of a run.
- Now and then, read `~/.claude/agent-memory/<agent>/general.md` and delete anything outdated.

**Memory is per machine.** This repo does not copy `agent-memory/`, so on a new machine each agent starts empty. Lessons reach other machines only after they are promoted into an agent file and exported. That is the reason step 5 matters.

## Status line (optional, ask first)

This repo does not install a status line. When an AI agent sets up this repo on a new machine, it should **ask the user once**: "Do you want a Claude Code status line that shows the model, context usage and plan quota?" Do it only on a yes.

If the answer is yes:

- If `~/.claude/settings.json` already has a `statusLine`, show it to the user and ask before replacing it.
- Write a script `~/.claude/statusline.sh` that reads the JSON Claude Code sends on stdin and prints one line:
  - `model.display_name`
  - `context_window.used_percentage`, as % of context used
  - `rate_limits.five_hour` and `rate_limits.seven_day` (`used_percentage`, `resets_at`): plan quota with a countdown to reset. Only Pro/Max plans send these.
  - `cost.total_cost_usd` when there is no `rate_limits` (API-key billing)
  - colour each percentage: green below 50, yellow from 50, red from 80
- Make it portable. Git Bash on Windows has no `jq`, so put the parsing and formatting in `~/.claude/statusline.py`, and have `statusline.sh` run it with `bash "$HOME/.claude/hooks/run-python.sh" "$HOME/.claude/statusline.py"` (stdin passes through). Use `$HOME`, never a hard-coded user path.
- Register it as `{"type": "command", "command": "bash \"$HOME/.claude/statusline.sh\""}` under `statusLine`. Then test it by piping a sample JSON into the script before telling the user to restart.

Why it helps with this team: a PM run with many dispatches fills the context quickly, and reviewer, QA and advisor rounds use quota. Seeing both lets you start a fresh session or hold a big run before you hit a limit.

## rtk and GitNexus

Both are optional. The team works without them; with them it uses fewer tokens (rtk) and finds callers faster (GitNexus).

### rtk (token-saving command proxy)

**What it does.** A `PreToolUse` hook (`rtk hook claude`) rewrites shell commands such as `git status` into `rtk git status`, which returns shorter output. `RTK.md`, imported from `CLAUDE.md`, tells Claude how it works. It applies to every session and every agent; you do not call it.

**Day to day**

- Nothing to do. Check the savings now and then with `rtk gain` (`rtk gain --history` per command).
- `rtk discover` lists commands from your Claude Code history that were not rewritten and could be.
- If the output of a command looks wrong or incomplete, rerun it as `rtk proxy <command>` to see the raw output.

**Pitfalls**

- Do not trust rtk output that is piped or redirected. The filtered text can hide matches (`| grep` finds 0 hits) or write the wrong content to a file. Use `rtk proxy <command>`, or a command that answers directly, for example `git grep -n "<pattern>" <branch> -- <path>` instead of `git show <branch>:<file> | grep`. See `Preferences.md > Verification`.
- If `rtk gain` says "command not found", the wrong crate named `rtk` is installed. Remove it and install rtk-ai/rtk.
- The hook only matches the Bash tool. Commands run through the Windows PowerShell tool are not rewritten, which is harmless.

### GitNexus (code knowledge graph over MCP)

**What it does.** `gitnexus analyze` builds a graph of a repo's symbols, calls and routes. The MCP server (`gitnexus mcp`) serves every indexed repo to Claude.

**How the team uses it.** Only when the project is indexed; otherwise everyone uses Grep and Read as usual.

| Who | Uses it to |
|---|---|
| PM (`personal-dev-team`) | Run `gitnexus status` before the first dispatch. A stale index is reindexed in the background; an unindexed project gets one offer to index it, and is indexed only on your yes. |
| `personal-architect` | Run `impact` / `api_impact` on what will change, before designing |
| `personal-developer` | Run `impact` before changing a shared symbol, and `query` / `context` to find existing patterns |
| `personal-reviewer` | Run `detect_changes` on the diff and `impact` on changed symbols, to find callers the diff does not touch |
| `personal-advisor` | Trace a flow with `query` / `context`, and size a recommendation with `impact` |

Every agent treats a GitNexus result as a hint: it confirms by reading the file and cites `file_path:line_number`. Agents never run `gitnexus analyze` themselves.

**Day to day**

- Index a project once: `bash ~/.claude/hooks/gitnexus-reindex.sh <repo-path>` (add `--force` for a full rebuild). Log: `/tmp/gitnexus-<repo>.log`. The wrapper always passes `--skip-agents-md`, and it undoes the `.gitnexus` line that `gitnexus analyze` appends to a tracked `.gitignore`.
- `gitnexus list` shows the indexed repos. `gitnexus status`, run inside a repo, shows whether its index is stale.
- In a normal session you can ask directly, for example "use GitNexus to find everything that calls `placeOrder`".
- Useful MCP tools:
  - `query` finds the code for a concept.
  - `context` shows the callers and callees of a symbol.
  - `impact` shows the blast radius before a change.
  - `detect_changes` shows what a diff touches.
  - `route_map` and `api_impact` show web routes and API consumers.

**Pitfalls**

- Run `gitnexus analyze` through the wrapper, not directly. Run directly, it also adds or updates a GitNexus section in the repo's `AGENTS.md` and `CLAUDE.md`.
- Even through the wrapper, `analyze` writes two untracked folders into the repo: `.gitnexus/` (the index) and `.claude/skills/gitnexus/` (six GitNexus skills). Keep them out of commits by adding them to the repo's `.git/info/exclude`, once per repo, before the first index. That file is never committed, so the repo's `.gitignore` stays untouched, and it covers every worktree of the repo:

  ```bash
  cd <repo-path>
  exclude="$(git rev-parse --git-path info/exclude)"   # also correct inside a worktree
  grep -qx '.gitnexus/' "$exclude" || printf '.gitnexus/\n.claude/skills/gitnexus/\n' >> "$exclude"
  ```

  Check `git status` after the first index.
- GitNexus is licensed PolyForm Noncommercial 1.0.0. Read its terms for your use.

## project-docs-kit (optional)

[project-docs-kit](https://github.com/DPatta/project-docs-kit) (`project-kickoff` / `project-adopt`) is optional. The team works without it, keeping its specs and checklists in `docs/specs/` ("team docs" mode).

It suits personal projects that one person works on. It does not suit projects where several people work in the same repo: its task status, numbering and approvals are written for a single owner, so parallel branches collide. Do not use it there.

Install it only on a machine where you start solo personal projects: `/plugin marketplace add DPatta/project-docs-kit`, then `/plugin install project-docs-kit@project-docs-kit`. When a project has its `project-docs` skill, the team switches to "docs-kit" mode by itself.

### How to use it with the team

**1. Set up the project once.**

- New, empty folder: run `/project-docs-kit:project-kickoff`, or ask "set up the project docs". It asks a few questions, then writes `AGENTS.md`, `docs/PROJECT.md`, `ROADMAP.md`, features, decisions, a task store and the project's own `project-docs` skill (`.claude/skills/project-docs/`).
- Existing code: run `/project-docs-kit:project-adopt`. It scans the repo, writes an evidence-backed `AGENTS.md`, adds `@AGENTS.md` to an existing `CLAUDE.md` / `GEMINI.md`, and can add the same task store, following the project's own conventions.
- Read the summary it shows before it writes, and check the list of files at the end that a `.gitignore` keeps out of commits. A global ignore of `.claude/`, `CLAUDE.md` or `docs/features/` hides kit files from git. Stage those with `git add -f` if you want them in the repo.

**2. Ask the team for work as usual**, for example "use the personal team to add X to <project>". The PM sees `.claude/skills/project-docs/SKILL.md` and works in docs-kit mode:

| Step | Who | What you do |
|---|---|---|
| New feature | Architect writes `docs/features/...` as `proposed` | Approve it and pick its phase when the PM asks. Nothing is built before that. |
| Tasks | Architect splits the approved feature into tasks in the task store | Nothing |
| Screens | Designer, only if `DESIGN.md` → Screens has no mockup yet | Approve the wireframe when the PM asks |
| Build | Developer, then reviewer, tester (when needed) and QA | Nothing, unless the PM stops with a question |
| Status | Only the PM moves a task `todo → in-progress → review → done`, with a `## Log` line naming the gate that passed | Nothing |
| Deferred findings | Become files in `docs/issues/` | Read them in the final report |
| Finish | The feature becomes `done` when all its tasks are `done` | Say "commit" when the PM reports it is ready. Code and docs go in the same commit. |

**3. Resume in a new session.** Ask the team to continue. The PM reads the `in-progress` and `review` tasks first; they outrank anything you remember from the old session.

**4. Keep the kit current.** Run `project-kickoff` again in a project set up by an older release, and it offers to upgrade the project's structure.

Without the kit, the same flow uses one checklist per feature in `docs/specs/<feature>-checklist.md` instead of feature and task files.

## Credits

- The `correct` and `interrogate` skills and some evidence rules (reproduce before fixing, evidence levels, inconclusive is not a pass, judging tests with two imagined edits, blast radius beyond callers) are adapted from [pstack](https://github.com/cursor/plugins/tree/main/pstack) by Lauren Tan, MIT License. Each adapted file names which parts come from pstack and which are our own. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the list and the license text.
- The `brainstorming` skill comes from [superpowers](https://github.com/obra/superpowers) by Jesse Vincent, and `ui-ux-pro-max` from [ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) by Next Level Builder, both MIT License.
- Everything else in this repo is our own work. That includes the team structure and the agents, the hooks and guards, the installer, and the money and market data checks.

## License

MIT, see [LICENSE](LICENSE). Bundled third-party parts keep their own licenses, listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
