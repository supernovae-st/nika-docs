#!/usr/bin/env python3
"""The one bare-screen reader must propagate process failure and time out."""

import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from first_command import read_first_command


class FirstCommandTest(unittest.TestCase):
    def test_supported_screen_shapes_still_use_the_same_reader(self) -> None:
        for screen in ("Next:\n\n nika new hello # comment\n", "Next:\n nika new hello\n"):
            with patch("first_command.subprocess.run", return_value=subprocess.CompletedProcess([], 0, screen)) as run:
                self.assertTrue(read_first_command("/selected/nika").startswith("nika "))
                self.assertTrue(run.call_args.kwargs["check"])
                self.assertGreater(run.call_args.kwargs["timeout"], 0)
                self.assertLessEqual(run.call_args.kwargs["timeout"], 15)
                self.assertNotIn("GH_TOKEN", run.call_args.kwargs["env"])

    def test_retired_screen_is_not_a_current_release_contract(self) -> None:
        screen = "start here\n nika try 01-hello\n"
        with patch("first_command.subprocess.run", return_value=subprocess.CompletedProcess([], 0, screen)):
            self.assertEqual(read_first_command("/selected/nika"), "")

    def test_timeout_propagates_with_a_finite_deadline(self) -> None:
        with patch("first_command.subprocess.run", side_effect=subprocess.TimeoutExpired("nika", 10)) as run:
            with self.assertRaises(subprocess.TimeoutExpired):
                read_first_command("/selected/nika")
            self.assertGreater(run.call_args.kwargs["timeout"], 0)
            self.assertLessEqual(run.call_args.kwargs["timeout"], 15)

    def test_a_failed_binary_cannot_supply_a_valid_looking_first_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "nika"
            binary.write_text(f"#!{sys.executable}\nprint('Next:\\n nika new hello')\nraise SystemExit(7)\n")
            binary.chmod(0o755)
            with self.assertRaises(subprocess.CalledProcessError):
                read_first_command(str(binary))


if __name__ == "__main__":
    unittest.main()
