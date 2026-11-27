#!/usr/bin/env bash
# Copy the current personal-team setup from this Mac's ~/.claude into payload/.
# The Mac is the source of truth: edit files in ~/.claude, run this, then commit.
set -euo pipefail

repository="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_directory="$HOME/.claude"
payload="$repository/payload"

# Marks this Mac as the source, so install.sh refuses to overwrite it.
touch "$source_directory/.personal-team-source"

agents=(personal-advisor personal-architect personal-designer personal-developer personal-qa personal-reviewer personal-tester security-secret-scanner)
skills=(personal-dev-team personal-review-method personal-security-audit correct interrogate brainstorming ui-ux-pro-max)
hooks=(agent-memory-only.sh agent-memory-only.py run-python.sh commit-ask-guard.sh commit-ask-guard.py gitnexus-reindex.sh)
binaries=(worktree-fingerprint.sh)

rm -rf "$payload"
mkdir -p "$payload/agents" "$payload/skills" "$payload/hooks" "$payload/bin"

for name in "${agents[@]}"; do cp "$source_directory/agents/$name.md" "$payload/agents/"; done
for name in "${skills[@]}"; do
  # -L follows symlinks so the copy holds real files
  cp -RL "$source_directory/skills/$name" "$payload/skills/"
done
for name in "${hooks[@]}"; do cp "$source_directory/hooks/$name" "$payload/hooks/"; done
mkdir -p "$payload/hooks/secret-scan"
cp "$source_directory/hooks/secret-scan/pre_push_guard.py" "$source_directory/hooks/secret-scan/pre-push-guard.sh" "$source_directory/hooks/secret-scan/private-terms.example.txt" "$payload/hooks/secret-scan/"
for name in "${binaries[@]}"; do cp "$source_directory/bin/$name" "$payload/bin/"; done
cp "$source_directory/Preferences.md" "$payload/"

find "$payload" \( -name '__pycache__' -o -name '.DS_Store' \) -prune -exec rm -rf {} +
# Private step, kept outside the repo: replaces employer names and dated history notes with
# neutral wording, and fails the export if any are left. The script lives only on the source Mac.
sanitizer="$source_directory/bin/sanitize-personal-team-payload.py"
if [ ! -f "$sanitizer" ]; then
  echo "STOP: $sanitizer is missing. Do not commit this export." >&2
  exit 1
fi
python3 "$sanitizer" "$payload"
echo "Exported to $payload:"
find "$payload" -type f | sed "s#$payload/##" | sort | awk -F/ '{print $1}' | uniq -c
