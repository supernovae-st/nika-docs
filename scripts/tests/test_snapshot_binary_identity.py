#!/usr/bin/env python3
"""A mismatched binary must not mutate the published release snapshot."""
import json
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
            for name in ('mintlify-snapshot.sh', 'mintlify_snapshot.py', 'first_command.py'):
                shutil.copy2(ROOT / 'scripts' / name, root / 'scripts' / name)
            original = 'export const STATUS = {version: "0.118.7", engineSha: "f3a31a6ee"};\n'
            snapshot = root / 'snippets/_status-snapshot.mdx'
            snapshot.write_text(original)
            gh = root / 'gh'
            gh.write_text('#!/bin/sh\nif [ "$1" = release ]; then\n' + "printf '%s\\n' '" + json.dumps({'tagName': 'v0.118.7', 'isDraft': False, 'isPrerelease': False, 'publishedAt': '2026-09-05T17:58:35Z'}) + "'\nelse\n" + "printf '%s\\n' '" + json.dumps({'ref': 'refs/tags/v0.118.7', 'object': {'type': 'commit', 'sha': 'f3a31a6ee00766e4b010379c535bca994631d637'}}) + "'\nfi\n")
            gh.chmod(0o755)
            binary = root / 'nika'
            binary.write_text('#!/bin/sh\nprintf "nika 0.116.2 (c4cdbeafb)\\n"\n')
            binary.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'], NIKA_BIN=str(binary))
            result = subprocess.run(['bash', str(root / 'scripts/mintlify-snapshot.sh')], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('does not match released version', result.stderr)
            self.assertEqual(snapshot.read_text(), original)


if __name__ == '__main__':
    unittest.main()
