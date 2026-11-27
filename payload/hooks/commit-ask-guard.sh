#!/usr/bin/env bash
# PreToolUse hook (matcher: Bash|PowerShell): ask before any command that creates a git commit.
# Runs commit-ask-guard.py; if Python is missing or the check fails, it still asks when the
# command looks like a commit, so a broken setup never lets a commit through silently.

hook_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
hook_input="$(cat)"
output="$(printf '%s' "$hook_input" | bash "$hook_directory/run-python.sh" "$hook_directory/commit-ask-guard.py")"
status=$?
if [ "$status" -eq 0 ]; then
  printf '%s' "$output"
  exit 0
fi
# Look only at tool_input.command (not cwd or other fields), without needing Python.
command_text="$(printf '%s' "$hook_input" | tr '\n' ' ' | sed -En 's/.*"command"[[:space:]]*:[[:space:]]*"(([^"\\]|\\.)*)".*/\1/p')"
if printf '%s' "$command_text" | grep -Eq '(^|[^[:alnum:]_-])git([^[:alnum:]_-].*)?(commit|merge|cherry-pick|revert)'; then
  printf '%s' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"🔶 ขออนุญาต GIT COMMIT 🔶\n(ตัวตรวจ commit รันไม่ได้ — ตรวจคำสั่งเองก่อน)\n\nกด Yes เฉพาะเมื่อคุณสั่งให้ commit"}}'
fi
exit 0
