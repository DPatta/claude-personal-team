// Docs layout test template (Vitest). Copy into the project's tests, then set the lists and caps with the owner.
// Keeps the docs from growing back: fixed layout, size caps, spec status, a short STATUS.md, a short CLAUDE.md.
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..", ".."); // adjust to the test's depth
const docsDirectory = join(repositoryRoot, "docs");

const ALLOWED_DOCS_ENTRIES = ["STATUS.md", "archive", "decisions", "knowledge", "specs"];
const FORBIDDEN_DOCS_FOLDERS = ["plans"]; // folders a dropped workflow used to write
const DECISIONS_MAX_BYTES = 32 * 1024;
const STATUS_MAX_LINES = 60;
const NEW_SPEC_MAX_LINES = 150;
const NEW_SPEC_FROM_DATE = "YYYY-MM-DD"; // specs named from this date on must be short
const CLAUDE_MD_MAX_LINES = 80;
const SPEC_STATUSES = ["active", "done"];

const lineCount = (text: string) => text.replace(/\r\n?/g, "\n").replace(/\n+$/, "").split("\n").length;
const markdownFiles = (directory: string) =>
  existsSync(directory) ? readdirSync(directory).filter((name) => name.endsWith(".md")) : [];

function frontMatterStatus(text: string): string | null {
  const lines = text.replace(/^﻿/, "").replace(/\r\n?/g, "\n").split("\n");
  if (lines[0] !== "---") return null;
  const end = lines.indexOf("---", 1);
  if (end < 0) return null;
  const statusLine = lines.slice(1, end).find((line) => line.startsWith("status:"));
  return statusLine ? statusLine.slice("status:".length).trim() : null;
}

describe("docs layout", () => {
  it("has none of the forbidden folders", () => {
    const present = FORBIDDEN_DOCS_FOLDERS.filter((name) => existsSync(join(docsDirectory, name)));
    expect(present).toEqual([]);
  });

  it("keeps only the known entries at the top of docs/", () => {
    const unexpected = readdirSync(docsDirectory).filter((name) => !ALLOWED_DOCS_ENTRIES.includes(name));
    expect(unexpected, "put new docs in specs/, decisions/, knowledge/ or archive/").toEqual([]);
  });

  it("keeps every decisions file under the size cap", () => {
    const decisionsDirectory = join(docsDirectory, "decisions");
    const tooLarge = markdownFiles(decisionsDirectory)
      .map((name) => ({ name, bytes: statSync(join(decisionsDirectory, name)).size }))
      .filter((file) => file.bytes > DECISIONS_MAX_BYTES);
    expect(tooLarge, "condense it and move the full record to docs/archive/decisions/").toEqual([]);
  });

  it("has a short STATUS.md with Now, Next and Parked", () => {
    const text = readFileSync(join(docsDirectory, "STATUS.md"), "utf8");
    expect(lineCount(text)).toBeLessThanOrEqual(STATUS_MAX_LINES);
    for (const heading of ["## Now", "## Next", "## Parked"]) {
      expect(text.split(/\r?\n/).some((line) => line.startsWith(heading)), heading).toBe(true);
    }
  });

  it("gives every spec a status in its front matter", () => {
    const specsDirectory = join(docsDirectory, "specs");
    const missing = markdownFiles(specsDirectory).filter(
      (name) => !SPEC_STATUSES.includes(frontMatterStatus(readFileSync(join(specsDirectory, name), "utf8")) ?? ""),
    );
    expect(missing, "add front matter `status: active` or `status: done`").toEqual([]);
  });

  it("keeps new specs short (the plan is their Tasks section)", () => {
    const specsDirectory = join(docsDirectory, "specs");
    const tooLong = markdownFiles(specsDirectory)
      .filter((name) => name.slice(0, 10) >= NEW_SPEC_FROM_DATE)
      .map((name) => ({ name, lines: lineCount(readFileSync(join(specsDirectory, name), "utf8")) }))
      .filter((spec) => spec.lines > NEW_SPEC_MAX_LINES);
    expect(tooLong).toEqual([]);
  });

  it("keeps CLAUDE.md short", () => {
    expect(lineCount(readFileSync(join(repositoryRoot, "CLAUDE.md"), "utf8"))).toBeLessThanOrEqual(CLAUDE_MD_MAX_LINES);
  });
});
