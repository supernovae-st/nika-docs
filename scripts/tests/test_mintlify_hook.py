#!/usr/bin/env python3
"""An installed MDX parser's failure must survive the actual push command."""

from __future__ import annotations

import pathlib
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class MintlifyHookTest(unittest.TestCase):
    def run_hook(self, mint_exit: int | None) -> subprocess.CompletedProcess[str]:
        text = (ROOT / "lefthook.yml").read_text(encoding="utf-8")
        block = re.search(
            r"(?m)^    mint-broken-links:\n      run: >\n((?:        [^\n]*\n)+)",
            text,
        )
        self.assertIsNotNone(block, "exercise the real folded hook command")
        assert block is not None
        command = shlex.split(" ".join(line[8:] for line in block[1].splitlines()))
        self.assertEqual(command[:2], ["sh", "-c"])
        self.assertEqual(len(command), 3)
        shell = shutil.which("sh")
        self.assertIsNotNone(shell)
        assert shell is not None
        with tempfile.TemporaryDirectory() as directory:
            if mint_exit is not None:
                mint = pathlib.Path(directory) / "mint"
                mint.write_text(
                    f'#!{shell}\n[ "$*" = "broken-links" ] || exit 99\n'
                    f'echo parser-ran\nexit {mint_exit}\n',
                    encoding="utf-8",
                )
                mint.chmod(0o755)
            return subprocess.run(
                [shell, *command[1:]], env={"PATH": directory},
                text=True, capture_output=True, timeout=5,
            )

    def test_installed_parser_exit_code_is_preserved(self) -> None:
        for exit_code in (0, 17):
            with self.subTest(exit_code=exit_code):
                result = self.run_hook(exit_code)
                self.assertEqual(result.returncode, exit_code, result.stdout + result.stderr)
                self.assertIn("parser-ran", result.stdout)
                self.assertNotIn("SKIPPED", result.stdout + result.stderr)

    def test_missing_optional_parser_keeps_its_explicit_skip(self) -> None:
        result = self.run_hook(None)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("CLI absent", result.stdout)
        self.assertIn("SKIPPED", result.stdout)
        self.assertNotIn("parser-ran", result.stdout)


if __name__ == "__main__":
    unittest.main()
