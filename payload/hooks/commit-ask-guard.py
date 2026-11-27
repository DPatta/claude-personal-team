#!/usr/bin/env python3
"""PreToolUse hook (matcher: Bash): ask the user before any command that creates a git commit.

Rule (Preferences.md > Git): Claude may commit only when the user says so. This turns that soft
rule into a permission prompt: the user's approval in the dialog is the instruction. The prompt
shows what would be committed: repo, branch, the full message and the files.

Asks for: git commit, git merge, git cherry-pick, git revert
  (not for their --abort / --quit / --skip, nor merge --no-commit / --squash / cherry-pick -n).
Skips the prompt on branches named autopilot/* (Preferences.md: starting autopilot authorises
commits on its own local autopilot/* branch).
Also sees through: rtk / env / command / sudo prefixes, VAR=value prefixes, git -C <dir>,
git -c k=v, cd <dir> earlier in the same command, and bash|sh|zsh -c "<script>".

Output: a permissionDecision "ask" JSON, or nothing (no opinion; other hooks and rules decide).
Fails toward asking: if the command cannot be parsed but mentions git and a commit verb, ask.
"""
import json
import os
import re
import shlex
import subprocess
import sys

COMMIT_SUBCOMMANDS = {"commit", "merge", "cherry-pick", "revert"}
NON_COMMITTING_FLAGS = {
    "merge": {"--abort", "--quit", "--no-commit", "--squash"},
    "cherry-pick": {"--abort", "--quit", "--skip", "--no-commit", "-n"},
    "revert": {"--abort", "--quit", "--skip", "--no-commit", "-n"},
    "commit": set(),
}
COMMAND_SEPARATORS = {"&&", "||", ";", "|", "&", "\n", "(", ")", "|&", ";;"}
TRANSPARENT_PREFIXES = {"rtk", "env", "command", "sudo", "exec", "time", "nohup"}
SHELLS = {"bash", "sh", "zsh"}
GIT_OPTIONS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
ASSIGNMENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
FALLBACK_PATTERN = re.compile(r"\bgit\b.*\b(commit|merge|cherry-pick|revert)\b", re.DOTALL)
HEREDOC_PATTERN = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n(.*?)\n\s*\1\b", re.DOTALL)
QUOTED_MESSAGE_PATTERN = re.compile(
    r"""(?:-m|--message)[= ]\s*(?:"((?:[^"\\]|\\.)*)"|'([^']*)')""", re.DOTALL
)
MAXIMUM_MESSAGE_LINES = 10
MAXIMUM_FILES_SHOWN = 10
APPROVAL_HINT = "กด Yes เฉพาะเมื่อคุณสั่งให้ commit"
TITLE = "🔶 ขออนุญาต GIT COMMIT 🔶"


def split_into_simple_commands(script):
    lexer = shlex.shlex(script, posix=True, punctuation_chars=";&|()\n")
    lexer.whitespace_split = True
    lexer.commenters = "#"
    commands, current = [], []
    for token in lexer:
        if token in COMMAND_SEPARATORS or set(token) <= set(";&|()\n"):
            if current:
                commands.append(current)
            current = []
        else:
            current.append(token)
    if current:
        commands.append(current)
    return commands


def find_commit_commands(script, working_directory, depth=0):
    """Return (subcommand, directory, arguments) for every commit-creating git call in script."""
    found = []
    for words in split_into_simple_commands(script):
        index = 0
        while index < len(words) and (
            words[index] in TRANSPARENT_PREFIXES or ASSIGNMENT_PATTERN.match(words[index])
        ):
            index += 1
        if index >= len(words):
            continue
        program = os.path.basename(words[index])
        arguments = words[index + 1:]

        if program.lower() in ("cd", "set-location", "sl", "chdir", "pushd"):
            target = next((word for word in arguments if not word.startswith("-")), os.path.expanduser("~"))
            working_directory = os.path.normpath(os.path.join(working_directory, os.path.expanduser(target)))
            continue

        if program in SHELLS and depth < 3 and "-c" in arguments:
            position = arguments.index("-c")
            if position + 1 < len(arguments):
                found += find_commit_commands(arguments[position + 1], working_directory, depth + 1)
            continue

        if program != "git":
            continue

        git_directory = working_directory
        position = 0
        while position < len(arguments) and arguments[position].startswith("-"):
            option = arguments[position]
            if option == "-C" and position + 1 < len(arguments):
                git_directory = os.path.normpath(
                    os.path.join(git_directory, os.path.expanduser(arguments[position + 1]))
                )
                position += 2
            elif option in GIT_OPTIONS_WITH_VALUE and "=" not in option:
                position += 2
            else:
                position += 1
        if position >= len(arguments):
            continue
        subcommand = arguments[position]
        if subcommand not in COMMIT_SUBCOMMANDS:
            continue
        rest = arguments[position + 1:]
        if set(rest) & NON_COMMITTING_FLAGS[subcommand]:
            continue
        found.append((subcommand, git_directory, rest))
    return found


