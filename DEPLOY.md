# Deploy — docs.nika.sh (Mintlify)

These docs are hosted by **Mintlify** — no build pipeline in this repo.
Mintlify watches `main`, reads [`docs.json`](docs.json), and publishes on
every push. The custom domain `docs.nika.sh` is **not live yet**: no DNS
record exists today. Three steps, two owners.

## 1 · Mintlify dashboard — connect + custom domain (Thibaut)

1. [dash.mintlify.com](https://dash.mintlify.com) → sign in with GitHub
   (`supernovae-st`).
2. If the project doesn't exist yet: **Add project** → connect the repo
   `supernovae-st/nika-docs` (root · `docs.json` is auto-detected). The
   first deployment publishes to a `*.mintlify.app` preview URL — verify
   the docs render there.

   > ⚠️ **`nika.mintlify.app` is NOT us** (verified 2026-06-10): that
   > subdomain belongs to an unrelated company (`nikaplanet.com`). Our
   > project will get a different preview slug — don't be confused by
   > the 200 on `nika.mintlify.app`.
3. **Settings → Custom domain** → enter `docs.nika.sh`. Mintlify shows
   the exact CNAME target (typically `cname.mintlify.app`). Note it.

## 2 · DNS record in the DO zone (Nicolas)

The `nika.sh` zone lives on DigitalOcean nameservers
(`ns1-3.digitalocean.com`). Add the CNAME:

```sh
doctl compute domain records create nika.sh \
  --record-type CNAME \
  --record-name docs \
  --record-data <target-from-step-1>. \
  --record-ttl 3600
```

(or dashboard: Networking → Domains → nika.sh → CNAME `docs` → target.)
Note the trailing dot on the target. Do **not** add `docs.nika.sh` to the
DO App spec of the website (`supernovae-st/nika.sh` `.do/app.yaml`) — the
docs are served by Mintlify, not by the app.

## 3 · Verify

```sh
dig +short docs.nika.sh            # the CNAME target appears
curl -sI https://docs.nika.sh | head -1   # 200 (TLS auto-provisioned by Mintlify)
```

Cert issuance starts once the CNAME resolves — usually minutes, up to an
hour. If it stalls, re-check the domain in the Mintlify dashboard (it
shows a verification status per domain).

## Reference

- Config: [`docs.json`](docs.json) — name `Nika`, dark default, og:image
  already pointed at `https://docs.nika.sh/...`.
- Sister runbook (the website app + the DO zone context):
  `supernovae-st/nika.sh` → `DEPLOY.md`.
- Content rule: language facts (verbs, builtins, providers) derive from
  `nika-spec` `canon.yaml` via the projection mesh — never hand-edit the
  generated `_canon` snippets.
