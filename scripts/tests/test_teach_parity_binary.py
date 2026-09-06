#!/usr/bin/env python3
"""Every teach-parity probe must judge the explicitly selected engine."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "teach-parity.py"
SPEC = importlib.util.spec_from_file_location("teach_parity_binary", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class TeachParityBinaryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        self.log = self.root / "calls.txt"
        self.selected = self.root / "candidate-engine"
        self.selected.write_text(
            f"#!{sys.executable}\n"
            "import pathlib, sys\n"
            f"with pathlib.Path({str(self.log)!r}).open('a') as log:\n"
            "    log.write(' '.join(sys.argv[1:]) + '\\n')\n"
            "if sys.argv[1:] == ['--help', '--all']:\n"
            "    print('Commands:\\n  run  Execute\\n\\nOptions:')\n"
            "elif sys.argv[1:] not in (['run', '--help'], ['catalog', '--help']):\n"
            "    sys.exit(2)\n",
            encoding="utf-8",
        )
        self.selected.chmod(0o755)
        self.shadow_dir = self.root / "path-bin"
        self.shadow_dir.mkdir()
        self.shadow = self.shadow_dir / "nika"
        self.shadow.write_text("#!/bin/sh\nexit 17\n", encoding="utf-8")
        self.shadow.chmod(0o755)
        self.docs = self.root / "docs"
        self.docs.mkdir()
        self.cli = self.docs / "cli.mdx"
        self.cli.write_text("| `nika run` | Execute |\n", encoding="utf-8")
        (self.docs / "guide.mdx").write_text(
            "```sh\nnika run flow.nika.yaml\nnika catalog\n```\n", encoding="utf-8"
        )

    def run_gate(self, env: dict[str, str]) -> tuple[int, str]:
        output = io.StringIO()
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(GATE, "DOCS_ROOT", self.docs),
            patch.object(GATE, "CLI_MDX", self.cli),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(output),
        ):
            status = GATE.main()
        return status, output.getvalue()

    def test_explicit_binary_wins_over_a_different_path_binary_for_both_directions(self) -> None:
        status, output = self.run_gate({"NIKA_BIN": str(self.selected), "PATH": str(self.shadow_dir)})
        self.assertEqual(status, 0, output)
        self.assertIn("GREEN", output)
        self.assertEqual(self.log.read_text().splitlines(), ["--help --all", "run --help", "catalog --help"])

    def test_explicit_binary_runs_without_nika_on_path(self) -> None:
        status, output = self.run_gate({"NIKA_BIN": str(self.selected), "PATH": ""})
        self.assertEqual(status, 0, output)
        self.assertNotIn("SKIP", output)
        self.assertTrue(self.log.exists(), output)

    def test_missing_explicit_binary_is_red_without_path_fallback(self) -> None:
        status, output = self.run_gate({"NIKA_BIN": str(self.root / "missing"), "PATH": str(self.shadow_dir)})
        self.assertEqual(status, 1, output)
        self.assertIn("NIKA_BIN", output)
        self.assertNotIn("SKIP", output)

    def test_relative_explicit_binary_is_refused(self) -> None:
        status, output = self.run_gate({"NIKA_BIN": "./candidate-engine", "PATH": ""})
        self.assertEqual(status, 1, output)
        self.assertIn("absolute", output)

    def test_path_fallback_is_used_when_no_explicit_binary_was_set(self) -> None:
        self.shadow.write_text(self.selected.read_text(), encoding="utf-8")
        status, output = self.run_gate({"PATH": str(self.shadow_dir)})
        self.assertEqual(status, 0, output)
        self.assertEqual(self.log.read_text().splitlines(), ["--help --all", "run --help", "catalog --help"])

    def test_failed_top_level_help_cannot_report_green(self) -> None:
        status, output = self.run_gate({"NIKA_BIN": str(self.shadow), "PATH": str(self.shadow_dir)})
        self.assertEqual(status, 1, output)
        self.assertIn("RED", output)
        self.assertNotIn("GREEN", output)

    def test_empty_command_inventory_cannot_report_green(self) -> None:
        self.selected.write_text("#!/bin/sh\nprintf 'nika run  run a file\\n'\n", encoding="utf-8")
        status, output = self.run_gate({"NIKA_BIN": str(self.selected), "PATH": ""})
        self.assertEqual(status, 1, output)
        self.assertIn("did not list any subcommands", output)

    def test_retired_new_form_is_still_rejected_without_mutating_the_docs_checkout(self) -> None:
        (self.docs / "guide.mdx").write_text("Run `nika new --from chain`.\n", encoding="utf-8")
        status, output = self.run_gate({"NIKA_BIN": str(self.selected), "PATH": ""})
        self.assertEqual(status, 1, output)
        self.assertIn("retired `nika new --from`", output)

    def test_timed_out_inventory_is_red_not_a_skip(self) -> None:
        with patch.object(GATE.subprocess, "run", side_effect=GATE.subprocess.TimeoutExpired("nika", 10)) as run:
            status, output = self.run_gate({"NIKA_BIN": str(self.selected), "PATH": ""})
        self.assertEqual(status, 1, output)
        self.assertIn("RED", output)
        self.assertNotIn("SKIP", output)
        self.assertEqual(run.call_args.kwargs["timeout"], 10)


if __name__ == "__main__":
    unittest.main()
