#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# mdx-yaml-fix · run `nika check --fix` on every authored ```yaml workflow
# fence of the docs, in place, and splice the repaired block back into the
# page byte-exact · one tool instead of one hand gesture per fence.
#
# What it does, per fence:
#   · finds every ```yaml fence (the info-string is FREE TEXT: bare, a
#     `<slug>.nika.yaml` name, a prose title · and the trap where the
#     envelope line itself sits in the title, ` ```yaml nika: v1 `: that
#     line is moved INTO the body first, the title becomes bare);
#   · fences may be INDENTED (a block inside an <Accordion> sits four
#     spaces in): the indent is stripped before the oracle reads the block
#     and put back on every line on splice-back;
#   · skips fences whose info-string says skeleton · illustration ·
#     modeline (not runnable by declaration) and fences whose first
#     content line is not `^\s*nika:\s` (fragments · a nested `nika:`
#     is another tool's key · the oracle needs a whole file);
#   · REFUSES to touch a fence inside a projected region
#     ({/* showcase:begin */} … {/* template:begin */} … {/* errors-*:begin */})
#     and the projected snippets · those re-project from nika-spec, a hand
#     edit there is a corruption the next projection reverts;
#   · writes the block to a temp file (named fences are materialized as
#     siblings first, so a composition parent resolves its child), runs
#     `nika check --fix <tmp>` then `nika check <tmp>`, and reports one
#     line per block: fixed · clean · STOP · skipped.
#
# Usage:  python3 scripts/mdx-yaml-fix.py [--dry] [--nika PATH] [FILE …]
#   no FILE → every tracked *.mdx / *.md (git ls-files)
#   --dry   → report, write nothing
#   --nika  → the binary to judge with (default: `nika` on PATH · NIKA_BIN)
# Exit 0 when no block STOPped · 1 when at least one did · 2 when no binary.
from __future__ import annotations

import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent

FENCE_OPEN = re.compile(r"^([ \t]*)```yaml([^\n]*)$")
FENCE_CLOSE = re.compile(r"^[ \t]*```[ \t]*$")
SKIP_INFO = re.compile(r"skeleton|illustration|modeline", re.I)
NAMED = re.compile(r"^\s*([A-Za-z0-9._-]+\.nika\.yaml)\s*$")
# the trap: the whole info-string IS an envelope line (` ```yaml nika: v1 `)
TITLE_ENVELOPE = re.compile(r"^\s*(nika:\s*\S+)\s*$")
ENVELOPE = re.compile(r"^\s*nika:\s", re.M)
REGION_BEGIN = re.compile(r"\{/\*\s*([a-z0-9-]+):begin\b")
REGION_END = re.compile(r"\{/\*\s*([a-z0-9-]+):end\b")
REFUSAL = re.compile(r"✗|✖")
PROJECTED_FILES = {
    "snippets/_canon.mdx",
    "snippets/_showcase.mdx",
    "snippets/_status-snapshot.mdx",
}


def dedent(lines: list[str], indent: str) -> list[str]:
    if not indent:
        return lines
    return [l[len(indent):] if l.startswith(indent) else l for l in lines]


def reindent(lines: list[str], indent: str) -> list[str]:
    if not indent:
        return lines
    # a blank line stays blank (no trailing whitespace planted)
    return [(indent + l) if l.strip("\r\n") else l for l in lines]


class Block:
    def __init__(self, path, open_idx, close_idx, indent, info, region):
        self.path = path
        self.open_idx = open_idx      # index of the opening fence line
        self.close_idx = close_idx    # index of the closing fence line
        self.indent = indent
        self.info = info              # raw info-string (after ```yaml)
        self.region = region          # projected region name or None
        self.line = open_idx + 1      # 1-based, for the report

    @property
    def name(self) -> str | None:
        m = NAMED.match(self.info)
        return m.group(1) if m else None


def find_blocks(lines: list[str]) -> list[Block]:
    """Every ```yaml fence of a page, with the projected region it sits in."""
    blocks: list[Block] = []
    region: str | None = None
    i = 0
    while i < len(lines):
        raw = lines[i].rstrip("\r\n")
        if (m := REGION_BEGIN.search(raw)):
            region = m.group(1)
        if REGION_END.search(raw):
            region = None
        if (m := FENCE_OPEN.match(raw)):
            indent, info = m.group(1), m.group(2)
            j = i + 1
            while j < len(lines) and not FENCE_CLOSE.match(lines[j].rstrip("\r\n")):
                j += 1
            if j >= len(lines):
                break  # unterminated fence · leave the page alone
            blocks.append(Block(None, i, j, indent, info, region))
            i = j
        i += 1
    return blocks


