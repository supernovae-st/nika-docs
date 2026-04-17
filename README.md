# nika-docs

Source of [docs.nika.sh](https://docs.nika.sh) — the Mintlify-built documentation for
[Nika](https://github.com/supernovae-st/nika), the AGPL Rust workflow engine for AI.

> **Mintlify deployment pending.** DNS `docs.nika.sh` and the Mintlify GitHub App
> are being wired up — the site will go live once the custom domain lands. In
> the meantime, preview locally (see below).

## What this repo is

A standalone public repository whose only job is to host the Mintlify
documentation source: a `docs.json` navigation config plus `.mdx` pages.
Mintlify watches `main` via its GitHub App and rebuilds the live site on push —
there is no CI or build server on our side.

This repo is **not** the Nika engine source, **not** the marketing site, and
**not** a library you install.

## Structure

```
nika-docs/
├── docs.json              Mintlify config + 4-tab navigation
├── introduction.mdx       Landing
├── getting-started/       3 pages (installation · first-workflow · editors)
├── concepts/              6 pages (architecture · verbs · workflows · bindings · events · providers)
├── architecture/          5 pages (layers · FCI · L0 decisions · admission · ADR index)
├── reference/             8 pages (YAML · CLI · schema · error codes · providers catalog · capabilities · constellation · status)
├── changelog/             2 pages (releases · roadmap)
├── snippets/              _status-snapshot.mdx (auto-generated — see below)
├── images/                logos + favicon
└── global.css             Mermaid transparent background
```

33 files, ~4,300 LOC of curated MDX across four tabs: **Guide · Architecture ·
Reference · Changelog**.

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

## The status snapshot is auto-generated

`snippets/_status-snapshot.mdx` is rendered by a script living in the engine
repo. **Do not hand-edit it** — your changes will be overwritten on the next
refresh.

To regenerate it (from the `supernovae-hq` monorepo root, with both the engine
and docs checked out as submodules):

```bash
cd nika/engine && bash scripts/mintlify-snapshot.sh
# Writes ../docs/snippets/_status-snapshot.mdx
# Then commit + push from nika/docs/:
cd ../docs && git add snippets/_status-snapshot.mdx
git commit -m "docs(snapshot): refresh live numbers"
git push
```

## Deploy

The Mintlify GitHub App is installed on this repo. Each push to `main`
triggers an automatic rebuild (typically ~30 seconds) and updates
`docs.nika.sh`. No CI configuration lives in this repo.

## Content conventions

- **Narrative vocabulary** (locked): "organ" not "module", "admitted" not
  "added", "grew" not "shipped", "chrysalis" not "beta", "emerge" reserved for
  v0.90.
- **Butterfly** 🦋 is used sparingly — only in `introduction.mdx`'s closing
  line, never in nav, chrome, or headings.
- **Headings**: sentence case, never title case.
- **Voice**: direct, technical, AGPL-proud, never try-hard.

## Contributing

Pull requests are welcome.

1. Fork + branch from `main`.
2. Run `npx mintlify@latest dev` locally and verify your changes render.
3. Run `npx mintlify@latest broken-links` — fix anything it reports.
4. One `.mdx` file per page, and every page must be listed in `docs.json`.
5. Keep conventions above (vocabulary, headings, voice).

## Related repositories

| Repo | Purpose |
|---|---|
| [`supernovae-st/nika`](https://github.com/supernovae-st/nika) | Rust engine — the workflow runtime itself (AGPL) |
| [`supernovae-st/nika.sh`](https://github.com/supernovae-st/nika.sh) | Marketing site (Astro) — [nika.sh](https://nika.sh) |
| [`supernovae-st/nika-client`](https://github.com/supernovae-st/nika-client) | TypeScript SDK for consuming the Nika daemon |
| [`supernovae-st/nika-design-skill`](https://github.com/supernovae-st/nika-design-skill) | Claude skill for authoring workflows |
| [`supernovae-st/homebrew-tap`](https://github.com/supernovae-st/homebrew-tap) | Homebrew formula |
| [`supernovae-st/nika-site-audit`](https://github.com/supernovae-st/nika-site-audit) | Example workflow: audit a website with Nika |

## License

`AGPL-3.0-or-later` — same as the engine.
