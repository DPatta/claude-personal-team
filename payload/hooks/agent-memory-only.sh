#!/usr/bin/env bash
# PreToolUse hook for read-only agents that have `memory:` enabled.
# Claude Code adds Write/Edit to any agent with memory; this keeps those tools
# inside the agent's own memory directory: ~/.claude/agent-memory/<agent-name>/
#
# Usage (agent frontmatter):
#   hooks:
#     PreToolUse:
#       - matcher: "Write|Edit"
#         hooks:
#           - type: command
#             command: "$HOME/.claude/hooks/agent-memory-only.sh <agent-name>"
#
# Exit 0 = allow, exit 2 = block (stderr is shown to the agent).
# Fails closed: a parse error, a missing path or a missing Python blocks the call.
# The logic lives in agent-memory-only.py (stdin, so large Write payloads are fine on Windows).

hook_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$hook_directory/run-python.sh" "$hook_directory/agent-memory-only.py" "$1"
status=$?
if [ "$status" -eq 0 ]; then
  exit 0
fi
if [ "$status" -ne 2 ]; then
  echo "agent-memory-only: blocked, the check could not run (exit $status)" >&2
fi
exit 2
