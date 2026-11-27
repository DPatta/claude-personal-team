#!/usr/bin/env bash
# PreToolUse hook (matcher: Bash|PowerShell): secret scan before any push.
# Runs pre_push_guard.py through run-python.sh. If the scan cannot run (no Python, crash),
# it fails closed: a command that looks like a push is denied with the reason.

guard_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
hook_input="$(cat)"
output="$(printf '%s' "$hook_input" | bash "$guard_directory/../run-python.sh" "$guard_directory/pre_push_guard.py")"
status=$?
if [ "$status" -eq 0 ]; then
  printf '%s' "$output"
  exit 0
fi
# Look only at tool_input.command (not cwd or other fields), without needing Python.
command_text="$(printf '%s' "$hook_input" | tr '\n' ' ' | sed -En 's/.*"command"[[:space:]]*:[[:space:]]*"(([^"\\]|\\.)*)".*/\1/p')"
if printf '%s' "$command_text" | grep -Eq '(^|[^[:alnum:]_-])(git|gh)([^[:alnum:]_-].*)?(push|pr create|repo create|api)'; then
  printf '%s' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"[secret-scan] Push blocked: the secret scan could not run (exit '"$status"'; is Python 3 installed?). Tell the user. Fix the scan, then retry."}}'
fi
exit 0
