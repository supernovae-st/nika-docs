#!/usr/bin/env python3
"""The released snapshot is one atomic projection, tested without network."""

from __future__ import annotations

import json
import contextlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
COMMIT = "c4cdbeafb" + "1" * 31
SNAPSHOT = b'''{/* Leave this comment, including version: "comment", untouched. */}
export const STATUS = {
  head: "unrelated-main-head",
  version: "0.116.1",
  engineSha: "previous",
  firstCommand: "nika try previous",
  providers: 99,
  cratesWorkspace: 56,
  futureField: { keep: [1, "two"] },
  lastUpdated: "2000-01-01"
};
'''


class SnapshotTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()
        (self.root / "snippets").mkdir()
        self.snap = self.root / "snippets/_status-snapshot.mdx"
        self.snap.write_bytes(SNAPSHOT)
        self.snap.chmod(0o640)
        for name in ("mintlify-snapshot.sh", "mintlify_snapshot.py", "first_command.py"):
            if (SCRIPTS / name).exists():
                shutil.copy2(SCRIPTS / name, self.root / "scripts" / name)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        # No ambient nika, gh, credentials, user config, or network tools.
        for name in ("bash", "dirname", "python3", "perl", "date"):
            target = shutil.which(name)
            assert target, name
            (self.bin_dir / name).symlink_to(target)
        self.log = self.root / "probes.jsonl"
        self.receipts = self.root / "receipts.json"
        self.data = {
            "release": {"tagName": "v0.116.2", "publishedAt": "2026-09-01T12:34:56Z",
                        "isDraft": False, "isPrerelease": False},
            "ref": {"ref": "refs/tags/v0.116.2", "object": {"type": "commit", "sha": COMMIT}},
            "banner": "nika 0.116.2 (c4cdbeafb)",
            "catalog": {"catalog_version": 1, "providers": [{"id": "local"}, {"id": "cloud"}]},
            "screen": "Welcome\nNext:\n  nika new hello\n",
        }
        common = (
            f"#!{sys.executable}\nimport json, pathlib, sys\n"
            f"data=json.loads(pathlib.Path({str(self.receipts)!r}).read_text())\n"
            f"with pathlib.Path({str(self.log)!r}).open('a') as log:\n"
            f" log.write(json.dumps({{'program': pathlib.Path(sys.argv[0]).name, 'args': sys.argv[1:], "
            f"'snapshot': pathlib.Path({str(self.snap)!r}).read_text()}})+'\\n')\n"
        )
        self.selected = self.root / "selected-nika"
        self.selected.write_text(common + '''
args=sys.argv[1:]
key = 'banner' if args == ['--version'] else 'catalog' if args == ['catalog','--json'] else 'screen'
if data.get('fail') == key: sys.exit(17)
value=data[key]
print(json.dumps(value) if isinstance(value, (dict,list)) else value)
''')
        self.selected.chmod(0o755)
        self.gh = self.bin_dir / "gh"
        self.gh.write_text(common + '''
if data.get('fail') == 'gh': sys.exit(19)
if sys.argv[1:3] == ['release','view']:
 value=data['release']
 if '--jq' in sys.argv: value=value.get('tagName', '') if isinstance(value,dict) else value
else:
 value=data.get('annotated') if '/git/tags/' in sys.argv[-1] else data['ref']
print(json.dumps(value) if isinstance(value, (dict,list)) else value)
''')
        self.gh.chmod(0o755)
        self.env = {"PATH": str(self.bin_dir), "HOME": str(self.root), "NIKA_BIN": str(self.selected)}

    def run_projection(self) -> subprocess.CompletedProcess[str]:
        self.receipts.write_text(json.dumps(self.data))
        return subprocess.run([str(self.bin_dir / "bash"), str(self.root / "scripts/mintlify-snapshot.sh")],
                              cwd=self.root, env=self.env, text=True, capture_output=True, timeout=5)

    def assert_red_unchanged(self) -> None:
        before = self.snap.read_bytes()
        result = self.run_projection()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.snap.read_bytes(), before, result.stdout + result.stderr)
        self.assertNotIn("GREEN", result.stdout)

    def test_happy_path_projects_one_binary_and_preserves_everything_else(self) -> None:
        result = self.run_projection()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        expected = SNAPSHOT.replace(b'"0.116.1"', b'"0.116.2"').replace(b'"previous"', b'"c4cdbeafb"')
        expected = expected.replace(b'"nika try previous"', b'"nika new hello"').replace(b'providers: 99', b'providers: 2')
        expected = expected.replace(b'"2000-01-01"', b'"2026-09-01"')
        self.assertEqual(self.snap.read_bytes(), expected)
        self.assertEqual(self.snap.stat().st_mode & 0o777, 0o640)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertTrue(all(call["snapshot"].encode() == SNAPSHOT for call in calls), "a probe saw a partial write")
        self.assertEqual([call["args"] for call in calls if call["program"] == "selected-nika"],
                         [["--version"], ["catalog", "--json"], []])
        self.assertIn("not", result.stdout.lower())
        self.assertIn("provenance", result.stdout.lower())

    def test_missing_binary_never_returns_green_or_updates_release_fields(self) -> None:
        self.env.pop("NIKA_BIN")
        self.assert_red_unchanged()

    def test_invalid_explicit_binary_never_falls_back_to_path(self) -> None:
        (self.bin_dir / "nika").symlink_to(self.selected)
        for explicit in ("", "nika", "./selected-nika", str(self.root / "missing"), str(self.root)):
            with self.subTest(explicit=explicit):
                self.env["NIKA_BIN"] = explicit
                self.assert_red_unchanged()

    def test_nonexecutable_binary_is_refused(self) -> None:
        self.selected.chmod(0o644)
        self.assert_red_unchanged()

    def test_path_selection_works_without_an_explicit_override(self) -> None:
        self.env.pop("NIKA_BIN")
        (self.bin_dir / "nika").symlink_to(self.selected)
        result = self.run_projection()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(b'engineSha: "c4cdbeafb"', self.snap.read_bytes())

    def test_candidate_version_dirty_or_malformed_banner_never_changes_bytes(self) -> None:
        for banner in ("nika 0.118.1 (71397bf28)", "nika 0.116.2 (c4cdbeafb-dirty)",
                       "nika 0.116.2 (c4cdbeafb) dirty", "nika 0.116.2 (unknown)",
                       "nika 0.116.2", "unrelated (c4cdbeafb)", "nika 0.116.2 (deadbeef)"):
            with self.subTest(banner=banner):
                self.data["banner"] = banner
                self.assert_red_unchanged()

    def test_unavailable_probe_leaves_the_entire_snapshot_unchanged(self) -> None:
        for probe in ("gh", "banner", "catalog", "screen"):
            with self.subTest(probe=probe):
                self.data["fail"] = probe
                self.assert_red_unchanged()

    def test_malformed_release_metadata_or_tag_commit_is_refused(self) -> None:
        release = self.data["release"]
        for invalid in ("not-json", [], {}, {**release, "tagName": "main"},
                        {**release, "tagName": "v0.116.2-rc.1"}, {**release, "isDraft": True},
                        {**release, "isPrerelease": True}, {**release, "publishedAt": "not-a-date"}):
            with self.subTest(release=invalid):
                self.data["release"] = invalid
                self.assert_red_unchanged()
        self.data["release"] = release
        for invalid in ({}, {"ref": "refs/tags/wrong", "object": {"type": "commit", "sha": COMMIT}},
                        {"ref": "refs/tags/v0.116.2", "object": {"type": "commit", "sha": "unknown"}}):
            with self.subTest(ref=invalid):
                self.data["ref"] = invalid
                self.assert_red_unchanged()

    def test_annotated_release_tag_is_resolved_to_its_commit(self) -> None:
        self.data["ref"]["object"] = {"type": "tag", "sha": "a" * 40}
        self.data["annotated"] = {"object": {"type": "commit", "sha": COMMIT}}
        result = self.run_projection()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_bad_catalog_or_missing_first_command_leaves_bytes_unchanged(self) -> None:
        catalog = self.data["catalog"]
        for invalid in ("not-json", [], {}, {"providers": "abc"}, {"providers": {}},
                        {"providers": []}, {"providers": [None]},
                        {"providers": catalog["providers"]},
                        {**catalog, "catalog_version": 2}, {**catalog, "catalog_version": True},
                        {**catalog, "providers": [{"id": ""}]},
                        {**catalog, "providers": [{"id": "local"}, {"id": "local"}]}):
            with self.subTest(catalog=invalid):
                self.data["catalog"] = invalid
                self.assert_red_unchanged()
        self.data["catalog"] = catalog
        self.data["screen"] = "welcome, but no known next-command label"
        self.assert_red_unchanged()

    def test_missing_or_duplicate_owned_field_is_not_a_partial_projection(self) -> None:
        for malformed in (SNAPSHOT.replace(b'  firstCommand: "nika try previous",\n', b''),
                          SNAPSHOT.replace(b'  providers: 99,', b'  providers: 99,\n  providers: 100,')):
            self.snap.write_bytes(malformed)
            self.assert_red_unchanged()

    def run_transaction(self, probe_hook=None, replace_hook=None) -> tuple[int, str]:
        import mintlify_snapshot as writer
        self.receipts.write_text(json.dumps(self.data))
        output = io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, self.env, clear=True))
            stack.enter_context(patch.object(writer, "SNAPSHOT", self.snap))
            stack.enter_context(contextlib.redirect_stdout(output))
            stack.enter_context(contextlib.redirect_stderr(output))
            if probe_hook:
                stack.enter_context(patch.object(writer.subprocess, "run", side_effect=probe_hook))
            if replace_hook:
                stack.enter_context(patch.object(writer.os, "replace", side_effect=replace_hook))
            status = writer.main()
        return status, output.getvalue()

    def test_every_probe_timeout_is_bounded_and_preserves_snapshot_bytes(self) -> None:
        real_run = subprocess.run
        for stage in ("release", "ref", "banner", "catalog", "screen"):
            seen = []

            def run(arguments, **kwargs):
                seen.append(arguments)
                self.assertGreater(kwargs["timeout"], 0)
                self.assertLessEqual(kwargs["timeout"], 15)
                self.assertTrue(kwargs["check"])
                if len(arguments) == 1:
                    actual = "screen"
                elif arguments[1:3] == ["release", "view"]:
                    actual = "release"
                elif arguments[1] == "api":
                    actual = "ref"
                elif arguments[1:] == ["--version"]:
                    actual = "banner"
                else:
                    actual = "catalog"
                if actual == stage:
                    raise subprocess.TimeoutExpired(arguments, kwargs["timeout"])
                return real_run(arguments, **kwargs)

            with self.subTest(stage=stage):
                status, output = self.run_transaction(probe_hook=run)
                self.assertEqual(status, 1, output)
                self.assertIn("timed out", output)
                self.assertEqual(self.snap.read_bytes(), SNAPSHOT)
                self.assertTrue(seen)
                self.assertEqual(list(self.snap.parent.glob(f".{self.snap.name}.*")), [])

    def test_atomic_replace_is_the_only_write_and_failure_removes_staging_file(self) -> None:
        def fail_replace(staged, target):
            self.assertEqual(Path(target), self.snap)
            self.assertEqual(Path(staged).parent, self.snap.parent)
            self.assertEqual(self.snap.read_bytes(), SNAPSHOT)
            self.assertIn(b'providers: 2', Path(staged).read_bytes())
            raise OSError("injected atomic replace failure")

        status, output = self.run_transaction(replace_hook=fail_replace)
        self.assertEqual(status, 1, output)
        self.assertIn("atomic replace failure", output)
        self.assertEqual(self.snap.read_bytes(), SNAPSHOT)
        self.assertEqual(list(self.snap.parent.glob(f".{self.snap.name}.*")), [])

    def test_concurrent_snapshot_change_is_preserved_and_reported(self) -> None:
        real_run = subprocess.run
        changed = SNAPSHOT.replace(b'unrelated-main-head', b'another-writer-head')

        def run(arguments, **kwargs):
            result = real_run(arguments, **kwargs)
            if len(arguments) == 1:
                self.snap.write_bytes(changed)
            return result

        status, output = self.run_transaction(probe_hook=run)
        self.assertEqual(status, 1, output)
        self.assertIn("snapshot changed", output)
        self.assertEqual(self.snap.read_bytes(), changed)
        self.assertEqual(list(self.snap.parent.glob(f".{self.snap.name}.*")), [])

    def test_binary_replacement_during_probes_is_refused(self) -> None:
        real_run = subprocess.run

        def run(arguments, **kwargs):
            result = real_run(arguments, **kwargs)
            if len(arguments) == 1:
                self.selected.write_bytes(self.selected.read_bytes() + b'\n# replaced\n')
            return result

        status, output = self.run_transaction(probe_hook=run)
        self.assertEqual(status, 1, output)
        self.assertIn("binary changed", output)
        self.assertEqual(self.snap.read_bytes(), SNAPSHOT)

    def test_crlf_and_unrelated_text_are_preserved_without_normalization(self) -> None:
        self.snap.write_bytes(SNAPSHOT.replace(b'\n', b'\r\n'))
        result = self.run_projection()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.snap.read_bytes().count(b'\r\n'), SNAPSHOT.count(b'\n'))

    def test_cyclic_annotated_tag_is_bounded_and_refused(self) -> None:
        self.data["ref"]["object"] = {"type": "tag", "sha": "a" * 40}
        self.data["annotated"] = {"object": {"type": "tag", "sha": "a" * 40}}
        self.assert_red_unchanged()
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertLessEqual(len(calls), 7)


if __name__ == "__main__":
    unittest.main()
