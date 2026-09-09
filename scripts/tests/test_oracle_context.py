"""Native regression cases: scaffolds and project-relative MCP configuration."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
BIN=os.environ.get('NIKA_BIN') or shutil.which('nika')
@unittest.skipUnless(BIN,'released nika binary required')
class OracleContextTests(unittest.TestCase):
 def run_page(self,text):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'scripts').mkdir();shutil.copy(ROOT/'scripts/oracle-sweep.py',root/'scripts/oracle-sweep.py');(root/'case.mdx').write_text(text)
   return subprocess.run(['python3',str(root/'scripts/oracle-sweep.py')],env={**os.environ,'NIKA_BIN':BIN},capture_output=True,text=True)
 def test_mcp_registry_is_required_and_resolved_in_the_example_project(self):
  page='''```yaml workflow.nika.yaml
nika: mcp-example
permits: {tools: ["mcp:filesystem/read_file"]}
tasks:
  read:
    invoke:
      tool: mcp:filesystem/read_file
      args: {path: ./data/article.txt}
outputs: {result: "${{ tasks.read.output }}"}
```
'''
  self.assertNotEqual(self.run_page(page).returncode,0)
  configured=page+'```json .nika/mcp_servers.json\n{"mcp_servers_format":1,"servers":{"filesystem":{"command":"node","args":["server.js"]}}}\n```'
  result=self.run_page(configured);self.assertEqual(result.returncode,0,result.stdout+result.stderr)
 def test_skeleton_accepts_only_slot_errors(self):
  page='''```yaml example.nika.yaml skeleton
nika: skeleton-example
model: mock/echo
tasks:
  draft:
    infer:
      prompt: "<SLOT: your prompt>"
      max_tokens: 10
outputs: {result: "${{ tasks.draft.output }}"}
```
'''
  result=self.run_page(page);self.assertEqual(result.returncode,0,result.stdout+result.stderr)
  self.assertNotEqual(self.run_page(page.replace('infer:','made_up_verb:')).returncode,0)
if __name__=='__main__':unittest.main()
