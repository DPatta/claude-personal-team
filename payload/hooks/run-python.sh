#!/usr/bin/env bash
# Run a Python 3 hook script portably (macOS, Linux, Windows Git Bash).
# Usage: run-python.sh <script.py> [args...]   (stdin is passed through)
# Tries python3, python, then the Windows launcher `py -3`, skipping the Windows Store
# stub that answers to `python` without being a real interpreter.
# Exit 127 if no Python 3 is found; the caller decides whether that blocks or asks.

script="$1"
shift

for candidate in "python3" "python" "py -3"; do
  # shellcheck disable=SC2086
  if $candidate -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' >/dev/null 2>&1; then
    # shellcheck disable=SC2086
    exec $candidate -I "$script" "$@"
  fi
done

echo "run-python: no Python 3.8+ found (tried python3, python, py -3)" >&2
exit 127
