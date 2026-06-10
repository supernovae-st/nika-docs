#!/usr/bin/env python3
"""Link + canon audit for nika-docs. Run from repo root: python3 scripts/link-audit.py
Exits 1 on findings. Checks:
  1. internal hrefs resolve to an existing page
  2. every page is registered in docs.json navigation
  3. no dead-branch GitHub links (nika-diamond was renamed main 2026-05)
  4. no legacy binding syntax ({{ ... }} without $ — spec canon is ${{ ... }} CEL)
"""
import re, glob, json, os, sys

findings = []
pages = {os.path.splitext(f)[0] for f in glob.glob('**/*.mdx', recursive=True)}
nav_pages = set()
def walk(o):
    if isinstance(o, dict):
        for v in o.values(): walk(v)
    elif isinstance(o, list):
        for v in o:
            nav_pages.add(v) if isinstance(v, str) else walk(v)
walk(json.load(open('docs.json'))['navigation'])

for f in glob.glob('**/*.mdx', recursive=True):
    s = open(f).read()
    for m in re.finditer(r'(?:href=["\']|\]\()(/[a-z0-9\-/#]+)', s):
        base = m.group(1).split('#')[0].lstrip('/')
        if base and base not in pages and not base.startswith('images'):
            findings.append(f'{f}: broken internal link {m.group(1)}')
    if 'nika-diamond' in s and 'renamed' not in s.split('nika-diamond')[0][-200:]:
        for i, line in enumerate(s.splitlines(), 1):
            if 'nika-diamond' in line and 'renamed' not in line:
                findings.append(f'{f}:{i}: dead-branch ref (nika-diamond renamed → main)')
    for i, line in enumerate(s.splitlines(), 1):
        if re.search(r'(?<!\$)\{\{ (tasks|vars|with|env|secrets)\b', line):
            findings.append(f'{f}:{i}: legacy binding syntax (use ${{{{ … }}}})')

orphans = pages - nav_pages - {p for p in pages if p.startswith('snippets/')}
findings += [f'page not in docs.json nav: {p}' for p in sorted(orphans)]

print('\n'.join(findings) if findings else 'link-audit: CLEAN')
sys.exit(1 if findings else 0)
