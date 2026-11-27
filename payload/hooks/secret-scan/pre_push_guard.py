#!/usr/bin/env python3
"""Secret scan guard for `git push` commands run by Claude Code.

Modes:
  (no arguments)                      PreToolUse hook; reads the hook JSON on stdin.
  scan    --repo DIR [--ref REF ...]  print unpushed commits, review key and findings.
  diff    --repo DIR [--ref REF ...]  print every added line of the unpushed commits.
  audit   --repo DIR [--limit N] [--since DATE]
                                      read-only audit of the whole repo: every tracked file at HEAD
                                      plus every commit in history (pushed or not), same rules.
  approve --repo DIR [--ref REF ...] --key KEY
                                      record the security agent's approval; refused
                                      when the deterministic scan still has findings
                                      or the key no longer matches the commits.

Besides secrets, the scan flags personal information in every repo: the user's home path
(/Users/<name>, /home/<name>, C:/Users/<name> (either slash)), the global git user.email, and the terms in
the private terms file (~/.claude/secret-scan-private-terms.txt, or SECRET_SCAN_PRIVATE_TERMS).
The terms file lives outside every repo. One regular expression per line, matched case-insensitively;
add `;; allow-remote=<text>,<text>` to allow a term in repos whose every remote URL contains one of
those texts (for example an employer name inside the employer's own repos).

Hook decisions:
  - deterministic findings            -> deny, ask Claude to dispatch the agent
  - clean but not yet agent-approved  -> deny, ask Claude to dispatch the agent
  - clean and approved                -> allow
  - command contains SECRET_SCAN_ACK=1 -> ask (the user approves in the prompt)
"""
import argparse
import getpass
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

STATE_DIRECTORY = Path.home() / ".claude" / "state" / "secret-scan" / "approved"
AGENT_NAME = "security-secret-scanner"
SCRIPT_PATH = Path(__file__).resolve()
ACKNOWLEDGE_TOKEN = "SECRET_SCAN_ACK=1"
INLINE_ALLOW_MARKER = "secret-scan: allow"
MAXIMUM_REPORTED_FINDINGS = 40
PRIVATE_TERMS_FILE = Path(os.path.expanduser(
    os.environ.get("SECRET_SCAN_PRIVATE_TERMS") or "~/.claude/secret-scan-private-terms.txt"))
ALLOW_REMOTE_SEPARATOR = ";;"
GENERIC_USER_NAMES = {"root", "user", "admin", "runner", "ubuntu", "vagrant", "shared", "public"}

SKIPPED_PATHS = re.compile(
    r"(^|/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|pubspec\.lock|Podfile\.lock|"
    r"Cargo\.lock|poetry\.lock|go\.sum|composer\.lock|bun\.lockb?|Gemfile\.lock)$"
)

# Files that are never read at all, filtered by git itself so their (often huge) lines never reach the regexes:
# lockfiles, SVG (often base64 images on one line), source maps and minified bundles.
EXCLUDED_PATHSPECS = [
    ":(exclude,glob)**/*.svg", ":(exclude,glob)**/*.map", ":(exclude,glob)**/*.min.js", ":(exclude,glob)**/*.min.css",
    ":(exclude,glob)**/package-lock.json", ":(exclude,glob)**/yarn.lock", ":(exclude,glob)**/pnpm-lock.yaml",
    ":(exclude,glob)**/*.lock", ":(exclude,glob)**/go.sum", ":(exclude,glob)**/bun.lockb",
]
# Lines longer than this are checked only with the fixed-prefix token rules, not the broad
# "name = value" rules, which are slow on long lines and noisy on generated content.
LONG_LINE_LENGTH = 4000
# Folders whose values are UI text or test ids, not credentials: the broad rules skip them.
BROAD_RULE_SKIPPED_PATHS = re.compile(r"(?i)(^|/)(test-?ids?|locales?|i18n|translations?|lang)/")

