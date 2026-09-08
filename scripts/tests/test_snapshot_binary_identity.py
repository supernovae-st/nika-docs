#!/usr/bin/env python3
"""A mismatched binary must not mutate the published release snapshot."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class SnapshotIdentity(unittest.TestCase):
    def test_mismatched_release_refuses_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'scripts').mkdir()
            (root / 'snippets').mkdir()
            shutil.copy2(ROOT / 'scripts/mintlify-snapshot.sh', root / 'scripts/mintlify-snapshot.sh')
            original = 'export const STATUS = {version: "0.118.7", engineSha: "f3a31a6ee"};\n'
            snapshot = root / 'snippets/_status-snapshot.mdx'
            snapshot.write_text(original)
            gh = root / 'gh'
            gh.write_text('#!/bin/sh\nprintf "v0.118.7\\n"\n')
            gh.chmod(0o755)
            binary = root / 'nika'
            binary.write_text('#!/bin/sh\nprintf "nika 0.116.2 (oldcommit)\\n"\n')
            binary.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'], NIKA_BIN=str(binary))
            result = subprocess.run(['bash', str(root / 'scripts/mintlify-snapshot.sh')], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('does not match release', result.stderr)
            self.assertEqual(snapshot.read_text(), original)


if __name__ == '__main__':
    unittest.main()
