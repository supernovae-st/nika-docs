import { compile } from '@mdx-js/mdx';
import { readFileSync } from 'node:fs';

const file = process.argv[2];
if (!file || file.startsWith('-')) {
  console.error('usage: node compile-mdx.mjs <page.mdx>');
  process.exit(2);
}

const raw = readFileSync(file, 'utf8');
const src = raw
  .replace(/^---[\s\S]*?---\s*/, '')
  .replace(/\{\/\*[\s\S]*?\*\/\}/g, '');
const out = await compile(src, { jsx: true });
if (!String(out)) process.exit(2);
