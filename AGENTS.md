# AGENTS.md — nika-docs (docs.nika.sh · Mintlify)

Vendor-neutral agent entry per the AGENTS.md convention (agents.md).

## What this repo is

Public documentation for Nika — the open workflow language for AI
(spec: `supernovae-st/nika-spec`, Apache-2.0) and its reference engine
(`supernovae-st/nika`, AGPL-3.0-or-later). Hosted via Mintlify
(`docs.json` is the nav source of truth).

## Editing rules

1. **Counts are projections** — verbs (4), builtins, providers, extract
   modes come from `nika-spec/canon.yaml`. Never invent or hardcode a
   stale count; check the spec repo when citing one.
2. **4 verbs only**: `infer` · `exec` · `invoke` · `agent`. Fetch is the
   `nika:fetch` builtin under `invoke:` — never document it as a verb.
3. New pages must be registered in `docs.json` nav.
4. MDX components: Mintlify set (Tabs, Accordion, Tip, Warning…).
5. Commit trailer: `Co-Authored-By: Nika 🦋 <nika@supernovae.studio>`.
