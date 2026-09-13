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
   Frontmatter `description:` cannot import — keep counts OUT of
   descriptions entirely. **No exemption, no "forever-locked" carve-out.**
   Dated changelog/ADR entries are frozen history; repair active pages instead.
2. **4 verbs only**: `infer` · `exec` · `invoke` · `agent`. Fetch is the
   `nika:fetch` builtin under `invoke:` — never document it as a verb.
3. New pages must be registered in `docs.json` nav — `python3
   scripts/link-audit.py` enforces this, plus internal-link resolution,
   dead-branch GitHub refs (`nika-diamond` was renamed `main` 2026-05),
   and legacy binding syntax (`{{ … }}` — spec canon is `${{ … }}` CEL).
   Run it before every commit; it exits 1 on findings.
4. MDX components: Mintlify set (Tabs, Accordion, Tip, Warning…).
5. Cross-property links: the ecosystem mesh lives in ONE place —
   `snippets/_ecosystem.mdx` (docs · spec · engine · SDK · brew ·
   studio). Include it rather than hand-writing link lists per page.
6. Expression canon: `${{ … }}` = CEL (conditions + references) ·
   `extract:`/`nika:jq` = jq (extraction + transform) · NO template
   filters. Model id in examples: `ollama/qwen3.5:4b` (local-first ·
   sovereignty default · the SAME model the engine's own scaffold and
   the brew caveat teach — one first experience across the funnel) ·
   cloud variant when needed: `mistral/mistral-large`. Respect an explicitly
   requested provider/model; examples do not change runtime defaults.
7. Commit trailer: `Co-Authored-By: Nika 🦋 <nika@supernovae.studio>`.
8. **These docs teach the current stable binary and only that binary.** The
   exact version is the projection at `snippets/_status-snapshot.mdx`; never
   freeze a release number in this rule. No dual grammar, no "if you are on
   the previous release" branch, no alias (`no-legacy-no-back-compat`). The
   envelope is the nine keys (`nika` · `model` · `inputs` · `const` ·
   `secrets` · `permits` · `run` · `tasks` · `outputs`), re-verified
   against the current stable binary at each projection (the nine-key
   envelope shipped in 0.109): the identity is `nika: <id>`
   (kebab-case · the description is a `#` comment above it · no
   `workflow:` block), every value lands under one of three authorities —
   `inputs:` (the caller supplies it · a deployment knob is an entry with
   `required: false` + `default:`) · `const:` (the file owns it) ·
   `secrets:` (a governed store); `config:` is not a field, `vars:` and
   `env:` are dead (`NIKA-VALUES-001`/`-002`, and the envelope `env:`
   only — `exec.env:` is alive). A task's jq bindings are `extract:`,
   cleanup is a task on an `unwind` edge (`after: {x: unwind}`), the
   fan-out leash lives inside `for_each:` (`items` · `max_parallel` ·
   `fail_fast`), a law opens through `lift:` only, and `graph_format` is
   3. An absent `permits:` block declares **zero** authority
   (`NIKA-AUTH-006`), so every effect-bearing example carries one. Also:
   `after:` is `success`/`failure` (not `succeeded`/`failed`), and `bool`
   is the boolean spelling — but raw JSON Schema under `infer.schema:` is
   a different language and is never touched. Every authored yaml fence
   is judged by `scripts/oracle-sweep.py` on the released binary;
   `scripts/mdx-yaml-fix.py` runs the binary's own `--fix` through the
   fences in place.
9. **Two regions of this repo are PROJECTED, not authored** — never
   hand-edit them, the next projection reverts you:
   - `{/* showcase:begin … */}` and `{/* template:begin … */}` blocks in
     `examples/*.mdx` and `guides/*.mdx` ← `nika-spec` `examples/showcase/`
     + `templates/`, via `nika-spec/scripts/showcase-projector.py`.
   - `{/* errors-*:begin */}` tables in `reference/error-codes.mdx` ←
     `nika-spec` `canon/diagnostics/registry.yaml`, same projector.

   The projector serves the spec's source as identity (the grammar door
   that once downcast the pack to the released binary is gone since
   nika-spec `2b3d6ac3e`): a served example IS the spec file. Changing
   one for real means changing the spec file and re-projecting, not
   editing the mirror.

## Task scope and completion

Read the source needed for the change: `docs.json` for navigation, the owning spec for language behavior, and the released-binary projection for current engine claims. A typo correction does not need a whole-repository architecture survey. For authored YAML, run the relevant oracle checks as required above; preserve effect boundaries and do not execute paid workflows implicitly.

Complete authorized edits through the required checks and requested publication, fixing failures introduced by the change. Report unrelated baseline failures separately. Preserve model choice and use available client tools; these instructions do not require a particular model or a private studio checkout.

## Publication boundary

This entire repository is public, including source files, assets and Git history.
Publish product usage, public contracts and released integrations only. Internal
workspaces, development services, project plans and operational evidence belong
in their private owners. Never move private material into a hidden page, snippet,
JSON export, screenshot or source comment here. Review the audience before
writing; run `python3 scripts/publication-audit.py` before committing.
