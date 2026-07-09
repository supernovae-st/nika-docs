# nika-docs

Source of [docs.nika.sh](https://docs.nika.sh) — the Mintlify-built documentation for
[Nika](https://github.com/supernovae-st/nika), the AGPL Rust workflow engine for AI.

> **Live at [docs.nika.sh](https://docs.nika.sh).** Every merge to `main`
> deploys via the Mintlify GitHub App. Preview locally with the steps below.

## What this repo is

A standalone public repository whose only job is to host the Mintlify
documentation source: a `docs.json` navigation config plus `.mdx` pages.
Mintlify watches `main` via its GitHub App and rebuilds the live site on push.
The repo also runs its own drift gate in CI (`.github/workflows/gate.yml` →
`scripts/link-audit.py`): internal links resolve · every page registered in
`docs.json` nav · no dead-branch GitHub refs · no legacy `{{ }}` binding syntax.

This repo is **not** the Nika engine source, **not** the marketing site, and
**not** a library you install.

## Structure

```
nika-docs/
├── docs.json              Mintlify config + navigation (every page MUST be registered)
├── introduction.mdx       Landing
├── getting-started/       installation · your-machine · first-workflow · editors · agents
├── guides/                patterns · agent-authoring · templates · troubleshooting · local-models · … (task-oriented)
├── concepts/              architecture · verbs · workflows · bindings · events · providers · security · …
├── examples/              overview + the tiered showcase workflows (PROJECTED — counts live in the projector)
├── architecture/          5 pages (layers · FCI · L0 decisions · admission · ADR index)
├── reference/             10 pages (YAML · CLI · schema · error codes · builtins · providers catalog · MCP catalog · capabilities · constellation · status)
├── changelog/             2 pages (releases · roadmap)
├── snippets/              _canon · _status-snapshot · _ecosystem (auto-generated/shared — see below)
├── scripts/link-audit.py  the repo's own drift gate (see CI)
├── .github/workflows/     gate.yml — link-audit on every push/PR
├── images/                logos + favicon
└── global.css             Mermaid transparent background
```

~57 pages of curated MDX across four tabs: **Guide · Architecture ·
Reference · Changelog** (count drifts — trust the tree, not this line).

## Local preview

Node 22 LTS is required (Mintlify blocks Node 25+). A `.nvmrc` is checked in.

```bash
# Pick up Node 22 (.nvmrc says 22):
nvm use                    # or: export PATH="/opt/homebrew/opt/node@22/bin:$PATH"

# Zero-config preview (no install step):
npx mintlify@latest dev    # → http://localhost:3000

# Broken-link check before opening a PR:
npx mintlify@latest broken-links
```

There is no `package.json` — Mintlify's CLI runs standalone via `npx`.

## Generated content — never hand-edit

Three classes of content are PROJECTED from external sources of truth.
Hand edits are overwritten on the next regeneration (and the projector
`--check` gates catch drift in the monorepo audit):

| Surface | Source of truth | Regenerate |
|---|---|---|
| `snippets/_status-snapshot.mdx` (engine live state) | engine repo | `bash scripts/mintlify-snapshot.sh` (in the engine) |
| `snippets/_canon.mdx` (language facts: verbs/builtins/providers counts) | `nika-spec/canon.yaml` | `python3 scripts/canon-projectors.py --write` (in the spec) |
| `examples/*.mdx` YAML+mermaid blocks · `guides/templates.mdx` template blocks · `reference/error-codes.mdx` tables | `nika-spec` showcase/ · templates/ · error registry | `python3 scripts/showcase-projector.py --write` (in the spec) |

In page bodies, **never hardcode counts** — import `{CANON}` / `{STATUS}`
from the snippets and reference fields (`{CANON.builtins}`,
`{STATUS.cratesAdmitted}`). Frontmatter `description:` cannot import →
keep volatile numbers out of descriptions entirely.

## Deploy

The Mintlify GitHub App is installed on this repo. Each push to `main`
triggers an automatic rebuild (typically ~30 seconds) and updates
`docs.nika.sh`. No CI configuration lives in this repo.

## Content conventions

- **Brand assets** (`images/logo-{light,dark}.svg` · `images/favicon.svg`)
  are vendored from the Nika brand kit — canonical files + usage rules at
  [nika.sh/brand](https://nika.sh/brand/nika-logo-dark.svg)
  ([BRAND.md](https://github.com/supernovae-st/nika.sh/blob/main/BRAND.md)).
  Sync contents from the kit, never hand-tune colors here.
- **Narrative vocabulary** (locked): "organ" not "module", "admitted" not
  "added", "grew" not "shipped", "chrysalis" not "beta", "emerge" reserved for
  the 1.0 release.
- **Butterfly** 🦋 is used sparingly — only in `introduction.mdx`'s closing
  line, never in nav, chrome, or headings.
- **Headings**: sentence case, never title case.
- **Voice**: direct, technical, AGPL-proud, never try-hard.

## Contributing

Pull requests are welcome.

1. Fork + branch from `main`.
2. Run `npx mintlify@latest dev` locally and verify your changes render.
3. Run `npx mintlify@latest broken-links` AND `python3 scripts/link-audit.py`
   — both must be clean (CI enforces the latter).
4. One `.mdx` file per page, and every page must be listed in `docs.json`.
5. Keep conventions above (vocabulary, headings, voice) + the generated-content
   rules (no hand-edits to projected blocks · no hardcoded counts).

## Related repositories

| Repo | Purpose |
|---|---|
| [`supernovae-st/nika`](https://github.com/supernovae-st/nika) | Rust engine — the workflow runtime itself (AGPL) |
| [`supernovae-st/nika-spec`](https://github.com/supernovae-st/nika-spec) | The open workflow language spec (Apache-2.0) — the language the engine implements |
| [`supernovae-st/nika.sh`](https://github.com/supernovae-st/nika.sh) | The site (Vite + React + r3f) — [nika.sh](https://nika.sh) |
| [`supernovae-st/nika-client`](https://github.com/supernovae-st/nika-client) | TypeScript SDK for consuming the Nika daemon |
| [`supernovae-st/nika-design-skill`](https://github.com/supernovae-st/nika-design-skill) | Claude skill for authoring workflows |
| [`supernovae-st/homebrew-tap`](https://github.com/supernovae-st/homebrew-tap) | Homebrew formula |
| [`supernovae-st/nika-site-audit`](https://github.com/supernovae-st/nika-site-audit) | Example workflow: audit a website with Nika |

## License

`AGPL-3.0-or-later` — same as the engine.
