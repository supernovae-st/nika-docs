#!/usr/bin/env python3
"""Offline regressions for pagination, stale projections and untrusted prose."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import release_catalog as catalog
import release_proposal as proposal


def release(tag="v0.120.1", **changes):
    return dict({"tag_name": tag, "name": tag, "draft": False, "prerelease": False,
                 "published_at": "2026-09-18T22:35:56Z", "assets": [{}], "body": "Notes",
                 "html_url": f"https://github.com/{catalog.REPO}/releases/tag/{tag}"}, **changes)


class CatalogTests(unittest.TestCase):
    def test_complete_multiline_highlights_are_inert_and_bounded(self):
        body = '- **A complete\nchange heading.** Details.\n- **A second <Tag>{value}.** More.\n- **Third.**\n- **Fourth.**'
        data = catalog.fetch(lambda _: [release(body=body)])
        self.assertEqual(data['releases'][0]['highlights'][0], 'A complete change heading.')
        page = catalog.render(data)
        self.assertIn('A complete change heading.', page)
        self.assertNotIn('<Tag>', page)
        self.assertNotIn('{value}', page)
        self.assertNotIn('Fourth.', page)

    def test_rendered_text_preserves_flags_and_inert_prose(self):
        for value in ['nika check --json', '<Tag>{value}</Tag> [x](javascript:x)',
                      'quotes " and backslashes \\ with `code`', 'Unicode — « »']:
            with self.subTest(value=value):
                rendered = catalog.text(value)
                self.assertTrue(rendered.startswith('{"') and rendered.endswith('"}'))
                self.assertEqual(json.loads(rendered[1:-1]), value)
                self.assertNotIn('<Tag>', rendered)
                self.assertNotIn('{value}', rendered)
        self.assertIn('  - {"nika check --json"}', catalog.render(
            catalog.fetch(lambda _: [release(body='- **nika check --json**')])) )

    def test_pagination_filters_and_semver(self):
        first = [release(f"v0.{i}.0") for i in range(100)]
        pages = [first, [release(), release("v0.121.0", draft=True), release("v0.122.0", prerelease=True)]]
        calls = []
        def fetcher(endpoint):
            calls.append(endpoint)
            return pages.pop(0)
        data = catalog.fetch(fetcher)
        self.assertEqual(len(data['releases']), 101)
        self.assertEqual(data['releases'][0]['tag'], 'v0.120.1')
        self.assertIn('page=2', calls[-1])

    def test_no_assets_is_not_installable_claim(self):
        data = catalog.fetch(lambda _: [release(assets=[])])
        self.assertIn('No attached assets', catalog.render(data))
        self.assertIn('release record only', catalog.render(data))

    def test_remote_title_is_inert_mdx(self):
        data = catalog.fetch(lambda _: [release(name='<script>{danger}</script> [x](javascript:x)')])
        page = catalog.render(data)
        self.assertNotIn('<script>', page)
        self.assertNotIn('{danger}', page)
        self.assertNotIn('](javascript:', page)

    def test_invalid_response_rejected(self):
        for rows in ({'message': 'rate limited'}, [], [release(), release()],
                     [release(published_at='yesterday')], [release(html_url='https://evil.test')],
                     [release(draft=None)], [release(tag_name='v1.0.0-rc.1')]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                catalog.fetch(lambda _: rows)

    def test_refresh_failure_keeps_both_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog.project(root, refresh=True, fetcher=lambda _: [release()])
            before = {p: (root/p).read_bytes() for p in [catalog.DATA, catalog.PAGE]}
            def fail(_):
                raise subprocess.CalledProcessError(1, 'gh')
            with self.assertRaises(subprocess.CalledProcessError):
                catalog.project(root, refresh=True, fetcher=fail)
            self.assertEqual(before, {p: (root/p).read_bytes() for p in before})

    def test_check_is_read_only_and_detects_note_edits_and_new_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog.project(root, refresh=True, fetcher=lambda _: [release()])
            before = (root/catalog.DATA).read_bytes()
            for rows in ([release(body='Edited notes')], [release(), release('v0.121.0')]):
                with self.assertRaisesRegex(ValueError, 'drift'):
                    catalog.project(root, refresh=True, check=True, fetcher=lambda _: rows)
                self.assertEqual(before, (root/catalog.DATA).read_bytes())
            self.assertEqual(catalog.project(root, refresh=True, fetcher=lambda _: [release()]), (1, []))
            (root/catalog.PAGE).write_text('stale page')
            with self.assertRaisesRegex(ValueError, 'changelog/releases.mdx'):
                catalog.project(root, check=True)

    def test_malformed_snapshot_rejected(self):
        data = catalog.fetch(lambda _: [release(), release('v0.119.0')])
        for key, value in [('url', 'https://other.test'), ('assetCount', -1), ('notesSha256', 'x'), ('name', 'line\nbreak')]:
            altered = copy.deepcopy(data)
            altered['releases'][0][key] = value
            with self.assertRaises(ValueError):
                catalog.render(altered)
        data['releases'].reverse()
        with self.assertRaises(ValueError):
            catalog.render(data)


HEAD = 'a' * 40
BRANCH = 'nika-release-heal/v0.120.1-' + 'b' * 12


def gate_record(event, conclusion='success', status='completed', **changes):
    return dict({'id': 1 if event == 'pull_request' else 2, 'head_sha': HEAD,
                 'head_branch': BRANCH, 'event': event, 'path': '.github/workflows/gate.yml',
                 'repository': {'full_name': proposal.REPO},
                 'head_repository': {'full_name': proposal.REPO},
                 'created_at': '9999-12-31T00:00:00Z', 'status': status, 'conclusion': conclusion,
                 'pull_requests': [], 'html_url': 'https://github.com/check'}, **changes)


def pr_view(**changes):
    return json.dumps(dict({'state': 'OPEN', 'isCrossRepository': False, 'baseRefName': 'main',
                            'headRefOid': HEAD, 'files': [{'path': 'changelog/releases.mdx'}]}, **changes))


def gates(dispatch=None, pr=None, jobs=None):
    def remote(endpoint, *args):
        if endpoint.startswith('actions/workflows/'):
            record = pr if 'event=pull_request' in endpoint else dispatch
            return {'workflow_runs': [record] if record else []}
        if endpoint.startswith('actions/runs/'):
            return {'jobs': jobs if jobs is not None else
                    [{'name': name, 'conclusion': 'success'} for name in proposal.REQUIRED]}
        return {'merged': True, 'sha': 'c' * 40}
    return remote


class MergeTests(unittest.TestCase):
    def run_flow(self, remote, command_extra=None, monotonic=None):
        """Drive proposal.main() with offline doubles; return (calls, error)."""
        with tempfile.TemporaryDirectory() as tmp:
            previous = Path.cwd()
            os.chdir(tmp)
            try:
                path = Path('snippets/data/releases.json')
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps({'releases': [{'tag': 'v0.120.1'}]}))
                calls = []

                def command(*args):
                    calls.append(args)
                    if command_extra:
                        answer = command_extra(args)
                        if answer is not None:
                            return answer
                    if args[:4] == ('git', 'diff', '--cached', '--name-only'):
                        return 'changelog/releases.mdx'
                    if args[:2] == ('git', 'write-tree'):
                        return 'b' * 40
                    if args[:2] == ('git', 'ls-remote'):
                        return ''
                    if args[:2] == ('git', 'rev-parse'):
                        return HEAD
                    if args[:3] == ('gh', 'pr', 'list'):
                        return '[{"number":7}]'
                    if args[:3] == ('gh', 'pr', 'view'):
                        return pr_view()
                    return ''

                def tracked(endpoint, *args):
                    calls.append((endpoint, *args))
                    return remote(endpoint, *args)

                clock = (patch.object(proposal.time, 'monotonic', return_value=0) if monotonic is None
                         else patch.object(proposal.time, 'monotonic', side_effect=monotonic))
                with patch.object(proposal, 'run', side_effect=command), \
                        patch.object(proposal, 'api', side_effect=tracked), \
                        patch.object(proposal.time, 'sleep'), clock:
                    error = None
                    try:
                        proposal.main()
                    except (ValueError, subprocess.CalledProcessError) as caught:
                        error = caught
                return calls, error
            finally:
                os.chdir(previous)

    @staticmethod
    def merge_calls(calls):
        return [c for c in calls if c[0] == 'pulls/7/merge']

    @staticmethod
    def approve_calls(calls):
        return [c for c in calls if c[:2] == ('gh', 'api') and str(c[-1]).endswith('/approve')]

    def test_flow_waits_for_both_gates_before_exact_head_merge(self):
        for verdict in ['success', 'failure']:
            with self.subTest(verdict=verdict):
                calls, error = self.run_flow(gates(dispatch=gate_record('workflow_dispatch', verdict),
                                                   pr=gate_record('pull_request')))
                merges = self.merge_calls(calls)
                self.assertEqual(len(merges), int(verdict == 'success'))
                if verdict == 'failure':
                    self.assertIsInstance(error, ValueError)
                    self.assertIn('checks failed', str(error))
                else:
                    self.assertIsNone(error)
                    self.assertIn('sha=' + HEAD, merges[0])
                    jobs = [i for i, c in enumerate(calls) if str(c[0]).startswith('actions/runs/')]
                    self.assertEqual(len(jobs), 2)  # every required job in BOTH gates
                    self.assertLess(max(jobs), calls.index(merges[0]))

    def test_held_pull_request_gate_is_approved_after_identity_validation(self):
        # The real PR #195 gate reported held as completed + action_required;
        # the legacy spelling puts action_required in status. Both must be
        # approved — never mistaken for a completed failure.
        for status, conclusion in [('completed', 'action_required'), ('action_required', None)]:
            with self.subTest(status=status, conclusion=conclusion):
                approved = []

                def command_extra(args):
                    if args[:2] == ('gh', 'api') and str(args[-1]).endswith('/approve'):
                        approved.append(args)
                        return ''  # the approve endpoint answers 201 with an empty body
                    return None

                def remote(endpoint, *args):
                    if 'event=pull_request' in endpoint:
                        record = (gate_record('pull_request') if approved
                                  else gate_record('pull_request', conclusion, status))
                        return {'workflow_runs': [record]}
                    return gates(dispatch=gate_record('workflow_dispatch'))(endpoint, *args)

                calls, error = self.run_flow(remote, command_extra)
                self.assertIsNone(error)
                self.assertEqual(len(approved), 1)
                self.assertEqual(approved[0][-1], f'repos/{proposal.REPO}/actions/runs/1/approve')
                viewed = next(i for i, c in enumerate(calls) if c[:3] == ('gh', 'pr', 'view'))
                self.assertLess(viewed, calls.index(approved[0]))  # identity checked before approval
                self.assertLess(calls.index(approved[0]), calls.index(self.merge_calls(calls)[0]))

    def test_approve_gate_revalidates_exact_run_identity(self):
        record = gate_record('pull_request', 'action_required', 'completed')
        rejected = [{'status': 'completed', 'conclusion': 'success'},  # not held
                    {'status': 'in_progress', 'conclusion': None},     # not held
                    {'head_sha': 'd' * 40}, {'head_branch': 'main'}, {'event': 'workflow_dispatch'},
                    {'path': '.github/workflows/other.yml'},
                    {'repository': {'full_name': 'fork/nika-docs'}},
                    {'head_repository': {'full_name': 'fork/nika-docs'}}]
        with patch.object(proposal, 'run') as mocked_run:
            for changes in rejected:
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    proposal.approve_gate('7', HEAD, BRANCH, dict(record, **changes))
            mocked_run.assert_not_called()  # identity fails before any API call
        calls = []

        def command(*args):
            calls.append(args)
            if args[:3] == ('gh', 'pr', 'view'):
                return pr_view()
            return ''

        with patch.object(proposal, 'run', side_effect=command):
            proposal.approve_gate('7', HEAD, BRANCH, record)
        self.assertEqual(calls[-1][-1], f'repos/{proposal.REPO}/actions/runs/1/approve')

    def test_wrong_proposal_identity_is_never_approved_or_merged(self):
        for view in [pr_view(isCrossRepository=True), pr_view(headRefOid='d' * 40),
                     pr_view(state='MERGED'), pr_view(files=[{'path': 'scripts/release_proposal.py'}])]:
            with self.subTest(view=view):
                def command_extra(args, view=view):
                    if args[:3] == ('gh', 'pr', 'view'):
                        return view
                    return None

                calls, error = self.run_flow(
                    gates(dispatch=gate_record('workflow_dispatch'),
                          pr=gate_record('pull_request', 'action_required', 'completed')), command_extra)
                self.assertIsInstance(error, ValueError)
                self.assertEqual(self.approve_calls(calls), [])
                self.assertEqual(self.merge_calls(calls), [])

    def test_gate_selection_requires_exact_same_repository_identity(self):
        base = gate_record('pull_request', None, 'action_required')

        def select(runs, **kwargs):
            return proposal.select_run(runs, head=HEAD, branch=BRANCH, event='pull_request', **kwargs)

        self.assertEqual(select([base])['id'], 1)
        # The empty pull_requests payload is ignored — never required or trusted.
        self.assertEqual(select([dict(base, pull_requests=[{'number': 9999}])])['id'], 1)
        for changes in [{'head_sha': 'd' * 40}, {'head_branch': 'main'}, {'event': 'push'},
                        {'path': '.github/workflows/other.yml'},
                        {'repository': {'full_name': 'fork/nika-docs'}},
                        {'head_repository': {'full_name': 'fork/nika-docs'}}, {'repository': None}]:
            with self.subTest(changes=changes):
                self.assertIsNone(select([dict(base, **changes)]))
        stale = dict(base, created_at='2000-01-01T00:00:00Z')
        self.assertIsNone(select([stale], since='2026-01-01T00:00:00Z'))
        self.assertEqual(select([dict(base, id=5), dict(base, id=9)])['id'], 9)

    def test_missing_pull_request_gate_times_out_without_merge(self):
        calls, error = self.run_flow(gates(dispatch=gate_record('workflow_dispatch')),
                                     monotonic=[0, 0, 2000])
        self.assertIsInstance(error, ValueError)
        self.assertIn('timed out', str(error))
        self.assertIn('missing', str(error))
        self.assertEqual(self.approve_calls(calls), [])
        self.assertEqual(self.merge_calls(calls), [])

    def test_failed_jobs_in_either_gate_block_the_merge(self):
        jobs = [{'name': name, 'conclusion': 'success'} for name in proposal.REQUIRED]
        jobs[0]['conclusion'] = 'failure'
        calls, error = self.run_flow(gates(dispatch=gate_record('workflow_dispatch'),
                                           pr=gate_record('pull_request'), jobs=jobs))
        self.assertIsInstance(error, ValueError)
        self.assertIn('gates must succeed', str(error))
        self.assertEqual(self.merge_calls(calls), [])

    def test_denied_approval_fails_closed(self):
        def command_extra(args):
            if args[:2] == ('gh', 'api') and str(args[-1]).endswith('/approve'):
                raise subprocess.CalledProcessError(1, args, '', 'gh: Forbidden (HTTP 403)')
            return None

        calls, error = self.run_flow(
            gates(dispatch=gate_record('workflow_dispatch'),
                  pr=gate_record('pull_request', 'action_required', 'completed')), command_extra)
        self.assertIsInstance(error, subprocess.CalledProcessError)
        self.assertEqual(self.merge_calls(calls), [])

    def test_subprocess_stderr_is_surfaced_without_secrets(self):
        failure = subprocess.CalledProcessError(
            1, ('gh', 'api'), output='',
            stderr='gh: Forbidden — https://x-access-token:ghs_ABCDEFGHIJKLMNOP@github.com (HTTP 403)')
        with patch.object(proposal.subprocess, 'run', side_effect=failure):
            with self.assertRaises(ValueError) as caught:
                proposal.run('gh', 'api', 'repos/x')
        message = str(caught.exception)
        self.assertIn('Forbidden', message)
        self.assertIn('REDACTED', message)
        self.assertNotIn('ghs_ABCDEFGHIJKLMNOP', message)
        self.assertNotIn('x-access-token', message)

    def test_only_generated_files_can_be_published(self):
        proposal.check_files(['changelog/releases.mdx'])
        for paths in ([], ['.github/workflows/gate.yml'], ['changelog/releases.mdx', 'README.md']):
            with self.assertRaises(ValueError):
                proposal.check_files(paths)

    def test_exact_same_repository_head_only(self):
        pr = {'state': 'OPEN', 'isCrossRepository': False, 'baseRefName': 'main',
              'headRefOid': 'abc', 'files': [{'path': 'changelog/releases.mdx'}]}
        proposal.check_pr(pr, 'abc')
        for key, value in [('state', 'CLOSED'), ('isCrossRepository', True), ('baseRefName', 'other'), ('headRefOid', 'other')]:
            with self.assertRaises(ValueError):
                proposal.check_pr({**pr, key: value}, 'abc')

    def test_every_gate_must_succeed(self):
        jobs = [{'name': name, 'conclusion': 'success'} for name in proposal.REQUIRED]
        proposal.check_jobs(jobs)
        with self.assertRaises(ValueError):
            proposal.check_jobs(jobs[:-1])
        for verdict in ['skipped', 'failure', 'cancelled', None]:
            with self.assertRaises(ValueError):
                proposal.check_jobs(jobs + [{'name': 'extra', 'conclusion': verdict}])


if __name__ == '__main__':
    unittest.main()