def commit_message(raw_command, arguments=None):
    """Best-effort full message: a heredoc body first, then -m/--message values, then a regex."""
    heredoc = HEREDOC_PATTERN.search(raw_command)
    if heredoc:
        return heredoc.group(2).strip("\n")
    messages = []
    words = arguments or []
    for position, word in enumerate(words):
        if word in ("-m", "--message") and position + 1 < len(words):
            messages.append(words[position + 1])
        elif word.startswith("--message="):
            messages.append(word.split("=", 1)[1])
        elif word.startswith("-m") and len(word) > 2 and not word.startswith("--"):
            messages.append(word[2:])
    if messages:
        return "\n\n".join(messages)
    match = QUOTED_MESSAGE_PATTERN.search(raw_command)
    if match:
        return match.group(1) if match.group(1) is not None else match.group(2)
    return ""


def commits_all_tracked_changes(arguments):
    for word in arguments:
        if word in ("-a", "--all"):
            return True
        if word.startswith("-") and not word.startswith("--") and len(word) > 2 and "m" not in word and "a" in word:
            return True
        if word in ("-am", "-ma"):
            return True
    return False


def files_to_commit(directory, arguments):
    command = ["git", "-C", directory, "diff", "--name-status"]
    command.append("HEAD" if commits_all_tracked_changes(arguments) else "--cached")
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=5)
        return [line.replace("\t", "  ") for line in result.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def current_branch(directory):
    try:
        result = subprocess.run(
            ["git", "-C", directory, "branch", "--show-current"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def indent(text, limit=MAXIMUM_MESSAGE_LINES):
    lines = text.splitlines() or [""]
    shown = lines[:limit]
    if len(lines) > limit:
        shown.append(f"… (+{len(lines) - limit} บรรทัด)")
    return "\n".join("    " + line for line in shown)


def describe(subcommand, directory, arguments, raw_command):
    branch = current_branch(directory)
    lines = [f"{subcommand.upper()} · repo: {os.path.basename(directory)} · branch: {branch or 'unknown'}"]
    if subcommand == "commit":
        if "--amend" in arguments:
            lines.append("⚠️ --amend: แก้ commit ล่าสุด")
        message = commit_message(raw_command, arguments)
        if not message and "--no-edit" in arguments:
            message = "(ใช้ message เดิมของ commit ล่าสุด)"
        lines.append("message:\n" + indent(message) if message else "message: (ไม่ได้ระบุ — จะเปิด editor หรืออ่านจากไฟล์)")
        files = files_to_commit(directory, arguments)
        if files:
            lines.append(f"files ({len(files)}):\n" + indent("\n".join(files), MAXIMUM_FILES_SHOWN))
        else:
            lines.append("files: (ยังไม่มีไฟล์ที่ stage — อาจ stage ในคำสั่งเดียวกัน)")
    else:
        target = " ".join(word for word in arguments if not word.startswith("-"))
        lines.append(f"target: {target or '(ไม่ระบุ)'}")
    return branch, "\n".join(lines)


def ask(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }, ensure_ascii=False))
    sys.exit(0)


def main():
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if hook_input.get("tool_name") not in ("Bash", "PowerShell"):
        sys.exit(0)
    command = (hook_input.get("tool_input") or {}).get("command") or ""
    if "git" not in command:
        sys.exit(0)
    working_directory = hook_input.get("cwd") or os.getcwd()

    try:
        commit_commands = find_commit_commands(command, working_directory)
    except Exception:
        if FALLBACK_PATTERN.search(command):
            message = commit_message(command)
            body = f"{TITLE}\n(อ่านคำสั่งได้ไม่ครบ แต่อาจสร้าง commit)\n"
            body += "message:\n" + indent(message) if message else "message: (หาไม่พบ)"
            ask(f"{body}\n\n{APPROVAL_HINT}")
        sys.exit(0)

    sections = []
    for subcommand, directory, arguments in commit_commands:
        branch, section = describe(subcommand, directory, arguments, command)
        if branch.startswith("autopilot/"):
            continue
        sections.append(section)

    if sections:
        ask(f"{TITLE}\n" + "\n\n".join(sections) + f"\n\n{APPROVAL_HINT}")
    sys.exit(0)


if __name__ == "__main__":
    main()