def judge(nika: str, path: pathlib.Path) -> tuple[int, str]:
    r = subprocess.run([nika, "check", str(path)], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def first_refusal(out: str) -> str:
    for l in out.splitlines():
        if REFUSAL.search(l):
            return l.strip()[:160]
    return out.strip().splitlines()[-1][:160] if out.strip() else "(no output)"


def process_file(fp: pathlib.Path, nika: str, dry: bool, report: list[str],
                 rel: str | None = None) -> tuple[int, dict]:
    """Repair one page in place · returns (stops, counts).

    `rel` is the label used in the report (and the key of PROJECTED_FILES);
    it defaults to the path relative to the docs root.
    """
    counts = {"fixed": 0, "clean": 0, "STOP": 0, "skipped": 0}
    fp = pathlib.Path(fp)
    if rel is None:
        try:
            rel = str(fp.resolve().relative_to(ROOT))
        except ValueError:
            rel = str(fp)
    text = fp.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    blocks = find_blocks(lines)
    if not blocks:
        return 0, counts
    if rel in PROJECTED_FILES:
        for b in blocks:
            report.append(f"{rel}:{b.line}  skipped  · projected file (re-project from nika-spec, never hand-fix)")
            counts["skipped"] += 1
        return 0, counts

    page_dir = pathlib.Path(tempfile.mkdtemp(prefix="mdx-yaml-fix-"))
    # named siblings first · a composition parent must resolve its child
    # (a named block's temp file IS its sibling · `--fix` repairs it in place)
    for b in blocks:
        if b.name and b.region is None and not SKIP_INFO.search(b.info):
            body = "".join(dedent(lines[b.open_idx + 1:b.close_idx], b.indent))
            if TITLE_ENVELOPE.match(b.info):
                body = TITLE_ENVELOPE.match(b.info).group(1) + "\n" + body
            (page_dir / b.name).write_text(body, encoding="utf-8")

    # forward pass · a composition child is fixed before its parent is
    # judged (the sibling on disk is the fixed one) · splices are collected
    # and applied in reverse at the end so line indices stay valid
    splices: list[tuple[int, int, list[str]]] = []
    for b in blocks:
        loc = f"{rel}:{b.line}"
        if b.region is not None:
            report.append(f"{loc}  skipped  · inside a projected region ({b.region}) · refused")
            counts["skipped"] += 1
            continue
        if SKIP_INFO.search(b.info):
            report.append(f"{loc}  skipped  · info-string says non-runnable ({b.info.strip()})")
            counts["skipped"] += 1
            continue
        body_lines = dedent(lines[b.open_idx + 1:b.close_idx], b.indent)
        title_move = TITLE_ENVELOPE.match(b.info)
        if title_move:
            body_lines = [title_move.group(1) + "\n"] + body_lines
        body = "".join(body_lines)
        if not ENVELOPE.search(body):
            report.append(f"{loc}  skipped  · no envelope line (a fragment · the oracle needs a whole file)")
            counts["skipped"] += 1
            continue
        name = b.name or f"block-{b.line}.nika.yaml"
        tmp = page_dir / name
        tmp.write_text(body, encoding="utf-8")
        subprocess.run([nika, "check", "--fix", str(tmp)], capture_output=True, text=True)
        rc, out = judge(nika, tmp)
        fixed = tmp.read_text(encoding="utf-8")
        did_fix = fixed != body or title_move is not None
        if rc != 0:
            counts["STOP"] += 1
            tag = "STOP (partly fixed)" if fixed != body else "STOP"
            report.append(f"{loc}  {tag}  [{name}] · {first_refusal(out)}")
        elif did_fix:
            counts["fixed"] += 1
            what = "envelope moved from the title into the body" if title_move else "nika check --fix"
            report.append(f"{loc}  fixed    [{name}] · {what}")
        else:
            counts["clean"] += 1
            report.append(f"{loc}  clean    [{name}]")
        if did_fix:
            new_body = reindent(fixed.splitlines(keepends=True), b.indent)
            if new_body and not new_body[-1].endswith("\n"):
                new_body[-1] += "\n"
            open_line = lines[b.open_idx]
            if title_move:
                # the title was the envelope line · the fence becomes bare
                nl = "\r\n" if open_line.endswith("\r\n") else "\n"
                open_line = f"{b.indent}```yaml{nl}"
            splices.append((b.open_idx, b.close_idx, [open_line] + new_body + [lines[b.close_idx]]))
    for open_idx, close_idx, new_lines in reversed(splices):
        lines[open_idx:close_idx + 1] = new_lines
    changed = bool(splices)
    shutil.rmtree(page_dir, ignore_errors=True)
    if changed and not dry:
        fp.write_text("".join(lines), encoding="utf-8")
    return counts["STOP"], counts


def tracked_pages() -> list[str]:
    r = subprocess.run(["git", "ls-files", "*.mdx", "*.md", "**/*.mdx", "**/*.md"],
                       cwd=ROOT, capture_output=True, text=True)
    return sorted(set(l for l in r.stdout.splitlines() if l.endswith((".mdx", ".md"))))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="*", help="pages to repair (default: every tracked *.mdx/*.md)")
    ap.add_argument("--dry", action="store_true", help="report only · write nothing")
    ap.add_argument("--nika", default=os.environ.get("NIKA_BIN") or shutil.which("nika"),
                    help="the binary that judges + repairs (default: NIKA_BIN or `nika` on PATH)")
    a = ap.parse_args(argv)
    if not a.nika or not pathlib.Path(a.nika).exists():
        print("mdx-yaml-fix · no `nika` binary (PATH · --nika · NIKA_BIN) · the judge IS the binary",
              file=sys.stderr)
        return 2
    files = a.files or tracked_pages()
    report: list[str] = []
    totals = {"fixed": 0, "clean": 0, "STOP": 0, "skipped": 0}
    for f in files:
        fp = pathlib.Path(f) if pathlib.Path(f).is_absolute() else ROOT / f
        if not fp.is_file():
            report.append(f"{f}  skipped  · not a file")
            continue
        _, counts = process_file(fp, a.nika, a.dry, report)
        for k in totals:
            totals[k] += counts[k]
    for l in report:
        print(l)
    mode = "dry · nothing written" if a.dry else "written in place"
    print(f"mdx-yaml-fix: {sum(totals.values())} blocks · {totals['fixed']} fixed · "
          f"{totals['clean']} clean · {totals['STOP']} STOP · {totals['skipped']} skipped ({mode})")
    return 1 if totals["STOP"] else 0


if __name__ == "__main__":
    sys.exit(main())
