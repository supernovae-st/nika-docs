#!/usr/bin/env python3
"""Offline regressions for pagination, stale projections and untrusted prose."""
import copy
import json
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


class MergeTests(unittest.TestCase):
    def test_real_proposal_flow_waits_for_ci_before_exact_head_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous = Path.cwd()
            import os
            os.chdir(tmp)
            try:
                path = Path('snippets/data/releases.json')
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps({'releases': [{'tag':'v0.120.1'}]}))
                for verdict in ['success', 'failure']:
                    calls = []
                    def command(*args):
                        calls.append(args)
                        if args[:4] == ('git','diff','--cached','--name-only'): return 'changelog/releases.mdx'
                        if args[:2] == ('git','write-tree'): return 'b' * 40
                        if args[:2] == ('git','ls-remote'): return ''
                        if args[:2] == ('git','rev-parse'): return 'a' * 40
                        if args[:3] == ('gh','pr','list'): return '[{"number":7}]'
                        if args[:3] == ('gh','pr','view'):
                            return json.dumps({'state':'OPEN','isCrossRepository':False,'baseRefName':'main',
                                               'headRefOid':'a'*40,'files':[{'path':'changelog/releases.mdx'}]})
                        return ''
                    def remote(endpoint, *args):
                        calls.append((endpoint, *args))
                        if endpoint.startswith('actions/workflows/'):
                            return {'workflow_runs':[{'id':1,'head_sha':'a'*40,
                                    'head_branch':'nika-release-heal/v0.120.1-'+'b'*12,
                                    'created_at':'9999-12-31T00:00:00Z','status':'completed',
                                    'conclusion':verdict,'html_url':'https://github.com/check'}]}
                        if endpoint.startswith('actions/runs/'):
                            return {'jobs':[{'name':n,'conclusion':'success'} for n in proposal.REQUIRED]}
                        return {'merged':True,'sha':'c'*40}
                    with patch.object(proposal, 'run', side_effect=command), patch.object(proposal, 'api', side_effect=remote):
                        if verdict == 'success': proposal.main()
                        else:
                            with self.assertRaisesRegex(ValueError, 'checks failed'): proposal.main()
                    merges = [c for c in calls if c[0] == 'pulls/7/merge']
                    self.assertEqual(len(merges), int(verdict == 'success'))
                    if merges:
                        self.assertIn('sha='+'a'*40, merges[0])
                        self.assertLess(next(i for i,c in enumerate(calls) if c[0].startswith('actions/runs/')),
                                        calls.index(merges[0]))
            finally:
                os.chdir(previous)

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