# (rule name, pattern, index of the group holding the value or 0 for the whole match, placeholder check)
# Rules with the placeholder check on are the "broad" rules.
CONTENT_RULES = [
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY( BLOCK)?-----"), 0, False),
    ("aws-access-key-id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), 0, False),
    ("aws-secret-access-key", re.compile(r"(?i)aws.{0,20}(?:secret|private).{0,20}?[\"'=:\s]([A-Za-z0-9/+=]{40})\b"), 1, False),
    ("github-token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})\b"), 0, False),
    ("gitlab-token", re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,}"), 0, False),
    ("slack-token", re.compile(r"\bxox[abposr]-[A-Za-z0-9\-]{10,}"), 0, False),
    ("slack-webhook", re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/_\-]{20,}"), 0, False),
    ("discord-webhook", re.compile(r"https://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w\-]+"), 0, False),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}"), 0, False),
    ("google-oauth-client-secret", re.compile(r"\bGOCSPX-[A-Za-z0-9_\-]{20,}"), 0, False),
    ("anthropic-api-key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}"), 0, False),
    ("openai-api-key", re.compile(r"\bsk-(?!ant-)(?:proj-|svcacct-|admin-)?[A-Za-z0-9_\-]{32,}"), 0, False),
    ("stripe-secret-key", re.compile(r"\b(?:sk|rk)_live_[0-9A-Za-z]{20,}"), 0, False),
    ("sendgrid-api-key", re.compile(r"\bSG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}"), 0, False),
    ("npm-token", re.compile(r"\bnpm_[A-Za-z0-9]{36}\b"), 0, False),
    ("npmrc-auth-token", re.compile(r"_authToken\s*=\s*([^\s$]{8,})"), 1, True),
    ("telegram-bot-token", re.compile(r"\b\d{8,10}:AA[A-Za-z0-9_\-]{33}\b"), 0, False),
    ("twilio-api-key", re.compile(r"\bSK[0-9a-fA-F]{32}\b"), 0, False),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"), 0, False),
    ("credential-in-url", re.compile(r"\b[a-z][a-z0-9+.\-]*://[^\s:/@'\"]+:([^\s@/'\"]{3,})@"), 1, True),
    (
        "generic-secret-assignment",
        re.compile(
            r"(?i)(?:password|passwd|pwd|secret|api[_\-]?key|apikey|access[_\-]?token|auth[_\-]?token|"
            r"refresh[_\-]?token|client[_\-]?secret|private[_\-]?key|signing[_\-]?key)[\w.\-]*[\"']?\s*[:=]\s*[\"']([^\"'\s]{8,})[\"']"
        ),
        1,
        True,
    ),
]

PLACEHOLDER_HINTS = (
    "${", "{{", "<", "process.env", "os.environ", "getenv", "env(", "example", "changeme", "change_me",
    "placeholder", "your", "xxxx", "****", "dummy", "sample", "redacted", "replace", "todo", "fake", "mock",
)

ENVIRONMENT_FILE = re.compile(r"(^|/)\.env(\.[\w.\-]+)?$")
ENVIRONMENT_TEMPLATE = re.compile(r"\.(example|sample|template|schema|defaults?|dist)$")
SENSITIVE_FILE_RULES = [
    ("private-key-file", re.compile(r"\.(pem|key|p12|pfx|jks|keystore|ppk)$")),
    ("ssh-key-file", re.compile(r"(^|/)id_(rsa|dsa|ecdsa|ed25519)$")),
    (
        "credentials-file",
        re.compile(
            r"(^|/)(credentials(\.json)?|service[-_]account[\w.\-]*\.json|client_secret[\w.\-]*\.json|"
            r"google-services\.json|GoogleService-Info\.plist|key\.properties|\.pypirc|\.netrc|"
            r"\.git-credentials|secrets?\.(ya?ml|json|toml))$"
        ),
    ),
]


# ---------------------------------------------------------------- git helpers

def run_git(repository, *arguments, check=True):
    completed = subprocess.run(
        ["git", "-C", str(repository), "-c", "core.quotePath=false", *arguments],
        capture_output=True,
        text=True,
        errors="replace",
    )
    if check and completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)} failed: {completed.stderr.strip()}")
    return completed


def repository_root(directory):
    completed = run_git(directory, "rev-parse", "--show-toplevel", check=False)
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def unpushed_commits(repository, references):
    output = run_git(repository, "rev-list", *references, "--not", "--remotes").stdout
    return [line for line in output.split() if line]


