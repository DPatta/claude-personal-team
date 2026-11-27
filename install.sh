#!/usr/bin/env bash
# Install the personal-team setup into ~/.claude.
# Windows: run in Git Bash (bash install.sh). macOS: run in Terminal (bash install.sh). Also works on Linux.
# Safe to re-run: files it would overwrite are backed up first.
# Never run it on the source Mac (the one that runs export-from-mac.sh): it would replace live files with the exported copies.
set -uo pipefail

repository="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
payload="$repository/payload"
claude_directory="$HOME/.claude"
timestamp="$(date +%Y%m%d-%H%M%S)"
backup="$claude_directory/backups/personal-team-$timestamp"
failures=0
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) operating_system=windows ;;
  Darwin) operating_system=macos ;;
  *) operating_system=linux ;;
esac

say() { printf '%s\n' "$*"; }
pass() { say "  PASS  $*"; }
fail() { say "  FAIL  $*"; failures=$((failures + 1)); }

say "== 1. Checks"
if grep -qi microsoft /proc/version 2>/dev/null; then
  say "  STOP  This is WSL, not Git Bash. It would install into the Linux home, which Claude Code for Windows does not read."
  say "        Open the \"Git Bash\" app from the Start menu and run: bash install.sh"
  exit 1
fi
if [ -e "$claude_directory/.personal-team-source" ] && [ "${1:-}" != "--force" ]; then
  say "  STOP  This is the source Mac: ~/.claude/.personal-team-source exists (export-from-mac.sh creates it)."
  say "        Installing here would replace your live files (and skill symlinks) with the exported copies."
  say "        To publish changes from this Mac, run: bash export-from-mac.sh   then commit."
  say "        If you really mean to install here, run: bash install.sh --force"
  exit 1
fi
say "  OS = $operating_system"
case "$operating_system" in
  windows) git_hint="install Git for Windows: winget install Git.Git" ;;
  macos) git_hint="install the Xcode Command Line Tools: xcode-select --install" ;;
  *) git_hint="install git with your package manager" ;;
esac
command -v git >/dev/null 2>&1 && pass "git found" || fail "git not found ($git_hint)"
python_command=""
for candidate in "python3" "python" "py -3"; do
  # shellcheck disable=SC2086
  if $candidate -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' >/dev/null 2>&1; then
    python_command="$candidate"; break
  fi
done
if [ -n "$python_command" ]; then
  pass "Python 3 found ($python_command)"
else
  case "$operating_system" in
    windows) fail "Python 3.8+ not found. Install it (winget install Python.Python.3.12), reopen Git Bash, re-run." ;;
    macos) fail "Python 3.8+ not found. Install it (xcode-select --install, or brew install python@3.12), reopen Terminal, re-run." ;;
    *) fail "Python 3.8+ not found. Install python3 with your package manager, then re-run." ;;
  esac
  say "        Without Python: reviewer/QA memory writes are blocked, and every commit-like command asks."
fi
say "  HOME = $HOME   (Claude Code dir: $claude_directory)"

say "== 2. Back up files that will be replaced → $backup"
mkdir -p "$backup"
while IFS= read -r relative; do
  if [ -e "$claude_directory/$relative" ]; then
    mkdir -p "$backup/$(dirname "$relative")"
    cp -R "$claude_directory/$relative" "$backup/$relative"
  fi
done < <(cd "$payload" && find . -mindepth 2 -maxdepth 2 | sed 's#^\./##'; echo Preferences.md; echo settings.json; echo CLAUDE.md; echo RTK.md)

