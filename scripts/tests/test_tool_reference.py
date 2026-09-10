import copy,importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('tools',ROOT/'scripts/tool-reference.py');tools=importlib.util.module_from_spec(spec);spec.loader.exec_module(tools)
class ToolReferenceTests(unittest.TestCase):
    def setUp(self):self.source=json.loads((ROOT/'snippets/data/tool-reference.json').read_text())
    def test_exhaustive_deterministic(self):
        out=tools.render(self.source);self.assertEqual(out,tools.render(copy.deepcopy(self.source)))
        self.assertEqual(len(json.loads(out['snippets/data/tool-mirror.json'])['entries']),len(self.source['registry']))
    def test_missing_contract_refused(self):
        self.source['registry'].append(dict(id='nika:unknown'))
        with self.assertRaisesRegex(ValueError,'membership differ'):tools.render(self.source)
    def test_duplicate_id_refused(self):
        self.source['registry'].append(self.source['registry'][0])
        with self.assertRaises(ValueError):tools.render(self.source)
    def test_mdx_preserves_code_and_escapes_expressions(self):
        text='Text {unsafe} <script>\n`{literal}`\n```yaml\ncondition: "${{ true }}"\n```'
        out=tools.mdx(text,'a'*40)
        self.assertIn('&#123;unsafe&#125;',out);self.assertNotIn('<script>',out)
        self.assertIn('`{literal}`',out);self.assertIn('```yaml illustration',out);self.assertIn('${{ true }}',out)
    def test_cross_references_exist(self):
        out=tools.render(self.source)['reference/tools/assert.mdx']
        for path in ['reference/language/words/args','concepts/security','guides/templates']:
            self.assertIn('/'+path,out);self.assertTrue((ROOT/(path+'.mdx')).exists())
        self.assertNotIn('https://nika.sh/',out)
if __name__=='__main__':unittest.main()
