#!/usr/bin/env python3
"""Offline release transport/verifier doubles; never contacts GitHub."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
TAG = "v0.116.2"
COMMIT = "c4cdbeafb" + "1" * 31
WORKFLOW = "supernovae-st/nika/.github/workflows/release.yml"


class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.tools = self.root / "tools"
        self.tools.mkdir()
        self.dest = self.root / "installed"
        self.log = self.root / "calls.jsonl"
        self.fixture = self.root / "fixture.json"
        self.archive = self.root / "archive.tar.gz"
        self.checksums = self.root / "checksums"
        self.asset = "nika-linux-x64-0.116.2.tar.gz"
        self.binary = (f"#!{sys.executable}\nimport json, pathlib, sys\n"
                       f"with pathlib.Path({str(self.log)!r}).open('a') as f: f.write(json.dumps(['nika']+sys.argv[1:])+'\\n')\n"
                       "args=sys.argv[1:]\n"
                       "if args == ['--version']: print('nika 0.116.2 (c4cdbeafb)')\n"
                       "elif args == ['catalog','--json']: print(json.dumps({'catalog_version':1,'providers':[{'id':'local'}]}))\n"
                       "else: print('Welcome\\nNext:\\n  nika new hello')\n").encode()
        self.make_archive()
        self.data = {
            "release": {"tagName": TAG, "isDraft": False, "isPrerelease": False,
                        "publishedAt": "2026-08-31T21:51:24Z"},
            "commit": COMMIT, "sourceRef": f"refs/tags/{TAG}", "workflow": WORKFLOW,
        }
        common = (f"#!{sys.executable}\nimport json, pathlib, shutil, sys\n"
                  f"data=json.loads(pathlib.Path({str(self.fixture)!r}).read_text())\n"
                  "args=sys.argv[1:]\n"
                  f"with pathlib.Path({str(self.log)!r}).open('a') as f: f.write(json.dumps([pathlib.Path(sys.argv[0]).name]+args)+'\\n')\n")
        self.write_tool("gh", common + f'''
if args[:2] == ['release','view']:
 if data.get('fail') == 'metadata': sys.exit(9)
 print(json.dumps(data['release']))
elif args[0] == 'api':
 print(json.dumps({{'ref': 'refs/tags/'+data['release']['tagName'], 'object': {{'type':'commit','sha':data['commit']}}}}))
elif args[:2] == ['attestation','verify']:
 expected = {{'--repo':'supernovae-st/nika',
             '--source-ref':data['sourceRef'], '--source-digest':data['commit'],
             '--cert-identity':'https://github.com/'+data['workflow']+'@'+data['sourceRef'],
             '--predicate-type':'https://slsa.dev/provenance/v1'}}
 for key, value in expected.items():
  if key not in args or args[args.index(key)+1] != value: sys.exit(10)
 if data.get('fail') == 'attestation': sys.exit(11)
 print('verified')
else: sys.exit(12)
''')
        self.write_tool("curl", common + f'''
if data.get('fail') == 'download': sys.exit(22)
url=args[-1]
source={str(self.checksums)!r} if url.endswith('/SHA256SUMS') else {str(self.archive)!r}
shutil.copyfile(source, args[args.index('--output')+1])
''')
        self.env = {"PATH": str(self.tools), "HOME": str(self.root)}

    def write_tool(self, name, content):
        path = self.tools / name
        path.write_text(content)
        path.chmod(0o755)

    def make_archive(self, extra=None, binary=None):
        with tarfile.open(self.archive, "w:gz", format=tarfile.USTAR_FORMAT) as archive:
            for name, body in [("nika", self.binary if binary is None else binary),
                               ("completions/nika.bash", b"completion")]:
                info = tarfile.TarInfo(name)
                info.mode = 0o755
                info.size = len(body)
                archive.addfile(info, io.BytesIO(body))
            if extra:
                archive.addfile(extra, io.BytesIO(b"x" * extra.size) if extra.isreg() else None)
        self.checksums.write_text(f"{hashlib.sha256(self.archive.read_bytes()).hexdigest()}  {self.asset}\n")

    def prepare(self):
        self.data['release'].setdefault('assets', [
            {"name": name, "size": path.stat().st_size, "state": "uploaded",
             "url": f"https://github.com/supernovae-st/nika/releases/download/{TAG}/{name}"}
            for name, path in [(self.asset, self.archive), ('SHA256SUMS', self.checksums)]])
        self.fixture.write_text(json.dumps(self.data))

    def run_install(self, *extra):
        self.prepare()
        return subprocess.run([sys.executable, str(SCRIPTS / "install_release.py"),
                               '--dest', str(self.dest), '--platform', 'linux-x64', *extra],
                              env=self.env, cwd=self.root, capture_output=True, text=True, timeout=10)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def assert_red(self, *extra):
        result = self.run_install(*extra)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('NIKA_BIN=', result.stdout)
        self.assertFalse(self.dest.exists())
        self.assertFalse(any(c[0] == 'nika' for c in self.calls()))
        return result

    def test_verified_exact_release_emits_absolute_binary_after_verification(self):
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(dict(line.split('=', 1) for line in result.stdout.splitlines()),
                         {'NIKA_TAG': TAG, 'NIKA_BIN': str(self.dest / 'nika')})
        self.assertEqual((self.dest / 'nika').read_bytes(), self.binary)
        calls = self.calls()
        attest = next(i for i, c in enumerate(calls) if c[1:3] == ['attestation','verify'])
        self.assertGreater(next(i for i, c in enumerate(calls) if c[0] == 'nika'), attest)
        releases = [c for c in calls if c[1:3] == ['release','view']]
        self.assertEqual(len(releases), 1)
        for call in [c for c in calls if c[0] == 'curl']:
            for flag in ('--max-time', '--connect-timeout', '--max-filesize', '--max-redirs', '--proto', '--proto-redir'):
                self.assertIn(flag, call)
            self.assertIn(f'/releases/download/{TAG}/', call[-1])
        self.assertEqual((self.dest.stat().st_mode & 0o777), 0o700)

    def test_explicit_tag_is_exact_and_never_latest(self):
        result = self.run_install('--tag', TAG)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(TAG, next(c for c in self.calls() if c[1:3] == ['release','view']))

    def test_wrong_checksum_fails_before_attestation_or_execution(self):
        self.checksums.write_text(f"{'0'*64}  {self.asset}\n")
        self.assert_red()
        self.assertFalse(any(c[1:3] == ['attestation','verify'] for c in self.calls()))

    def test_missing_duplicate_or_malformed_checksum_fails(self):
        for content in ('', f"{'a'*64}  other.tar.gz\n", self.checksums.read_text()*2, f"bad  {self.asset}\n"):
            with self.subTest(content=content):
                self.checksums.write_text(content)
                self.data['release'].pop('assets', None)
                self.assert_red()

    def test_wrong_provenance_and_unavailable_attestation_fail_before_unpacking(self):
        for key, value in [('workflow', WORKFLOW.replace('release.yml','ci.yml')),
                           ('sourceRef','refs/heads/main'), ('fail','attestation')]:
            with self.subTest(key=key):
                before = self.data.copy()
                self.data[key] = value
                self.assert_red()
                self.data = before

    def test_unpublished_unstable_and_invalid_tags_fail(self):
        original = self.data['release'].copy()
        for key, value in [('isDraft',True), ('isPrerelease',True), ('publishedAt',None),
                           ('tagName','v0.116.2-rc.1'), ('tagName','v0.116'),
                           ('tagName','../../evil'), ('tagName','v00.116.2')]:
            with self.subTest(key=key, value=value):
                self.data['release'] = {**original, key:value}
                self.assert_red()

    def test_missing_duplicate_wrong_url_or_oversize_asset_fails(self):
        self.prepare()
        assets = self.data['release']['assets']
        for bad in [[], assets[1:], assets + assets[:1],
                    [{**assets[0], 'url':'https://evil.example/asset'}, assets[1]],
                    [{**assets[0], 'size': 1024**3}, assets[1]]]:
            with self.subTest(assets=bad):
                self.data['release']['assets'] = bad
                self.assert_red()

    def test_requested_tag_mismatch_and_invalid_requested_tag_fail(self):
        for tag in ('v0.116.1', '../escape', 'latest', 'v1.2'):
            with self.subTest(tag=tag):
                self.assert_red('--tag', tag)

    def test_transport_failure_is_not_success(self):
        for stage in ('metadata','download'):
            self.data['fail'] = stage
            self.assert_red()

    def test_archive_traversal_absolute_links_devices_and_duplicates_fail(self):
        for name, kind in [('../escape', tarfile.REGTYPE), ('/tmp/escape', tarfile.REGTYPE),
                           ('completions/../../escape', tarfile.REGTYPE), ('nika', tarfile.SYMTYPE),
                           ('evil', tarfile.LNKTYPE), ('evil', tarfile.CHRTYPE), ('nika', tarfile.REGTYPE)]:
            with self.subTest(name=name, kind=kind):
                member = tarfile.TarInfo(name)
                member.type = kind
                member.linkname = '/tmp/escape' if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE) else ''
                self.make_archive(extra=member)
                self.data['release'].pop('assets', None)
                self.assert_red()
        self.assertFalse((self.root / 'escape').exists())

    def test_existing_or_symlink_destination_is_never_overwritten(self):
        self.dest.mkdir()
        marker = self.dest / 'nika'
        marker.write_bytes(b'keep')
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(marker.read_bytes(), b'keep')
        marker.unlink()
        self.dest.rmdir()
        self.dest.symlink_to(self.tools, target_is_directory=True)
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.dest.is_symlink())

    def test_no_attestation_means_even_invalid_archive_is_not_opened(self):
        self.archive.write_bytes(b'not a tar')
        self.checksums.write_text(f"{hashlib.sha256(self.archive.read_bytes()).hexdigest()}  {self.asset}\n")
        self.data['fail'] = 'attestation'
        result = self.assert_red()
        self.assertIn('attestation', result.stderr)

    def test_install_then_projection_pins_binary_and_latest_race_preserves_snapshot(self):
        from test_mintlify_snapshot import SNAPSHOT
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        (self.root / 'scripts').mkdir()
        (self.root / 'snippets').mkdir()
        for name in ('mintlify_snapshot.py', 'first_command.py'):
            shutil.copy2(SCRIPTS / name, self.root / 'scripts' / name)
        snapshot = self.root / 'snippets/_status-snapshot.mdx'
        env = {**self.env, 'NIKA_BIN': str(self.dest / 'nika')}
        for latest, expected in [(TAG, 0), ('v0.116.3', 1)]:
            with self.subTest(latest=latest):
                snapshot.write_bytes(SNAPSHOT)
                self.data['release']['tagName'] = latest
                self.fixture.write_text(json.dumps(self.data))
                result = subprocess.run([sys.executable, str(self.root / 'scripts/mintlify_snapshot.py')],
                                        env=env, cwd=self.root, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                if expected:
                    self.assertIn('does not match released version', result.stderr)
                    self.assertEqual(snapshot.read_bytes(), SNAPSHOT)
                else:
                    self.assertIn(b'version: "0.116.2"', snapshot.read_bytes())
                    self.assertIn(b'firstCommand: "nika new hello"', snapshot.read_bytes())

    def test_subprocess_timeouts_are_bounded_and_fail_closed(self):
        sys.path.insert(0, str(SCRIPTS))
        import install_release as installer
        self.prepare()
        real_run = subprocess.run
        for stage in ('metadata', 'ref', 'download', 'attestation', 'banner'):
            def run(args, **kwargs):
                self.assertTrue(kwargs['check'])
                self.assertGreater(kwargs['timeout'], 0)
                self.assertLessEqual(kwargs['timeout'], 100)
                current = ('metadata' if args[1:3] == ['release', 'view'] else
                           'ref' if args[1] == 'api' else
                           'download' if args[0] == 'curl' else
                           'attestation' if args[1:3] == ['attestation', 'verify'] else 'banner')
                if current == stage:
                    raise subprocess.TimeoutExpired(args, kwargs['timeout'])
                return real_run(args, **kwargs)
            with self.subTest(stage=stage), patch.dict(os.environ, self.env, clear=True), \
                    patch.object(installer.subprocess, 'run', side_effect=run):
                with self.assertRaises(subprocess.TimeoutExpired):
                    installer.install(self.dest, None, 'linux-x64')
                self.assertFalse(self.dest.exists())

    def test_decompression_limit_prevents_binary_execution(self):
        sys.path.insert(0, str(SCRIPTS))
        import install_release as installer
        self.prepare()
        with patch.dict(os.environ, self.env, clear=True), patch.object(installer, 'MAX_UNPACKED', 64):
            with self.assertRaisesRegex(ValueError, 'decompression bounds'):
                installer.install(self.dest, None, 'linux-x64')
        self.assertFalse(self.dest.exists())
        self.assertFalse(any(c[0] == 'nika' for c in self.calls()))


class WiringTest(unittest.TestCase):
    def test_all_three_callers_share_the_verified_installer(self):
        gate = (SCRIPTS.parent / '.github/workflows/gate.yml').read_text()
        heal = (SCRIPTS.parent / '.github/workflows/release-heal.yml').read_text()
        self.assertEqual(gate.count('python3 scripts/install_release.py'), 2)
        self.assertEqual(heal.count('python3 scripts/install_release.py'), 1)
        for workflow in (gate, heal):
            self.assertNotIn('sudo ', workflow)
            self.assertNotIn('curl -fsSL "${dl}', workflow)
            self.assertIn('attestations: read', workflow)
            self.assertIn('"$GITHUB_ENV"', workflow)
        for name in ('test_mintlify_snapshot.py','test_first_command.py','test_install_release.py'):
            self.assertIn(name, gate)

    def test_heal_validates_before_normal_branch_pr_without_bypass(self):
        heal = (SCRIPTS.parent / '.github/workflows/release-heal.yml').read_text()
        self.assertNotIn('HEAL_DEPLOY_KEY', heal)
        self.assertNotIn('ssh-key:', heal)
        self.assertIn('pull-requests: write', heal)
        self.assertNotIn('One SDK 0.116', (SCRIPTS.parent / '.github/workflows/gate.yml').read_text())
        self.assertIn('gh pr create', heal)
        self.assertIn('HEAD:refs/heads/', heal)
        self.assertIn('NIKA_TAG', heal)
        self.assertLess(heal.index('scripts/install_release.py'), heal.index('bash scripts/mintlify-snapshot.sh'))
        for check in ('scripts/link-audit.py','scripts/count-drift-gate.py','scripts/teach-parity.py','scripts/oracle-sweep.py'):
            self.assertLess(heal.index(check), heal.index('git push'))
        self.assertNotIn('--force', heal)


if __name__ == '__main__':
    unittest.main()
