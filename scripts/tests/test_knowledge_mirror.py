import copy
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
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
    def test_rejected_candidate_leaves_admitted_source_and_pages_unchanged(self):
        duplicate=copy.deepcopy(self.data)
        duplicate['words'].append(copy.deepcopy(duplicate['words'][0]))
        cases=[
            ('invalid-json','{invalid',False,'JSONDecodeError'),
            ('duplicate-identity',json.dumps(duplicate),False,'Duplicate canonical identity'),
            ('unreviewed-retirement',json.dumps(self.data),True,'explicit removal review'),
        ]
        for name,candidate,retired,reason in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                root=Path(folder)
                for directory in ['scripts','snippets/data','reference/language']:
                    (root/directory).mkdir(parents=True,exist_ok=True)
                for relative in ['scripts/knowledge-mirror.py','snippets/data/knowledge-taxonomy.json',
                                 'snippets/data/language-reference.json','docs.json']:
                    shutil.copyfile(ROOT/relative,root/relative)
                admitted=root/'snippets/data/language-reference.json'
                nav=root/'docs.json'
                page=root/('reference/language/retired.mdx' if retired else 'reference/language/overview.mdx')
                page.write_text('previously admitted page\n')
                before={p:p.read_bytes() for p in [admitted,nav,page]}
                source=root/'candidate.json';source.write_text(candidate)
                result=subprocess.run([sys.executable,str(root/'scripts/knowledge-mirror.py'),
                                       '--write','--source',str(source)],capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0)
                self.assertIn(reason,result.stderr)
                for path,content in before.items():
                    self.assertEqual(path.read_bytes(),content,f'{name} changed {path.name}')
    def test_valid_candidate_is_imported_and_rendered(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for directory in ['scripts','snippets/data']:
                (root/directory).mkdir(parents=True,exist_ok=True)
            for relative in ['scripts/knowledge-mirror.py','snippets/data/knowledge-taxonomy.json',
                             'snippets/data/language-reference.json','docs.json']:
                shutil.copyfile(ROOT/relative,root/relative)
            candidate=json.dumps(self.data)
            source=root/'candidate.json';source.write_text(candidate)
            result=subprocess.run([sys.executable,str(root/'scripts/knowledge-mirror.py'),
                                   '--write','--source',str(source)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual((root/'snippets/data/language-reference.json').read_text(),candidate)
            for relative,expected in mirror.render(self.data).items():
                self.assertEqual((root/relative).read_text(),expected)
    def test_current_owner_changes_and_new_templates_are_not_hidden_by_valid_old_pin(self):
        import tempfile,hashlib
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'schemas').mkdir();(root/'templates').mkdir()
            path=root/'schemas/workflow.schema.json';path.write_bytes(b'{}')
            snapshot={'inputs':{'schemas/workflow.schema.json':hashlib.sha256(b'{}').hexdigest()}}
            verifier.verify_current_source(snapshot,root)
            path.write_bytes(b'{"properties":{}}')
            with self.assertRaisesRegex(ValueError,'Owner advanced'):verifier.verify_current_source(snapshot,root)
            path.write_bytes(b'{}');(root/'templates/new.nika').write_text('nika: new')
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
    def test_inline_code_keeps_braces_and_prose_escapes_stray_braces(self):
        self.assertEqual(mirror.code_span('${{ inputs.X }}'),'`${{ inputs.X }}`')
        self.assertIn('`${{ inputs.X }}`',mirror.md_prose('Typed workflow inputs · ${{ inputs.X }} · caller.'))
        self.assertNotIn('&#123;',mirror.md_prose('Typed workflow inputs · ${{ inputs.X }} · caller.'))
        self.assertIn('&#123;not-cel&#125;',mirror.md_prose('ordinary {not-cel} prose'))
        self.assertNotIn('{not-cel}',mirror.md_prose('ordinary {not-cel} prose'))
    def test_inputs_page_does_not_leak_entities_in_cel_or_dump_json_in_a_cell(self):
        page=mirror.render(self.data)['reference/language/words/inputs.mdx']
        self.assertIn('`${{ inputs.X }}`',page)
        self.assertNotIn('$&#123;',page)
        self.assertIn('```json',page)
        self.assertIn('<details>',page)
        self.assertIn('source-versus-implementation',page)
        self.assertNotRegex(page,r'\| additionalProperties \| &#123;')
        self.assertIn('\n  "type":',page)
    def test_code_span_keeps_backticks_and_pipes_leave_the_table(self):
        self.assertIn('`',mirror.code_span('a`b'))
        self.assertIn('a`b',mirror.code_span('a`b'))
        word=copy.deepcopy(self.data['words'][0])
        word['name']='pipe_field';word['id']='language:word:pipe_field';word['docsPath']='reference/language/words/pipe_field'
        word['contracts']=[{'pointer':'/properties/pipe_field','context':'/','required':False,'siblings':[],
            'declaration':{'type':'string','pattern':'a|b','enum':['x|y']}}]
        data=copy.deepcopy(self.data);data['words'].append(word)
        page=mirror.render(data)['reference/language/words/pipe_field.mdx']
        self.assertNotRegex(page,r'\| pattern \| `')
        self.assertIn('declaration below',page)
        self.assertIn('a|b',page)
    def test_md_prose_nested_ticks_pipes_cel_and_jsx_like(self):
        src='see `` `nested` `` and ${{ inputs.X }} and {Not.JSX} and `a|b`'
        out=mirror.md_prose(src)
        self.assertIn('nested',out)
        self.assertIn('`${{ inputs.X }}`',out)
        self.assertIn('&#123;Not.JSX&#125;',out)
        self.assertNotIn('{Not.JSX}',out)
        self.assertIn('a|b',out)
        self.assertNotIn('$&#123;',out)
        # Inner backtick of a double-delimited span survives.
        self.assertIn('`` `nested` ``',out)
    def test_representative_pages_compile_as_mdx(self):
        import subprocess, tempfile
        runtime=ROOT/'scripts'/'tests'/'mdx-runtime'
        compiler=runtime/'compile-mdx.mjs'
        modules=runtime/'node_modules'/'@mdx-js'/'mdx'
        if not modules.exists():
            inst=subprocess.run(['npm','ci'],cwd=runtime,capture_output=True,text=True,timeout=120)
            self.assertEqual(inst.returncode,0,inst.stderr)
        missing=subprocess.run(['node',str(compiler)],cwd=runtime,capture_output=True,text=True)
        self.assertNotEqual(missing.returncode,0)
        self.assertIn('usage:',missing.stderr)
        pages={
            'inputs.mdx':mirror.render(self.data)['reference/language/words/inputs.mdx'],
            'hostile.mdx':'# H\n\n'+mirror.md_prose('CEL ${{ inputs.X }} ticks `` `x` `` jsx {Nope} pipe `a|b`')+'\n',
        }
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name,body in pages.items():
                path=root/name;path.write_text(body)
                result=subprocess.run(['node',str(compiler),str(path)],
                    cwd=runtime,capture_output=True,text=True,timeout=60)
                self.assertEqual(result.returncode,0,name+'\n'+result.stderr+result.stdout)
            bad=root/'bad.mdx';bad.write_text('# H\n\n{this is not {valid mdx\n')
            broken=subprocess.run(['node',str(compiler),str(bad)],
                cwd=runtime,capture_output=True,text=True,timeout=60)
            self.assertNotEqual(broken.returncode,0)
            self.assertTrue(broken.stderr or broken.stdout)
    def test_link_audit_handles_underscores_and_rejects_missing_targets(self):
        import tempfile, subprocess
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            names=['page_'+str(i) for i in range(20)]
            for name in names:(root/(name+'.mdx')).write_text('Reference')
            (root/'docs.json').write_text(json.dumps({'navigation':{'pages':names}}))
            (root/'snippets/data').mkdir(parents=True)
            routes=root/'snippets/data/documentation-navigation.json'
            routes.write_text(json.dumps({'legacyGuides':{'/docs':'page_1'}}))
            page=root/'page_0.mdx';page.write_text('[Other](/page_1)')
            command=['python3',str(ROOT/'scripts/link-audit.py')]
            self.assertEqual(subprocess.run(command,cwd=root,capture_output=True).returncode,0)
            page.write_text('[Missing](/page_missing)')
            self.assertNotEqual(subprocess.run(command,cwd=root,capture_output=True).returncode,0)
            for link in ['https://nika.sh/docs', 'https://www.nika.sh/language/words/test', 'https://docs.nika.sh/page_missing']:
                page.write_text('[Documentation]('+link+')')
                self.assertNotEqual(subprocess.run(command,cwd=root,capture_output=True).returncode,0,link)
            page.write_text('[Documentation](https://docs.nika.sh/page_1)')
            self.assertEqual(subprocess.run(command,cwd=root,capture_output=True).returncode,0)
            routes.write_text(json.dumps({'legacyGuides':{'/docs':'page_missing'}}))
            self.assertNotEqual(subprocess.run(command,cwd=root,capture_output=True).returncode,0)
    def test_new_unclassified_context_is_reported(self):
        self.data['words'][0]['contracts'][0]['context']='/$defs/brandNewDomain'
        self.data['words'][0]['contracts']=self.data['words'][0]['contracts'][:1]
        with self.assertRaisesRegex(ValueError,'Unclassified schema context'):mirror.sections(self.data)
    def test_external_mcp_catalog_is_distinct_from_nika_oracle(self):
        taxonomy=json.loads((ROOT/'snippets/data/knowledge-taxonomy.json').read_text())
        self.assertEqual(taxonomy['families']['mcp-server']['guide'],'reference/mcp-catalog')
        self.assertNotEqual(taxonomy['families']['mcp-server']['guide'],'reference/mcp-server')
    def test_taxonomy_guides_exist_and_are_in_navigation(self):
        taxonomy=json.loads((ROOT/'snippets/data/knowledge-taxonomy.json').read_text())
        nav=json.loads((ROOT/'docs.json').read_text());serialized=json.dumps(nav['navigation'])
        for entry in [*taxonomy['families'].values(),*taxonomy['destinations'].values()]:
            self.assertTrue((ROOT/(entry['guide']+'.mdx')).is_file())
            self.assertIn(json.dumps(entry['guide']),serialized)
if __name__=='__main__':unittest.main()
