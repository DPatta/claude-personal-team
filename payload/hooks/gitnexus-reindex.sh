#!/bin/sh
# Reindex one repo with GitNexus, then undo the `.gitnexus` line that
# `gitnexus analyze` always appends to the tracked .gitignore (the repos
# already ignore .gitnexus via .git/info/exclude). Any other .gitignore
# change is left alone. --skip-agents-md is always passed, so analyze never
# adds or updates a GitNexus section in the repo's AGENTS.md or CLAUDE.md.
# Usage: gitnexus-reindex.sh <repo-path> [analyze args, e.g. --force]
#        (log: /tmp/gitnexus-<repo>.log)

repo="$1"
shift
cd "$repo" || exit 0
log="/tmp/gitnexus-$(basename "$repo").log"

snap=$(mktemp)
had_gitignore=0
if [ -f .gitignore ]; then
  cp .gitignore "$snap"
  had_gitignore=1
fi

gitnexus analyze --skip-agents-md "$@" >"$log" 2>&1

if [ "$had_gitignore" = 1 ]; then
  expected="$(cat "$snap")
.gitnexus"
  if [ "$(cat .gitignore)" = "$expected" ]; then
    cp "$snap" .gitignore
    echo "[gitnexus-reindex] restored .gitignore" >>"$log"
  fi
elif [ "$(cat .gitignore 2>/dev/null)" = ".gitnexus" ]; then
  rm -f .gitignore
  echo "[gitnexus-reindex] removed .gitignore created by gitnexus" >>"$log"
fi
rm -f "$snap"
