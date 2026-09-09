#!/usr/bin/env python3
"""Verify the imported reference against Git objects at its named spec revision."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
ROOT = Path(__file__).resolve().parents[1]
def verify(snapshot, read_source):
    rev = snapshot['revision']
    if not re.fullmatch('[a-f0-9]{40}', rev): raise ValueError('Invalid revision')
    raw = {path: read_source(rev, path) for path in snapshot['inputs']}
    for path, data in raw.items():
        if hashlib.sha256(data).hexdigest() != snapshot['inputs'][path]: raise ValueError('Source hash mismatch: '+path)
    schema_path = 'schemas/workflow.schema.json'
    schema = json.loads(raw[schema_path]); expected = {}
    def walk(value, pointer=''):
        if isinstance(value, dict):
            props = value.get('properties', {})
            for name, decl in props.items():
                expected[pointer+'/properties/'+name] = (name, pointer or '/', name in value.get('required', []), decl, sorted(set(props)-{name}))
            maps=('properties','patternProperties','$defs','definitions','dependentSchemas')
            arrays=('allOf','anyOf','oneOf','prefixItems')
            singles=('items','contains','additionalProperties','unevaluatedProperties','unevaluatedItems','propertyNames','not','if','then','else')
            for key in maps:
                for name,child in value.get(key,{}).items():walk(child,pointer+'/'+key+'/'+name.replace('~','~0').replace('/','~1'))
            for key in arrays:
                for i,child in enumerate(value.get(key,[])):walk(child,pointer+'/'+key+'/'+str(i))
            for key in singles:
                if isinstance(value.get(key),dict):walk(value[key],pointer+'/'+key)
    walk(schema); seen = set(); ids = set()
    for word in snapshot['words']:
        name = word['name']
        if word['id'] != 'language:word:'+name or word['id'] in ids: raise ValueError('Invalid or duplicate identity')
        ids.add(word['id'])
        if word['docsPath'] != 'reference/language/words/'+name: raise ValueError('Invalid destination')
        for c in word['contracts']:
            pointer = c['pointer']; actual = (name,c['context'],c['required'],c['declaration'],c['siblings'])
            if pointer in seen or expected.get(pointer) != actual: raise ValueError('Declaration mismatch: '+pointer)
            seen.add(pointer)
        examples = []
        for path, data in sorted(raw.items()):
            if not path.startswith('templates/') or not path.endswith('.nika.yaml'): continue
            lines = data.decode().splitlines()
            hits = [i for i,line in enumerate(lines) if re.match(r'^\s*'+re.escape(name)+r'\s*:',line)]
            if not hits: continue
            first=hits[0];start=max(0,first-3);end=min(len(lines),first+7)
            examples.append(dict(path=path,line=first+1,startLine=start+1,endLine=end,excerpt='\n'.join(lines[start:end]),matchKind='literal-key-occurrence'))
        if examples != word['examples']: raise ValueError('Source excerpt or coverage mismatch: '+name)
    if seen != set(expected): raise ValueError('Missing schema declarations')
    return len(ids)
def main():
    p=argparse.ArgumentParser();p.add_argument('--spec-root',required=True,type=Path);p.add_argument('--current-source',action='store_true',help='Also require exact parity with the supplied owner checkout, including new/deleted templates');a=p.parse_args()
    snapshot=json.loads((ROOT/'snippets/data/language-reference.json').read_text())
    def read(rev,path): return subprocess.check_output(['git','show',f'{rev}:{path}'],cwd=a.spec_root)
    # The set of input files itself must be exhaustive, not only the listed hashes.
    tracked=subprocess.check_output(['git','ls-tree','-r','--name-only',snapshot['revision'],'--','templates','schemas/workflow.schema.json'],cwd=a.spec_root,text=True).splitlines()
    wanted={p for p in tracked if p=='schemas/workflow.schema.json' or re.fullmatch(r'templates/[^/]+\.nika\.yaml',p)}
    if wanted != set(snapshot['inputs']): raise SystemExit('Missing or unexpected source input')
    count=verify(snapshot,read)
    if a.current_source: verify_current_source(snapshot,a.spec_root)
    print(f'Verified {count} fields against pinned Git objects, including every declaration and source excerpt')
def verify_current_source(snapshot, root):
    files=[root/'schemas/workflow.schema.json',*sorted((root/'templates').glob('*.nika.yaml'))]
    observed={path.relative_to(root).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    if observed != snapshot['inputs']:
        changed=sorted(path for path in set(observed)|set(snapshot['inputs']) if observed.get(path)!=snapshot['inputs'].get(path))
        raise ValueError('Owner advanced beyond documentation snapshot: '+', '.join(changed))
if __name__=='__main__': main()