def review_key(repository, commits):
    digest = hashlib.sha256()
    digest.update(repository.encode())
    for commit in sorted(commits):
        digest.update(commit.encode())
    return digest.hexdigest()[:20]


def iterate_added_lines(repository, references, git_arguments=None, initial_commit=None):
    """Yield (commit, path, line number, text) for every added line, plus (commit, path, None, None) per touched file.

    By default reads the unpushed commits of `references`. `git_arguments` replaces the git command
    (for the audit); `initial_commit` labels lines when the output has no commit markers (a plain diff).
    """
    if git_arguments is None:
        git_arguments = [
            "log", "-p", "--no-merges", "--no-color", "--no-ext-diff", "--unified=0", "--diff-filter=d",
            "--format=%x00COMMIT %H", *references, "--not", "--remotes", "--", ".", *EXCLUDED_PATHSPECS,
        ]
    process = subprocess.Popen(
        ["git", "-C", str(repository), "-c", "core.quotePath=false", *git_arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        errors="replace",
    )
    commit = initial_commit
    path = None
    line_number = 0
    for raw_line in process.stdout:
        line = raw_line.rstrip("\n")
        if line.startswith("\x00COMMIT "):
            commit = line.split(" ", 1)[1]
            path = None
            continue
        if line.startswith("diff --git "):
            remainder = line[len("diff --git "):]
            separator = remainder.rfind(" b/")
            path = remainder[separator + 3:] if separator != -1 else remainder
            yield commit, path, None, None
            continue
        if line.startswith("+++ "):
            if line.startswith("+++ b/"):
                path = line[6:]
            continue
        if line.startswith("@@"):
            match = re.match(r"@@ -\S+ \+(\d+)", line)
            line_number = int(match.group(1)) if match else 0
            continue
        if line.startswith("+") and path is not None:
            yield commit, path, line_number, line[1:]
            line_number += 1
    process.wait()


# ---------------------------------------------------------------- scanning

def mask(value):
    value = value.strip()
    if len(value) <= 6:
        return f"***({len(value)} chars)"
    return f"{value[:4]}…({len(value)} chars)"


# A value that is only a variable reference, such as $api_key, $API_KEY, ${TOKEN}, $(command),
# $env:TOKEN or %TOKEN%. Names must be snake_case or UPPER_CASE so that a password that merely
# starts with "$" (for example "$ecretPass1") is still treated as a value.
VARIABLE_REFERENCE = re.compile(
    r"^(?:\$(?:[a-z_][a-z0-9_]*|[A-Z_][A-Z0-9_]*|\{[^}]+\}|\([^)]+\)|env:[A-Za-z_]\w*)|%[A-Za-z_]\w*%)$"
)


def looks_like_placeholder(value):
    if VARIABLE_REFERENCE.match(value.strip()):
        return True
    # UI text such as "Please enter your password" or Thai labels: spaces or non-ASCII letters.
    if any(character.isspace() for character in value) or any(ord(character) > 127 for character in value):
        return True
    lowered = value.lower()
    if any(hint in lowered for hint in PLACEHOLDER_HINTS):
        return True
    return len(set(lowered)) <= 2


def sensitive_file_rule(path):
    if ENVIRONMENT_FILE.search(path) and not ENVIRONMENT_TEMPLATE.search(path):
        return "env-file"
    for rule_name, pattern in SENSITIVE_FILE_RULES:
        if pattern.search(path):
            return rule_name
    return None


def remote_urls(repository):
    output = run_git(repository, "remote", "-v", check=False).stdout
    return {fields[1].lower() for fields in (line.split() for line in output.splitlines()) if len(fields) >= 2}


def load_private_terms():
    """Return [(pattern, [allowed remote texts])] from the private terms file; missing file means no terms."""
    try:
        lines = PRIVATE_TERMS_FILE.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    terms = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        term, _, options = line.partition(ALLOW_REMOTE_SEPARATOR)
        term = term.strip()
        allowed_remotes = []
        options = options.strip()
        if options.startswith("allow-remote="):
            allowed_remotes = [text.strip().lower() for text in options[len("allow-remote="):].split(",") if text.strip()]
        try:
            pattern = re.compile(term, re.IGNORECASE)
        except re.error:
            pattern = re.compile(re.escape(term), re.IGNORECASE)
        terms.append((pattern, allowed_remotes))
    return terms


def personal_rules(repository):
    """Rules for personal information, active in every repo except where a term allows the repo's remotes."""
    rules = []
    user_names = set()
    try:
        user_names.add(getpass.getuser())
    except Exception:
        pass
    user_names.add(Path.home().name)
    for user_name in user_names:
        if len(user_name) < 3 or user_name.lower() in GENERIC_USER_NAMES:
            continue
        rules.append(("personal-home-path", re.compile(
            r"(?i)(?:/Users/|/home/|[A-Za-z]:(?:\\\\|\\|/)Users(?:\\\\|\\|/))" + re.escape(user_name) + r"(?![\w.\-])")))
    email = run_git(repository, "config", "--global", "user.email", check=False).stdout.strip()
    if "@" in email and not email.lower().endswith(("noreply.github.com", ".invalid", "example.com")):
        rules.append(("personal-email", re.compile(re.escape(email), re.IGNORECASE)))
    urls = remote_urls(repository)
    for pattern, allowed_remotes in load_private_terms():
        if allowed_remotes and urls and all(any(text in url for text in allowed_remotes) for url in urls):
            continue
        rules.append(("private-term", pattern))
    return rules


def scan_findings(repository, references):
    return scan_lines(repository, iterate_added_lines(repository, references))


def scan_lines(repository, added_lines, keep_raw=False):
    """Apply every rule to (commit, path, line number, text) tuples. With keep_raw, each finding also
    carries "raw_key", a digest of the raw value, so the audit can match history to HEAD without
    keeping the value itself."""
    findings = []
    seen = set()
    private_rules = personal_rules(repository)

    def add(finding, raw_value):
        if keep_raw:
            finding["raw_key"] = hashlib.sha256(f"{finding['rule']}\0{finding['path']}\0{raw_value}".encode()).hexdigest()
        findings.append(finding)

    for commit, path, line_number, text in added_lines:
        if line_number is None:
            rule_name = sensitive_file_rule(path)
            key = (rule_name, path)
            if rule_name and key not in seen:
                seen.add(key)
                add({"rule": rule_name, "commit": commit, "path": path, "line": None, "value": "(whole file)"}, "(whole file)")
            for rule_name, pattern in private_rules:
                match = pattern.search(path)
                key = (rule_name, path, "path")
                if match and key not in seen:
                    seen.add(key)
                    add({"rule": rule_name, "commit": commit, "path": path, "line": None,
                         "value": f"in file name: {mask(match.group(0))}"}, "path:" + match.group(0).lower())
            continue
        if SKIPPED_PATHS.search(path) or INLINE_ALLOW_MARKER in text:
            continue
        for rule_name, pattern in private_rules:
            for match in pattern.finditer(text):
                key = (rule_name, path, match.group(0).lower())
                if key in seen:
                    continue
                seen.add(key)
                add({"rule": rule_name, "commit": commit, "path": path, "line": line_number, "value": mask(match.group(0))},
                    match.group(0).lower())
        broad_rules_apply = len(text) <= LONG_LINE_LENGTH and not BROAD_RULE_SKIPPED_PATHS.search(path)
        for rule_name, pattern, group_index, check_placeholder in CONTENT_RULES:
            if check_placeholder and not broad_rules_apply:
                continue
            for match in pattern.finditer(text):
                value = match.group(group_index) or match.group(0)
                if check_placeholder and looks_like_placeholder(value):
                    continue
                key = (rule_name, path, value)
                if key in seen:
                    continue
                seen.add(key)
                add({"rule": rule_name, "commit": commit, "path": path, "line": line_number, "value": mask(value)}, value)
    return findings


def format_finding(finding):
    location = finding["path"] if finding["line"] is None else f"{finding['path']}:{finding['line']}"
    return f"  - {finding['rule']}  {location}  (commit {finding['commit'][:8]})  value {finding['value']}"


# ---------------------------------------------------------------- command parsing

PUSH_SEGMENT_SPLITTER = re.compile(r"&&|\|\||;|\||\n")
GIT_OPTIONS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
SHELLS = {"bash", "sh", "zsh", "pwsh", "powershell"}
UNSCANNABLE = None  # marker in place of references: a push that bypasses git and cannot be scanned
GH_REPO_WRITE_PATH = re.compile(r"/repos/[^/\s]+/[^/\s]+/(contents|git)/")
# git subcommands that create commits. When one runs in the same command as a push, the hook
# (which runs before the command) cannot see those commits, so the push would go out unscanned.
COMMIT_CREATING_SUBCOMMANDS = {"commit", "merge", "rebase", "cherry-pick", "revert", "am", "pull"}


def option_value(tokens, names):
    for index, token in enumerate(tokens):
        for name in names:
            if token == name and index + 1 < len(tokens):
                return tokens[index + 1]
            if name.startswith("--") and token.startswith(name + "="):
                return token.split("=", 1)[1]
    return None


def gh_push_invocation(tokens, directory):
    """Return (directory, references) when a `gh` command pushes commits, else None.

    gh repo create --push    pushes the current branch (HEAD) of --source (default ".")
    gh pr create             may push the current branch before opening the pull request
    gh api -X PUT|POST|PATCH|DELETE /repos/o/r/contents|git/...   writes to a repo without git: unscannable
    """
    words = [token for token in tokens[1:] if not token.startswith("-")]
    if words[:2] == ["repo", "create"] and "--push" in tokens:
        source = option_value(tokens, ["--source", "-s"]) or "."
        return (os.path.normpath(os.path.join(directory, os.path.expanduser(source))), ["HEAD"])
    if words[:2] == ["pr", "create"]:
        return (directory, ["HEAD"])
    if words[:1] == ["api"]:
        method = (option_value(tokens, ["--method", "-X"]) or "").upper()
        has_fields = any(token in ("-f", "-F", "--field", "--raw-field", "--input") for token in tokens)
        writes = method in ("PUT", "POST", "PATCH", "DELETE") or (not method and has_fields)
        if writes and any(GH_REPO_WRITE_PATH.search("/" + token.lstrip("/")) for token in tokens):
            return (directory, UNSCANNABLE)
    return None


def find_push_invocations(command, working_directory, depth=0, commit_creators=None):
    """Return a list of (directory, references) for every push in the command.

    Covers `git push`, `git subtree push`, `gh repo create --push`, `gh pr create`, repo-writing
    `gh api` calls (references UNSCANNABLE) and any of these inside `bash|sh|zsh -c "..."`.
    When a list is passed as commit_creators, every git subcommand in the command that creates
    commits (COMMIT_CREATING_SUBCOMMANDS) is appended to it as (directory, subcommand).
    """
    invocations = []
    directory = working_directory
    for segment in PUSH_SEGMENT_SPLITTER.split(command):
        try:
            tokens = shlex.split(segment)
        except ValueError:
            # Unbalanced quotes: the splitter cut a quoted script such as `bash -c '... && git push'`.
            # Strip the stray quotes so `push'` still reads as `push`.
            tokens = [token.strip("'\"") for token in segment.split()]
            tokens = [token for token in tokens if token]
        while tokens and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[0]):
            tokens.pop(0)
        if not tokens:
            continue
        if tokens[0].lower() in ("cd", "set-location", "sl", "pushd") and len(tokens) > 1:
            directory = os.path.normpath(os.path.join(directory, os.path.expanduser(tokens[1])))
            continue
        while tokens and tokens[0] in ("rtk", "command", "exec", "time", "nohup", "env", "sudo"):
            tokens.pop(0)
        if not tokens:
            continue
        program = os.path.basename(tokens[0]).lower()
        if program.endswith(".exe"):
            program = program[:-4]
        if program in SHELLS and depth < 3:
            script_flag = next((flag for flag in ("-c", "-Command", "-command") if flag in tokens), None)
            if script_flag and tokens.index(script_flag) + 1 < len(tokens):
                script = " ".join(tokens[tokens.index(script_flag) + 1:])
                invocations += find_push_invocations(script, directory, depth + 1, commit_creators)
            continue
        if program == "gh":
            invocation = gh_push_invocation(tokens, directory)
            if invocation:
                invocations.append(invocation)
            continue
        if program != "git":
            continue
        index = 1
        git_directory = directory
        while index < len(tokens) and tokens[index].startswith("-"):
            option = tokens[index]
            if option in GIT_OPTIONS_WITH_VALUE and index + 1 < len(tokens):
                if option == "-C":
                    git_directory = os.path.normpath(os.path.join(git_directory, os.path.expanduser(tokens[index + 1])))
                index += 2
            else:
                index += 1
        if index < len(tokens) and tokens[index] == "subtree" and "push" in tokens[index + 1:]:
            invocations.append((git_directory, ["HEAD"]))
            continue
        if index < len(tokens) and tokens[index] in COMMIT_CREATING_SUBCOMMANDS and commit_creators is not None:
            commit_creators.append((git_directory, tokens[index]))
        if index >= len(tokens) or tokens[index] != "push":
            continue
        invocations.append((git_directory, push_references(git_directory, tokens[index + 1:])))
    return invocations


