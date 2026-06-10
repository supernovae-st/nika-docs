# AGENTS.md — nika-docs (docs.nika.sh · Mintlify)

Vendor-neutral agent entry per the AGENTS.md convention (agents.md).

## What this repo is

Public documentation for Nika — the open workflow language for AI
(spec: `supernovae-st/nika-spec`, Apache-2.0) and its reference engine
(`supernovae-st/nika`, AGPL-3.0-or-later). Hosted via Mintlify
(`docs.json` is the nav source of truth).

## Editing rules

1. **Counts are projections — never hardcode them in page bodies.**
   Language facts (verbs, builtins, providers, extract modes) derive from
   `nika-spec/canon.yaml` via `snippets/_canon.mdx` (auto-generated):
   `import { CANON } from "/snippets/_canon.mdx"` then `{CANON.builtins}`
   inline. Engine live state (version, crates, tests, ADRs) derives from
   `snippets/_status-snapshot.mdx` the same way (`STATUS.version`…).
   Frontmatter `description:` cannot import — keep volatile numbers OUT
   of descriptions entirely (only forever-locked facts like the 42-crate
   target may appear as words). Dated changelog/ADR entries are FROZEN
   history: never retro-edit their numbers.
2. **4 verbs only**: `infer` · `exec` · `invoke` · `agent`. Fetch is the
   `nika:fetch` builtin under `invoke:` — never document it as a verb.
3. New pages must be registered in `docs.json` nav — `python3
   scripts/link-audit.py` enforces this, plus internal-link resolution,
   dead-branch GitHub refs (`nika-diamond` was renamed `main` 2026-05),
   and legacy binding syntax (`{{ … }}` — spec canon is `${{ … }}` CEL).
   Run it before every commit; it exits 1 on findings.
4. MDX components: Mintlify set (Tabs, Accordion, Tip, Warning…).
5. Cross-property links: the ecosystem mesh lives in ONE place —
   `snippets/_ecosystem.mdx` (site · spec · engine · SDK · brew ·
   studio). Include it rather than hand-writing link lists per page.
6. Expression canon: `${{ … }}` = CEL (conditions + references) ·
   `output:`/`nika:jq` = jq (extraction + transform) · NO template
   filters. Model id in examples: `anthropic/claude-sonnet-4-6`.
7. Commit trailer: `Co-Authored-By: Nika 🦋 <nika@supernovae.studio>`.
