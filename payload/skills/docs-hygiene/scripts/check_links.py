#!/usr/bin/env python3
"""Check relative Markdown links and #anchors in a repo.

Usage: check_links.py [REPO]   (default: current directory)
Prints one line per broken link, "file:line: target: reason", sorted.
Exit code 1 when anything is broken. Run it before and after a move or
condense and diff the two outputs: fix only the new lines.
"""
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
EXPLICIT_ANCHOR = re.compile(r"<a\s+(?:name|id)=\"([^\"]+)\"")


def slugify(heading_text):
    """GitHub-style heading slug."""
    text = re.sub(r"`([^`]*)`", r"\1", heading_text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text).strip().lower()
    kept = []
    for character in text:
        category = unicodedata.category(character)
        if character in " -_" or category[0] in "LNM":
            kept.append(character)
    return "".join(kept).replace(" ", "-")


def markdown_files(repository):
    try:
        output = subprocess.run(
            ["git", "-C", str(repository), "ls-files", "-z", "--", "*.md", "*.markdown"],
            check=True, capture_output=True, text=True,
        ).stdout
        return [repository / name for name in output.split("\0") if name]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return sorted(repository.rglob("*.md"))


def read_lines(path):
    lines, in_fence = [], False
    for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            lines.append((number, line))
    return lines


def anchors_of(path, cache):
    if path not in cache:
        found, seen = set(), {}
        for _, line in read_lines(path):
            for explicit in EXPLICIT_ANCHOR.findall(line):
                found.add(explicit)
            match = HEADING.match(line)
            if match:
                slug = slugify(match.group(2))
                count = seen.get(slug, 0)
                seen[slug] = count + 1
                found.add(slug if count == 0 else f"{slug}-{count}")
        cache[path] = found
    return cache[path]


def main():
    repository = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    cache, problems = {}, []
    for source in markdown_files(repository):
        if not source.is_file():
            continue
        for number, line in read_lines(source):
            for target in LINK.findall(re.sub(r"`[^`]*`", "", line)):
                if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
                    continue  # http:, mailto: and other schemes
                path_part, _, anchor = target.partition("#")
                path_part = path_part.split("?")[0]
                if path_part.startswith("/"):
                    destination = repository / path_part.lstrip("/")
                elif path_part:
                    destination = (source.parent / path_part).resolve()
                else:
                    destination = source
                where = f"{source.relative_to(repository)}:{number}: {target}"
                if not destination.exists():
                    problems.append(f"{where}: missing file")
                elif anchor and destination.suffix.lower() in (".md", ".markdown"):
                    if anchor.lower() not in anchors_of(destination, cache):
                        problems.append(f"{where}: missing anchor")
    for problem in sorted(problems):
        print(problem)
    print(f"{len(problems)} broken link(s)", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