def push_references(directory, arguments):
    references = []
    positionals = []
    for argument in arguments:
        if argument in ("--all", "--mirror", "--branches"):
            references.append("--branches")
        elif argument == "--tags":
            references.append("--tags")
        elif not argument.startswith("-"):
            positionals.append(argument)
    refspecs = positionals[1:]
    if not refspecs:
        return references or ["HEAD"]
    for refspec in refspecs:
        source = refspec.lstrip("+").split(":", 1)[0]
        if not source:
            continue  # deletion such as `:branch`
        resolved = run_git(directory, "rev-parse", "--verify", "--quiet", f"{source}^{{commit}}", check=False)
        if resolved.returncode == 0:
            references.append(resolved.stdout.strip())
    return references


# ---------------------------------------------------------------- hook

def emit_decision(decision, reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))


def reference_arguments(references):
    return " ".join(f"--ref {shlex.quote(reference)}" for reference in references)


def hook_main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("tool_name") not in ("Bash", "PowerShell"):
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if "push" not in command and "gh" not in command:
        return 0
    working_directory = payload.get("cwd") or os.getcwd()
    acknowledged = ACKNOWLEDGE_TOKEN in command

    try:
        commit_creators = []
        invocations = find_push_invocations(command, working_directory, commit_creators=commit_creators)
        if invocations and commit_creators:
            created_by = ", ".join(sorted({f"git {subcommand}" for _, subcommand in commit_creators}))
            emit_decision("deny", "[secret-scan] Push blocked: this one command both creates commits "
                                  f"({created_by}) and pushes. This hook runs before the command starts, so it "
                                  "cannot see the new commits, and they would go out unscanned.\n"
                                  "Run them as separate tool calls: first the commit (or merge, rebase, pull...), "
                                  "then the push on its own, so the outgoing commits are scanned. "
                                  f"{ACKNOWLEDGE_TOKEN} does not override this.")
            return 0
        blocked_sections = []
        acknowledged_sections = []
        for directory, references in invocations:
            if references is UNSCANNABLE:
                section = ("UNSCANNABLE PUSH: this `gh api` call writes to a repository directly, bypassing git, "
                           "so its content cannot be scanned. Commit locally and use `git push` instead.")
                blocked_sections.append(section)
                acknowledged_sections.append(section)
                continue
            repository = repository_root(directory)
            if repository is None or not references:
                continue
            commits = unpushed_commits(repository, references)
            if not commits:
                continue
            key = review_key(repository, commits)
            findings = scan_findings(repository, references)
            approved = (STATE_DIRECTORY / key).exists()
            header = f"repo: {repository}\n  refs: {' '.join(references)}\n  unpushed commits: {len(commits)}\n  key: {key}"
            if findings:
                lines = [format_finding(finding) for finding in findings[:MAXIMUM_REPORTED_FINDINGS]]
                if len(findings) > MAXIMUM_REPORTED_FINDINGS:
                    lines.append(f"  ... and {len(findings) - MAXIMUM_REPORTED_FINDINGS} more")
                section = f"POSSIBLE SECRETS OR PERSONAL INFO FOUND\n  {header}\n" + "\n".join(lines)
                blocked_sections.append(section)
                acknowledged_sections.append(section)
            elif not approved:
                blocked_sections.append(f"NOT YET REVIEWED BY {AGENT_NAME}\n  {header}")
                acknowledged_sections.append(f"Not reviewed by {AGENT_NAME}\n  {header}")
            if findings or not approved:
                blocked_sections[-1] += f"\n  agent arguments: --repo {shlex.quote(repository)} {reference_arguments(references)} --key {key}"
    except Exception as error:  # fail closed, but let the user decide
        if acknowledged:
            emit_decision("ask", f"[secret-scan] Scan error ({error}). User must approve this push manually.")
        else:
            emit_decision("deny", f"[secret-scan] Push blocked because the secret scan failed: {error}. "
                                  f"Tell the user. If they still want to push, retry as `{ACKNOWLEDGE_TOKEN} <same push command>` "
                                  "and they will be asked to approve it.")
        return 0

    if not blocked_sections:
        return 0

    if acknowledged:
        emit_decision("ask", "[secret-scan] Push requested with SECRET_SCAN_ACK=1 despite:\n\n" + "\n\n".join(acknowledged_sections)
                      + "\n\nApprove only if you have checked these are false positives.")
        return 0

    reason = (
        "[secret-scan] Push blocked.\n\n" + "\n\n".join(blocked_sections) + "\n\n"
        f"Next step: dispatch the `{AGENT_NAME}` agent (Agent tool, subagent_type \"{AGENT_NAME}\") and pass it the "
        "agent arguments line(s) above. It reviews the outgoing commits and, when they are clean, records its approval.\n"
        "- Agent verdict PASS: retry the exact same push command.\n"
        "- Agent verdict FAIL or NEEDS USER: report the agent's findings to the user in Thai and STOP. Do not push, "
        "do not rewrite commits, until the user decides.\n"
        f"- Only if the user explicitly confirms the findings are false positives: retry as `{ACKNOWLEDGE_TOKEN} <same push command>`; "
        "the user will get an approval prompt.\n"
        "Never run the approve command yourself and never print full secret values."
    )
    emit_decision("deny", reason)
    return 0


