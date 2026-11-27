"""PreToolUse hook body for read-only agents that have `memory:` enabled.

Claude Code adds Write/Edit to any agent with memory; this keeps those tools inside the
agent's own memory directory: ~/.claude/agent-memory/<agent-name>/

Called by agent-memory-only.sh with the agent name as argv[1] and the hook JSON on stdin.
Exit 0 = allow, exit 2 = block (stderr is shown to the agent).
Fails closed: any parse error or missing path blocks the call.
Portable: macOS, Linux and Windows (case-insensitive paths, C:\\ or /c/ style).
"""
import json
import os
import re
import sys


def normalise(path):
    # Git Bash style /c/Users/... -> C:/Users/... on Windows
    if os.name == "nt":
        match = re.match(r"^/([a-zA-Z])/(.*)$", path)
        if match:
            path = f"{match.group(1)}:/{match.group(2)}"
    return os.path.normcase(os.path.realpath(path))


def main():
    agent_name = sys.argv[1] if len(sys.argv) > 1 else ""
    if not re.fullmatch(r"[a-z0-9-]+", agent_name):
        print("agent-memory-only: invalid or missing agent name argument", file=sys.stderr)
        sys.exit(2)
    try:
        hook_input = json.load(sys.stdin)
        tool_input = hook_input.get("tool_input") or {}
        file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
        if not file_path:
            raise ValueError("no file_path in tool_input")
        if not os.path.isabs(file_path) and not re.match(r"^/[a-zA-Z]/", file_path):
            file_path = os.path.join(hook_input.get("cwd") or os.getcwd(), file_path)
        resolved_target = normalise(file_path)
        memory_directory = normalise(
            os.path.join(os.path.expanduser("~"), ".claude", "agent-memory", agent_name)
        )
    except Exception as error:
        print(f"agent-memory-only: blocked, could not read the tool call ({error})", file=sys.stderr)
        sys.exit(2)

    if resolved_target.startswith(memory_directory + os.sep):
        sys.exit(0)

    print(
        f"agent-memory-only: blocked. {agent_name} may write only inside {memory_directory}{os.sep} "
        f"but tried {resolved_target}. You never edit project files; report findings instead.",
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
