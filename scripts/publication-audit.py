#!/usr/bin/env python3
"""Refuse private workspace material in the public documentation repository."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
# Rules contain identifiers to detect, never the protected content itself.
RULES = {
    'private workspace reference': r'\bNika[\s_-]*Lab\b|\b(?:the|le|du)\s+Lab\b|\bLab\s+(?:MCP|language identity)|lab\.nika\.sh|(?:explore-lab|lab-agents)',
    'private development reference': r'nika-dx\b|benchmark-dx\b|/dx/(?:state|workflows|benchmarks)|\.claude/plans/|\b(?:lab|dx):(?:page|space|subject|task|mission):',
    'private classification': r'\b(?:internal-workspace|internal-evidence|mixed-review-required|lab-subject-assembly)\b',
    'private capture': r'public/control/(?:ssot|dx)|NIKA_LAB_REPOSITORIES|\blab_(?:development_context|trace_path|get_node|read|relations|search|status)\b',
}
# Only detector definitions and their synthetic regression cases need exceptions.
DETECTORS = {'scripts/publication-audit.py', 'scripts/tests/test_publication_audit.py'}
DATA_FILES = {
    'docs.json', 'api-reference/openapi.json',
    'snippets/data/documentation-navigation.json', 'snippets/data/knowledge-mirror.json',
    'snippets/data/knowledge-taxonomy.json', 'snippets/data/language-reference.json',
    'snippets/data/tool-mirror.json', 'snippets/data/tool-reference.json',
    'scripts/public-assets.json',
}

def files(root):
    raw = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=root)
    return sorted(set(p for p in raw.decode().split('\0') if p))

def audit(root):
    findings = []
    paths = files(root)
    media = json.loads((root/'scripts/public-assets.json').read_text())
    for name in paths:
        path = root/name
        if not path.exists() and not path.is_symlink():
            continue  # A tracked deletion is absent from the candidate tree.
        if path.is_symlink():
            findings.append(f'{name}: symlinks cannot publish unchecked content')
            continue
        if name in DETECTORS:
            continue
        raw = path.read_bytes()
        if name.startswith(('images/', 'videos/')):
            if media.get(name) != hashlib.sha256(raw).hexdigest():
                findings.append(f'{name}: new or changed media needs public-audience review')
        if path.suffix.lower() in {'.zip', '.gz', '.tgz', '.tar', '.db', '.sqlite', '.sqlite3'}:
            findings.append(f'{name}: archives and databases are not documentation inputs')
        if path.suffix == '.json' and name not in DATA_FILES:
            findings.append(f'{name}: data export has no public input contract')
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            if name not in media:
                findings.append(f'{name}: binary has no public-audience review')
            continue
        # Decode common URL/HTML/JSON spellings as well as authored text.
        text = html.unescape(unquote(text))
        text = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m[1],16)), text)
        for reason, pattern in RULES.items():
            if re.search(pattern, text, re.I):
                findings.append(f'{name}: {reason}')
    taxonomy = json.loads((root/'snippets/data/knowledge-taxonomy.json').read_text())
    if taxonomy.get('destinations'):
        findings.append('taxonomy: application navigation must not be published')
    for entry in taxonomy.get('families', {}).values():
        if entry.get('visibility') != 'public-concept':
            findings.append('taxonomy: only explicitly public concepts are admitted')
    if not any(p.endswith('.mdx') for p in paths):
        findings.append('publication audit found no documentation; refusing an empty check')
    return findings

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    args=parser.parse_args()
    findings=audit(args.root)
    print('\n'.join(findings) if findings else 'publication-audit: CLEAN')
    raise SystemExit(bool(findings))

if __name__ == '__main__':
    main()