# ---------------------------------------------------------------- command line modes

def resolve_repository(arguments):
    repository = repository_root(os.path.expanduser(arguments.repo))
    if repository is None:
        sys.exit(f"not a git repository: {arguments.repo}")
    return repository, (arguments.ref or ["HEAD"])


def command_scan(arguments):
    repository, references = resolve_repository(arguments)
    commits = unpushed_commits(repository, references)
    print(f"repo: {repository}\nrefs: {' '.join(references)}\nunpushed commits: {len(commits)}")
    if not commits:
        print("nothing to push")
        return 0
    print(f"key: {review_key(repository, commits)}")
    print(run_git(repository, "log", "--no-merges", "--format=  %h %an %ad %s", "--date=short", *references, "--not", "--remotes").stdout.rstrip())
    findings = scan_findings(repository, references)
    print(f"\ndeterministic findings: {len(findings)}")
    for finding in findings:
        print(format_finding(finding))
    return 1 if findings else 0


def command_diff(arguments):
    repository, references = resolve_repository(arguments)
    current_commit = None
    for commit, path, line_number, text in iterate_added_lines(repository, references):
        if commit != current_commit:
            current_commit = commit
            print(f"\n=== commit {commit[:12]}")
        if line_number is None:
            print(f"--- file {path}")
        else:
            print(f"{path}:{line_number}: {text}")
    return 0


