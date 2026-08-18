#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Tests for scripts/mdx-yaml-fix.py · run: python3 -m unittest scripts/tests/test_mdx_yaml_fix.py
#
# Two layers. The splice logic is proven against a STUB `nika` (a tiny
# script that performs the r1-identity rewrite deterministically), so the
# byte-exactness, the indent preservation, the title-as-envelope move and
# the projected-region refusal never depend on which binary is installed.
# The last test runs the same fixture through the REAL binary and is
# skipped unless one that refuses `nika: v1` is on PATH (or in NIKA_BIN).
from __future__ import annotations

import importlib.util
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
TOOL = HERE.parent / "mdx-yaml-fix.py"

spec = importlib.util.spec_from_file_location("mdx_yaml_fix", TOOL)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

STUB = r'''#!/usr/bin/env python3
# a stub `nika` · `check --fix F` performs the r1-identity rewrite in place
# (`nika: v1` + `workflow: {id, description}` → `# <description>` + `nika: <id>`)
# · `check F` exits 0 iff the file opens (comments aside) on `nika: <kebab>`
# and carries no `workflow:` line, else 2 with a PARSE ✗ line.
import re, sys
args = sys.argv[1:]
fix = "--fix" in args
path = [a for a in args if not a.startswith("-") and a != "check"][-1]
text = open(path, encoding="utf-8").read()
if fix:
    m = re.search(r'^nika: v1\n(?:workflow:\n  id: ([a-z][a-z0-9-]*)\n(?:  description: "([^"]*)"\n)?)', text, re.M)
    if m:
        head = (f"# {m.group(2)}\n" if m.group(2) else "") + f"nika: {m.group(1)}\n"
        text = text[:m.start()] + head + text[m.end():]
        open(path, "w", encoding="utf-8").write(text)
first = next((l for l in text.splitlines() if l.strip() and not l.startswith("#")), "")
ok = re.match(r"^nika: [a-z][a-z0-9-]*$", first) and not re.search(r"^workflow:", text, re.M)
if ok:
    print(" ✔ audited")
    sys.exit(0)
print("PARSE ✗  [NIKA-PARSE-005] unknown field `workflow` in the workflow envelope (strict mode)")
sys.exit(2)
'''

FIXTURE = '''---
title: fixture
description: "three fences · one plain · one indented · one whose title is the envelope"
---

import { CANON } from "/snippets/_canon.mdx"

Prose before the first fence · {CANON.builtins} builtins · `for_each: {items}` in backticks.

```yaml
nika: v1
workflow:
  id: plain-flow
  description: "The plain one."

tasks:
  greet:
    infer:
      prompt: "hi"
      model: ollama/qwen3.5:4b
```

<Accordion title="indented">
    Text inside the accordion.

    ```yaml
    nika: v1
    workflow:
      id: indented-flow

    tasks:
      greet:
        infer:
          prompt: "hi"
          model: ollama/qwen3.5:4b
    ```

    More text.
</Accordion>

```yaml nika: v1
workflow:
  id: og-hero
tasks:
  hero:
    infer:
      prompt: "hi"
      model: ollama/qwen3.5:4b
```

{/* showcase:begin projected.nika.yaml */}
```yaml projected.nika.yaml
nika: v1
workflow:
  id: projected-flow
tasks:
  greet:
    infer:
      prompt: "hi"
      model: ollama/qwen3.5:4b
```
{/* showcase:end */}

```yaml
  # a fragment · no envelope · never judged
  hero:
    for_each: { items: "${{ const.locales }}" }
```

```yaml the envelope · a skeleton, not a runnable file
nika: v1
workflow:
  id: <identifier>
```

Prose after the last fence.
'''

EXPECTED_PLAIN = '''```yaml
# The plain one.
nika: plain-flow

tasks:
  greet:
    infer:
      prompt: "hi"
      model: ollama/qwen3.5:4b
```'''

EXPECTED_INDENTED = '''    ```yaml
    nika: indented-flow

    tasks:
      greet:
        infer:
          prompt: "hi"
          model: ollama/qwen3.5:4b
    ```'''

EXPECTED_TITLE = '''```yaml
nika: og-hero
tasks:
  hero:
    infer:
      prompt: "hi"
      model: ollama/qwen3.5:4b
```'''


def strip_blocks(text: str) -> str:
    """The page with every ```yaml fence body blanked · what must stay byte-exact."""
    out, inside = [], False
    for line in text.splitlines(keepends=True):
        if mod.FENCE_OPEN.match(line.rstrip("\r\n")):
            inside = True
            out.append("<<open>>\n")
            continue
        if inside and mod.FENCE_CLOSE.match(line.rstrip("\r\n")):
            inside = False
            out.append("<<close>>\n")
            continue
        if not inside:
            out.append(line)
    return "".join(out)


