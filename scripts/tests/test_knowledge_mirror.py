import copy
import importlib.util
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
def module(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/file);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
mirror=module('mirror','knowledge-mirror.py');verifier=module('verify','verify-knowledge-source.py')
class KnowledgeMirrorTests(unittest.TestCase):
    def setUp(self):self.data=json.loads((ROOT/'snippets/data/language-reference.json').read_text())
    def test_deterministic_and_every_identity_has_page(self):
        outputs=mirror.render(self.data)
        self.assertEqual(outputs,mirror.render(copy.deepcopy(self.data)))
        manifest=json.loads(outputs['snippets/data/knowledge-mirror.json'])
        for e in manifest['entries']:
            self.assertIn(e['path']+'.mdx',outputs);self.assertEqual(e['publication'],'not-verified')
    def test_duplicate_identity_refused(self):
        self.data['words'].append(copy.deepcopy(self.data['words'][0]))
        with self.assertRaises(ValueError):mirror.render(self.data)
    def test_current_owner_changes_and_new_templates_are_not_hidden_by_valid_old_pin(self):
        import tempfile,hashlib
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'schemas').mkdir();(root/'templates').mkdir()
            path=root/'schemas/workflow.schema.json';path.write_bytes(b'{}')
            snapshot={'inputs':{'schemas/workflow.schema.json':hashlib.sha256(b'{}').hexdigest()}}
            verifier.verify_current_source(snapshot,root)
            path.write_bytes(b'{"properties":{}}')
            with self.assertRaisesRegex(ValueError,'Owner advanced'):verifier.verify_current_source(snapshot,root)
            path.write_bytes(b'{}');(root/'templates/new.nika.yaml').write_text('nika: new')
            with self.assertRaisesRegex(ValueError,'Owner advanced'):verifier.verify_current_source(snapshot,root)
    def test_path_traversal_refused(self):
        self.data['words'][0]['docsPath']='../introduction'
        with self.assertRaises(ValueError):mirror.render(self.data)
    def test_new_schema_field_requires_reference(self):
        schema={'properties':{'one':{'type':'string'},'two':{'type':'boolean'}}}
        raw=json.dumps(schema).encode();import hashlib
        snapshot={'revision':'a'*40,'inputs':{'schemas/workflow.schema.json':hashlib.sha256(raw).hexdigest()},'words':[]}
        with self.assertRaisesRegex(ValueError,'Missing schema'):verifier.verify(snapshot,lambda rev,path:raw)
    def test_forged_declaration_refused(self):
        import hashlib
        raw=b'{"properties":{"one":{"type":"string"}}}'
        snapshot={'revision':'a'*40,'inputs':{'schemas/workflow.schema.json':hashlib.sha256(raw).hexdigest()},'words':[{'id':'language:word:one','name':'one','docsPath':'reference/language/words/one','contracts':[{'pointer':'/properties/one','context':'/','required':False,'declaration':{'type':'boolean'},'siblings':[]}],'examples':[]}]}
        with self.assertRaisesRegex(ValueError,'Declaration mismatch'):verifier.verify(snapshot,lambda rev,path:raw)
    def test_jitter_excerpt_and_context(self):
        page=mirror.render(self.data)['reference/language/words/jitter.mdx']
        self.assertIn('boolean',page);self.assertIn('```yaml illustration',page);self.assertIn('/reference/language/words/backoff_ms',page)
    def test_link_audit_handles_underscores_and_rejects_missing_targets(self):
        import tempfile, subprocess
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            names=['page_'+str(i) for i in range(20)]
            for name in names:(root/(name+'.mdx')).write_text('Reference')
            (root/'docs.json').write_text(json.dumps({'navigation':{'pages':names}}))
            page=root/'page_0.mdx';page.write_text('[Other](/page_1)')
            command=['python3',str(ROOT/'scripts/link-audit.py')]
            self.assertEqual(subprocess.run(command,cwd=root,capture_output=True).returncode,0)
            page.write_text('[Missing](/page_missing)')
            self.assertNotEqual(subprocess.run(command,cwd=root,capture_output=True).returncode,0)
    def test_new_unclassified_context_is_reported(self):
        self.data['words'][0]['contracts'][0]['context']='/$defs/brandNewDomain'
        self.data['words'][0]['contracts']=self.data['words'][0]['contracts'][:1]
        with self.assertRaisesRegex(ValueError,'Unclassified schema context'):mirror.sections(self.data)
    def test_taxonomy_guides_exist_and_are_in_navigation(self):
        taxonomy=json.loads((ROOT/'snippets/data/knowledge-taxonomy.json').read_text())
        nav=json.loads((ROOT/'docs.json').read_text());serialized=json.dumps(nav['navigation'])
        for entry in [*taxonomy['families'].values(),*taxonomy['destinations'].values()]:
            self.assertTrue((ROOT/(entry['guide']+'.mdx')).is_file())
            self.assertIn(json.dumps(entry['guide']),serialized)
if __name__=='__main__':unittest.main()