def empty_tree(repository):
    completed = subprocess.run(["git", "-C", str(repository), "mktree"], input="", capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(f"git mktree failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


def command_audit(arguments):
    """Read-only audit: every tracked file at HEAD, then every commit in history (all refs, oldest first)."""
    repository = repository_root(os.path.expanduser(arguments.repo))
    if repository is None:
        sys.exit(f"not a git repository: {arguments.repo}")
    head = run_git(repository, "rev-parse", "--verify", "--quiet", "HEAD", check=False).stdout.strip()
    if not head:
        print(f"repo: {repository}\nno commits yet; nothing to audit")
        return 0
    head_lines = iterate_added_lines(
        repository, None, initial_commit=head,
        git_arguments=["diff", "--no-color", "--no-ext-diff", "--unified=0", empty_tree(repository), head,
                       "--", ".", *EXCLUDED_PATHSPECS])
    head_findings = scan_lines(repository, head_lines, keep_raw=True)
    history_lines = iterate_added_lines(
        repository, None,
        git_arguments=["log", "-p", "--all", "--reverse", "--no-merges", "--no-color", "--no-ext-diff",
                       "--unified=0", "--diff-filter=d", "--format=%x00COMMIT %H",
                       *([f"--since={arguments.since}"] if arguments.since else []),
                       "--", ".", *EXCLUDED_PATHSPECS])
    history_findings = scan_lines(repository, history_lines, keep_raw=True)
    pushed_commits = set(run_git(repository, "rev-list", "--remotes", check=False).stdout.split())
    in_head = {finding["raw_key"] for finding in head_findings}
    history_only = [finding for finding in history_findings if finding["raw_key"] not in in_head]
    count_arguments = ["rev-list", "--all", "--count"] + ([f"--since={arguments.since}"] if arguments.since else [])
    since_label = f", since {arguments.since}" if arguments.since else ""
    commit_count = run_git(repository, *count_arguments, check=False).stdout.strip() or "?"
    remotes = ", ".join(sorted(remote_urls(repository))) or "(none)"

    print(f"repo: {repository}\nHEAD: {head[:12]}\ncommits in history (all refs{since_label}): {commit_count}\nremotes: {remotes}")
    print(f"\n== A. In the current files (HEAD): {len(head_findings)} finding(s)")
    for finding in head_findings[:arguments.limit]:
        print(format_finding(finding))
    if len(head_findings) > arguments.limit:
        print(f"  ... and {len(head_findings) - arguments.limit} more")
    print(f"\n== B. Only in history (removed from the current files, still in old commits): {len(history_only)} finding(s)")
    for finding in history_only[:arguments.limit]:
        where = "pushed" if finding["commit"] in pushed_commits else "local only"
        print(format_finding(finding) + f"  [{where}]")
    if len(history_only) > arguments.limit:
        print(f"  ... and {len(history_only) - arguments.limit} more")
    print("\nNote: values are masked. Merge commits, lockfiles, SVG, source maps and minified files are not read,"
          " and the audit never records an approval.")
    return 1 if head_findings or history_only else 0


def command_approve(arguments):
    repository, references = resolve_repository(arguments)
    commits = unpushed_commits(repository, references)
    if not commits:
        print("nothing to push; no approval needed")
        return 0
    key = review_key(repository, commits)
    if key != arguments.key:
        print(f"REFUSED: key mismatch (current {key}); commits changed since the block. Re-run scan.")
        return 2
    findings = scan_findings(repository, references)
    if findings:
        print(f"REFUSED: deterministic scan still has {len(findings)} finding(s). Only the user can override with {ACKNOWLEDGE_TOKEN}.")
        return 2
    STATE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (STATE_DIRECTORY / key).write_text(json.dumps({
        "repository": repository, "references": references, "commits": commits, "approved_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }, indent=2))
    print(f"APPROVED: key {key} ({len(commits)} commit(s)). The push can be retried.")
    return 0


def main():
    if len(sys.argv) == 1:
        return hook_main()
    parser = argparse.ArgumentParser(description="Secret scan for unpushed commits")
    subparsers = parser.add_subparsers(dest="mode", required=True)
    for mode in ("scan", "diff", "approve", "audit"):
        subparser = subparsers.add_parser(mode)
        subparser.add_argument("--repo", required=True)
        if mode == "audit":
            subparser.add_argument("--limit", type=int, default=200)
            subparser.add_argument("--since", help="only read history after this date, a date (YYYY-MM-DD) or text such as '6 months ago'")
        else:
            subparser.add_argument("--ref", action="append")
        if mode == "approve":
            subparser.add_argument("--key", required=True)
    arguments = parser.parse_args()
    modes = {"scan": command_scan, "diff": command_diff, "approve": command_approve, "audit": command_audit}
    return modes[arguments.mode](arguments)


if __name__ == "__main__":
    sys.exit(main())
