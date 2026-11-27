#!/bin/bash
# Print one hash covering every tracked and untracked (non-ignored) file in the
# current git working tree, including the content of untracked files.
# Uses a throwaway copy of the index, so the real index and staging are untouched.
# Usage: run inside the repo, before and after a read-only agent; compare the two hashes.
set -euo pipefail
git_index="$(git rev-parse --git-path index)"
temporary_index="$(mktemp)"
trap 'rm -f "$temporary_index"' EXIT
if [ -f "$git_index" ]; then cp "$git_index" "$temporary_index"; else rm -f "$temporary_index"; fi
GIT_INDEX_FILE="$temporary_index" git add -A
GIT_INDEX_FILE="$temporary_index" git write-tree