class Base(unittest.TestCase):
    nika: str

    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp(prefix="mdx-yaml-fix-test-"))
        self.page = self.dir / "fixture.mdx"
        self.page.write_text(FIXTURE, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def run_tool(self, dry: bool = False) -> tuple[list[str], dict]:
        report: list[str] = []
        _, counts = mod.process_file(self.page, self.nika, dry, report, rel="fixture.mdx")
        return report, counts


class StubTests(Base):
    """The splice logic · judged by the stub, so the assertions are exact."""

    def setUp(self):
        super().setUp()
        stub = self.dir / "nika"
        stub.write_text(STUB, encoding="utf-8")
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
        self.nika = str(stub)

    def test_outside_the_blocks_is_byte_exact(self):
        before = strip_blocks(FIXTURE)
        report, counts = self.run_tool()
        after = self.page.read_text(encoding="utf-8")
        self.assertEqual(strip_blocks(after), before)
        self.assertEqual(counts["fixed"], 3, report)
        self.assertEqual(counts["STOP"], 0, report)
        self.assertTrue(after.endswith("Prose after the last fence.\n"))

    def test_plain_block_is_repaired(self):
        self.run_tool()
        after = self.page.read_text(encoding="utf-8")
        self.assertIn(EXPECTED_PLAIN, after)
        self.assertNotIn("id: plain-flow", after)

    def test_indented_block_keeps_its_indent(self):
        self.run_tool()
        after = self.page.read_text(encoding="utf-8")
        self.assertIn(EXPECTED_INDENTED, after)
        # every non-blank line of the accordion body still sits four spaces in
        seg = after[after.index("<Accordion"):after.index("</Accordion>")]
        for line in seg.splitlines()[1:]:
            if line.strip():
                self.assertTrue(line.startswith("    "), repr(line))

    def test_title_envelope_moves_into_the_body(self):
        report, _ = self.run_tool()
        after = self.page.read_text(encoding="utf-8")
        self.assertIn(EXPECTED_TITLE, after)
        self.assertNotIn("```yaml nika: v1", after)
        self.assertTrue(any("envelope moved from the title into the body" in l for l in report), report)

    def test_projected_region_is_refused(self):
        report, counts = self.run_tool()
        after = self.page.read_text(encoding="utf-8")
        region = after[after.index("{/* showcase:begin"):after.index("{/* showcase:end */}")]
        self.assertIn("nika: v1\nworkflow:\n  id: projected-flow", region)
        self.assertTrue(any("inside a projected region (showcase) · refused" in l for l in report), report)

    def test_fragment_and_skeleton_are_skipped(self):
        report, counts = self.run_tool()
        self.assertTrue(any("no envelope line" in l for l in report), report)
        self.assertTrue(any("info-string says non-runnable" in l for l in report), report)
        self.assertEqual(counts["skipped"], 3, report)

    def test_dry_writes_nothing(self):
        report, counts = self.run_tool(dry=True)
        self.assertEqual(self.page.read_text(encoding="utf-8"), FIXTURE)
        self.assertEqual(counts["fixed"], 3, report)

    def test_projected_snippet_file_is_refused_whole(self):
        report: list[str] = []
        _, counts = mod.process_file(self.page, self.nika, False, report, rel="snippets/_canon.mdx")
        self.assertEqual(self.page.read_text(encoding="utf-8"), FIXTURE)
        self.assertEqual(counts["skipped"], 6, report)


def nine_key_binary() -> str | None:
    """A real `nika` that REFUSES `nika: v1` · None when the machine has none."""
    nika = os.environ.get("NIKA_BIN") or shutil.which("nika")
    if not nika or not pathlib.Path(nika).exists():
        return None
    with tempfile.NamedTemporaryFile("w", suffix=".nika.yaml", delete=False) as f:
        f.write('nika: v1\nworkflow:\n  id: probe\ntasks:\n  t:\n    infer:\n      prompt: "x"\n      model: mock/echo\n')
        probe = f.name
    try:
        r = subprocess.run([nika, "check", probe], capture_output=True, text=True)
    finally:
        os.unlink(probe)
    return nika if r.returncode != 0 else None


REAL = nine_key_binary()


@unittest.skipUnless(REAL, "no nine-key `nika` on PATH / NIKA_BIN · the real-oracle proof is skipped")
class OracleTests(Base):
    """The same fixture through the real binary · the proof the stub stands in for."""

    def setUp(self):
        super().setUp()
        self.nika = REAL

    def test_real_binary_repairs_the_three_authored_fences(self):
        before = strip_blocks(FIXTURE)
        report, counts = self.run_tool()
        after = self.page.read_text(encoding="utf-8")
        self.assertEqual(strip_blocks(after), before)
        self.assertEqual(counts["fixed"], 3, report)
        self.assertEqual(counts["STOP"], 0, report)
        self.assertIn(EXPECTED_PLAIN, after)
        self.assertIn(EXPECTED_INDENTED, after)
        self.assertIn(EXPECTED_TITLE, after)
        # the projected region is untouched even by the real binary
        self.assertIn("nika: v1\nworkflow:\n  id: projected-flow", after)


if __name__ == "__main__":
    unittest.main()