say "== 3. Copy files"
mkdir -p "$claude_directory"/{agents,skills,hooks,bin}
cp "$payload"/agents/*.md "$claude_directory/agents/"
for skill in "$payload"/skills/*; do
  rm -rf "$claude_directory/skills/$(basename "$skill")"
  cp -R "$skill" "$claude_directory/skills/"
done
cp -R "$payload"/hooks/. "$claude_directory/hooks/"
cp "$payload"/bin/* "$claude_directory/bin/"
cp "$payload/Preferences.md" "$claude_directory/"
chmod +x "$claude_directory"/hooks/*.sh "$claude_directory"/hooks/secret-scan/*.sh "$claude_directory"/bin/*.sh 2>/dev/null
pass "copied $(find "$payload" -type f | wc -l | tr -d ' ') files"
private_terms_file="$claude_directory/secret-scan-private-terms.txt"
if [ -f "$private_terms_file" ]; then
  pass "private terms file kept: $private_terms_file"
else
  cp "$claude_directory/hooks/secret-scan/private-terms.example.txt" "$private_terms_file"
  say "  TODO  fill in $private_terms_file (employer, private project names, your email); see the comments in it"
fi

say "== 4. CLAUDE.md imports Preferences.md"
touch "$claude_directory/CLAUDE.md"
if grep -qx '@Preferences.md' "$claude_directory/CLAUDE.md"; then
  pass "already imported"
else
  printf '\n@Preferences.md\n' >> "$claude_directory/CLAUDE.md"
  pass "added @Preferences.md"
fi

say "== 5. settings.json: commit guard, secret-scan push guard, auto-compact at 40%"
if [ -n "$python_command" ]; then
  # shellcheck disable=SC2086
  $python_command - "$claude_directory/settings.json" <<'PYTHON'
import json, os, sys
path = sys.argv[1]
settings = json.load(open(path, encoding="utf-8")) if os.path.exists(path) and os.path.getsize(path) else {}
wanted = [
    # (marker that identifies an existing entry, command, timeout)
    ("commit-ask-guard", 'bash "$HOME/.claude/hooks/commit-ask-guard.sh"', 10),
    ("pre_push_guard|pre-push-guard", 'bash "$HOME/.claude/hooks/secret-scan/pre-push-guard.sh"', 120),
]
entries = settings.setdefault("hooks", {}).setdefault("PreToolUse", [])
for marker, command, timeout in wanted:
    markers = marker.split("|")
    existing = None
    for entry in entries:
        for hook in entry.get("hooks", []):
            if any(name in hook.get("command", "") for name in markers):
                existing = (entry, hook)
    if existing:
        entry, hook = existing
        hook["command"] = command
        hook["timeout"] = timeout
        entry["matcher"] = "Bash|PowerShell"
    else:
        entries.append({"matcher": "Bash|PowerShell", "hooks": [{"type": "command", "command": command, "timeout": timeout}]})
    print(f"  PASS  {markers[0]} registered in settings.json")
# Compact earlier than the default so long sessions keep room to work. Never overwrite a value the user set.
environment = settings.setdefault("env", {})
if "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE" in environment:
    print(f"  PASS  CLAUDE_AUTOCOMPACT_PCT_OVERRIDE already set to {environment['CLAUDE_AUTOCOMPACT_PCT_OVERRIDE']}, left as is")
else:
    environment["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"] = "40"
    print("  PASS  CLAUDE_AUTOCOMPACT_PCT_OVERRIDE set to 40")
with open(path, "w", encoding="utf-8") as handle:
    json.dump(settings, handle, indent=2, ensure_ascii=False)
    handle.write("\n")
PYTHON
else
  fail "skipped (needs Python). Add these to ~/.claude/settings.json → hooks.PreToolUse by hand:"
  say '        {"matcher":"Bash|PowerShell","hooks":[{"type":"command","command":"bash \"$HOME/.claude/hooks/commit-ask-guard.sh\"","timeout":10}]}'
  say '        {"matcher":"Bash|PowerShell","hooks":[{"type":"command","command":"bash \"$HOME/.claude/hooks/secret-scan/pre-push-guard.sh\"","timeout":120}]}'
  say '      and under "env": "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "40"'
fi

say "== 6. Self-test (runs the hooks exactly as Claude Code will)"
memory_file="$claude_directory/agent-memory/personal-reviewer/notes.md"
project_file="$repository/README.md"
memory_check() {
  printf '{"tool_name":"Write","cwd":"%s","tool_input":{"file_path":"%s","content":"x"}}' "$repository" "$1" \
    | bash -c '"$HOME/.claude/hooks/agent-memory-only.sh" personal-reviewer' >/dev/null 2>&1
  echo $?
}
[ "$(memory_check "$memory_file")" = "0" ] && pass "reviewer may write its memory" || fail "reviewer memory write was blocked"
[ "$(memory_check "$project_file")" = "2" ] && pass "reviewer may not write project files" || fail "reviewer project write was NOT blocked"
if command -v cygpath >/dev/null 2>&1; then
  windows_memory_file="$(cygpath -w "$memory_file")"
  [ "$(memory_check "${windows_memory_file//\\/\\\\}")" = "0" ] && pass "Windows-style path (C:\\...) accepted" || fail "Windows-style memory path was blocked"
fi
guard_output="$(printf '{"tool_name":"Bash","cwd":"%s","tool_input":{"command":"git commit -m \\"test: x\\""}}' "$repository" \
  | bash -c 'bash "$HOME/.claude/hooks/commit-ask-guard.sh"')"
case "$guard_output" in
  *'"ask"'*) pass "commit asks for approval" ;;
  *) fail "commit guard did not ask (output: ${guard_output:-empty})" ;;
esac
status_output="$(printf '{"tool_name":"Bash","cwd":"%s","tool_input":{"command":"git status"}}' "$repository" \
  | bash -c 'bash "$HOME/.claude/hooks/commit-ask-guard.sh"')"
[ -z "$status_output" ] && pass "git status does not ask" || fail "git status asked"
push_repository="$(mktemp -d)"
(cd "$push_repository" && git init -q && echo x > a.txt && git add a.txt \
  && git -c user.name=test -c user.email=test@example.invalid commit -q -m test)
push_output="$(printf '{"tool_name":"Bash","cwd":"%s","tool_input":{"command":"git push origin HEAD"}}' "$push_repository" \
  | bash -c 'bash "$HOME/.claude/hooks/secret-scan/pre-push-guard.sh"')"
combined_output="$(printf '{"tool_name":"Bash","cwd":"%s","tool_input":{"command":"git commit -m x && git push origin HEAD"}}' "$push_repository" \
  | bash -c 'bash "$HOME/.claude/hooks/secret-scan/pre-push-guard.sh"')"
test_terms_file="$(mktemp)"
printf 'ExampleCorp ;; allow-remote=github.com/examplecorp/\n' > "$test_terms_file"
(cd "$push_repository" && echo "we work at ExampleCorp" > b.txt && git add b.txt \
  && git -c user.name=test -c user.email=test@example.invalid commit -q -m term)
term_output="$(printf '{"tool_name":"Bash","cwd":"%s","tool_input":{"command":"git push origin HEAD"}}' "$push_repository" \
  | SECRET_SCAN_PRIVATE_TERMS="$test_terms_file" bash -c 'bash "$HOME/.claude/hooks/secret-scan/pre-push-guard.sh"')"
(cd "$push_repository" && git remote add origin https://github.com/examplecorp/app.git)
allowed_output="$(cd "$push_repository" && SECRET_SCAN_PRIVATE_TERMS="$test_terms_file" bash "$HOME/.claude/hooks/run-python.sh" "$HOME/.claude/hooks/secret-scan/pre_push_guard.py" scan --repo . --ref HEAD 2>&1)"
rm -rf "$push_repository" "$test_terms_file"
case "$push_output" in
  *'"deny"'*'NOT YET REVIEWED'*) pass "push is blocked until security-secret-scanner reviews it" ;;
  *) fail "push guard did not block an unreviewed push (output: ${push_output:-empty})" ;;
esac
case "$combined_output" in
  *'"deny"'*'both creates commits'*) pass "commit and push in one command is blocked" ;;
  *) fail "push guard allowed commit and push in one command (output: ${combined_output:-empty})" ;;
esac
case "$term_output" in
  *'"deny"'*'private-term'*) pass "a private term blocks the push" ;;
  *) fail "push guard did not flag a private term (output: ${term_output:-empty})" ;;
esac
case "$allowed_output" in
  *'deterministic findings: 0'*) pass "a private term is allowed in its allow-remote repo" ;;
  *) fail "allow-remote did not allow the term (output: ${allowed_output:-empty})" ;;
esac
audit_repository="$(mktemp -d)"
(cd "$audit_repository" && git init -q && printf 'token=%s%s\n' 'AKIA' 'ABCDEFGHIJKLMNOP' > config.txt && git add config.txt \
  && git -c user.name=test -c user.email=test@example.invalid commit -q -m key \
  && echo 'token=$AWS_KEY' > config.txt && git -c user.name=test -c user.email=test@example.invalid commit -q -am removed)
audit_output="$(bash "$HOME/.claude/hooks/run-python.sh" "$HOME/.claude/hooks/secret-scan/pre_push_guard.py" audit --repo "$audit_repository" 2>&1)"
rm -rf "$audit_repository"
case "$audit_output" in
  *'In the current files (HEAD): 0'*'Only in history'*'aws-access-key-id'*'local only'*) pass "audit finds a key removed from the files but left in history" ;;
  *) fail "audit missed a key left in history (output: ${audit_output:-empty})" ;;
esac
test_repository="$(mktemp -d)"
before="$(cd "$test_repository" && git init -q && echo one > a.txt && bash "$claude_directory/bin/worktree-fingerprint.sh" 2>/dev/null)"
after="$(cd "$test_repository" && echo two > b.txt && bash "$claude_directory/bin/worktree-fingerprint.sh" 2>/dev/null)"
rm -rf "$test_repository"
if [ -n "$before" ] && [ -n "$after" ] && [ "$before" != "$after" ]; then
  pass "worktree-fingerprint detects a new untracked file"
else
  fail "worktree-fingerprint failed (before='$before' after='$after')"
fi

say "== 7. Optional tools: rtk and GitNexus (skipped if not installed; never counted as failures)"
if command -v rtk >/dev/null 2>&1 && rtk gain >/dev/null 2>&1; then
  # rtk writes RTK.md, adds @RTK.md to CLAUDE.md and registers `rtk hook claude` (Bash matcher).
  if rtk init -g --auto-patch >/dev/null 2>&1; then
    pass "rtk $(rtk --version 2>/dev/null | awk '{print $2}') hook and RTK.md installed (rtk init -g)"
  else
    say "  WARN  rtk init -g failed. Run it by hand: rtk init -g --auto-patch"
  fi
elif command -v rtk >/dev/null 2>&1; then
  say "  WARN  an rtk is on PATH but 'rtk gain' fails: it is probably the other crate named rtk. Remove it and install rtk-ai/rtk."
else
  case "$operating_system" in
    windows) rtk_hint="winget install rtk-ai.rtk" ;;
    macos) rtk_hint="brew install rtk" ;;
    *) rtk_hint="see https://github.com/rtk-ai/rtk#installation" ;;
  esac
  say "  SKIP  rtk not installed. Install: $rtk_hint   then re-run install.sh"
fi
if command -v gitnexus >/dev/null 2>&1; then
  if ! command -v claude >/dev/null 2>&1; then
    say "  SKIP  gitnexus found but the claude CLI is not on PATH. Register it by hand: claude mcp add --scope user gitnexus -- gitnexus mcp"
  elif claude mcp get gitnexus >/dev/null 2>&1; then
    pass "GitNexus MCP already registered"
  else
    if [ "$operating_system" = windows ]; then
      # npm installs gitnexus as a .cmd shim on Windows; stdio MCP servers need cmd /c to start it.
      # MSYS_NO_PATHCONV stops Git Bash from rewriting "/c" into "C:/".
      MSYS_NO_PATHCONV=1 claude mcp add --scope user gitnexus -- cmd /c gitnexus mcp >/dev/null 2>&1
    else
      claude mcp add --scope user gitnexus -- "$(command -v gitnexus)" mcp >/dev/null 2>&1
    fi
    claude mcp get gitnexus >/dev/null 2>&1 && pass "GitNexus MCP registered (user scope)" \
      || say "  WARN  could not register GitNexus MCP. Run: claude mcp add --scope user gitnexus -- gitnexus mcp"
  fi
else
  say "  SKIP  GitNexus not installed. Needs Node.js 22.18+: npm install -g gitnexus   then re-run install.sh"
fi

say ""
if [ "$failures" -eq 0 ]; then
  say "Done. All checks passed. Backup: $backup"
else
  say "Done with $failures problem(s) above. Backup: $backup"
fi
say "Next, inside Claude Code on this machine:"
say "  1. Install the Claude in Chrome extension (QA uses it) and the Figma plugin if you design here."
say "  2. Restart Claude Code, then run /agents to see the personal-* agents."
say "  Optional: ask Claude to set up a status line (README > Status line). It asks you first."
say "  Optional, for solo personal projects only: /plugin marketplace add DPatta/project-docs-kit   then   /plugin install project-docs-kit@project-docs-kit"
exit "$failures"
