import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('publication_audit', ROOT/'scripts/publication-audit.py')
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

class PublicationBoundary(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        self.write('scripts/public-assets.json','{}')
        self.write('snippets/data/knowledge-taxonomy.json',json.dumps({'families':{'words':{'visibility':'public-concept'}},'destinations':{}}))
        self.write('introduction.mdx','Write a workflow. Use nika mcp to validate its language. Open source contracts stay public.')
    def tearDown(self):self.temp.cleanup()
    def write(self,path,text):
        target=self.root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text)
    def test_product_language_and_public_oracle_remain_allowed(self):
        self.assertEqual(audit.audit(self.root),[])
    def test_hidden_or_unlisted_page_is_still_public(self):
        self.write('unlisted.mdx','Nika Lab private guide')
        self.assertTrue(audit.audit(self.root))
    def test_navigation_and_json_are_scanned(self):
        self.write('docs.json',json.dumps({'navigation':['guides/lab-agents']}))
        self.assertTrue(audit.audit(self.root))
    def test_encoded_private_link_is_detected(self):
        self.write('introduction.mdx','https://github.com/supernovae-st/nika%2Dlab')
        self.assertTrue(audit.audit(self.root))
    def test_json_escaped_private_name_is_detected(self):
        self.write('docs.json',r'{"title":"Nika\u0020Lab"}')
        self.assertTrue(audit.audit(self.root))
    def test_unreviewed_data_export_is_refused_without_keywords(self):
        self.write('snippets/data/extra.json','{"items":["opaque"]}')
        self.assertTrue(audit.audit(self.root))
    def test_mixed_and_unknown_audiences_are_refused(self):
        for visibility in ('mixed-review-required','internal-evidence','unknown'):
            self.write('snippets/data/knowledge-taxonomy.json',json.dumps({'families':{'entry':{'visibility':visibility}},'destinations':{}}))
            self.assertTrue(audit.audit(self.root))
    def test_application_routes_are_not_a_public_taxonomy(self):
        self.write('snippets/data/knowledge-taxonomy.json',json.dumps({'families':{},'destinations':{'planning':{'guide':'introduction'}}}))
        self.assertTrue(audit.audit(self.root))
    def test_screenshot_requires_review(self):
        self.write('images/capture.svg','<svg/>')
        self.assertTrue(audit.audit(self.root))
    def test_archive_cannot_hide_capture(self):
        self.write('snapshot.gz','opaque')
        self.assertTrue(audit.audit(self.root))
    def test_symlink_cannot_bypass_audit(self):
        (self.root/'copied.mdx').symlink_to(self.root/'introduction.mdx')
        self.assertTrue(audit.audit(self.root))
    def test_real_public_repository(self):
        self.assertEqual(audit.audit(ROOT),[])

if __name__=='__main__':unittest.main()
