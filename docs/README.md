# Documentation

**[`ROADMAP.md`](./ROADMAP.md) — where the work stands and what is next.** The only
file that records progress.

**One home per fact.** Each fact is written out in one doc and linked from the rest, so
a change is made once. File names are kebab-case, except the repo-level trackers —
`README`, `ROADMAP`, `TODO`, `BUGS` — which are uppercase so they read as what they are.

## Start here

| Doc | What it covers |
|---|---|
| [`setup/clerk.md`](./setup/clerk.md) | Clerk setup — organizations, roles, keys, `ALLOWED_ORIGINS`, webhooks. **Do this first; nothing authenticates without it.** |
| [`setup/infrastructure.md`](./setup/infrastructure.md) | The root `.env`, and the Prometheus/Grafana/cAdvisor stack — what it covers, and what production does not |
| [`setup/making-it-yours.md`](./setup/making-it-yours.md) | Renaming the template for your project — service identity, branding, deploy names, and replacing the example domain |
| [`setup/deploy-dokploy.md`](./setup/deploy-dokploy.md) | Dokploy/Traefik facts for a first deploy — what `make deploy-check` cannot exercise, and what to check when a clean build 404s |
| [`TODO.md`](./TODO.md) | Cross-cutting follow-ups no single doc owns — what each unblocks and where the reasoning lives. Nothing here is broken |
| [`BUGS.md`](./BUGS.md) | Known defects in merged code — what's broken, how to reproduce it, what fixing it involves |

## Product

What the product does, for the people deciding scope. Conventions are in
[`product/README.md`](./product/README.md).

| Doc | What it covers |
|---|---|
| [`product/prd-mvp.md`](./product/prd-mvp.md) | The first release's scope — a skeleton for a fork to fill |
| [`product/features/account.md`](./product/features/account.md) | Getting in, organizations, the roles, the profile, deleting an account |

## Data model

What the platform stores — one doc per server module, each with the numbered modelling
decisions that record why its schema looks the way it does. Conventions are in
[`data-model/README.md`](./data-model/README.md).

| Doc | What it covers |
|---|---|
| [`data-model/account.md`](./data-model/account.md) | The `"user"` table — the platform's record of a person Clerk has told it about |
| [`data-model/conversation.md`](./data-model/conversation.md) | The `conversation` table — one row per chat thread with the assistant |

## Architecture

How the platform is built. These describe the system as it stands and are kept current;
a document that plans one change is not architecture.

**An architecture doc states facts.** What the system is and does, with the reason in a
clause where a reader needs it — no Decisions or Seams sections, no rejected
alternatives, no history, and no links to the specs or plans that produced it. What is
still open lives in [`TODO.md`](./TODO.md), and the doc states only today's side of it.

| Doc | What it covers |
|---|---|
| [`architecture/server.md`](./architecture/server.md) | How `server/` is put together — the four layers and the modules, the rules between them and how they are enforced, startup, the middleware stack, the transaction, errors, events and tenancy |
| [`architecture/web-app.md`](./architecture/web-app.md) | How `web-app/` is put together — two portals over six packages, the access gate, the session boundary, the path to the API, and what a third portal costs |
| [`architecture/authorization.md`](./architecture/authorization.md) | Tenants, the four roles, and which layer enforces each rule on the server and in the portals |
| [`architecture/authentication.md`](./architecture/authentication.md) | The path from sign-in to the user row — portal, Clerk, token, API — and where each step lives |

## Guides

How to build something again, portable beyond this repo. A guide describes a pattern's
general shape and says where this repo departs from it; architecture describes this repo.

| Doc | What it covers |
|---|---|
| [`guides/api-client-codegen.md`](./guides/api-client-codegen.md) | The OpenAPI → orval → TanStack Query pipeline, rebuildable in a fresh repo — runtime wiring, hook conventions, and the gotchas in §9. The commands are in [`../CLAUDE.md`](../CLAUDE.md) under **API Contract** |

Service-level docs live next to their code:

- [`../server/docs/authentication.md`](../server/docs/authentication.md) — how the server verifies a token and provisions a user
- [`../server/docs/gdpr-compliance-guide.md`](../server/docs/gdpr-compliance-guide.md) — the erasure pattern — and [`gdpr-erasure-findings.md`](../server/docs/gdpr-erasure-findings.md), the open gaps in what is built
- [`../CLAUDE.md`](../CLAUDE.md), [`../server/CLAUDE.md`](../server/CLAUDE.md), [`../web-app/CLAUDE.md`](../web-app/CLAUDE.md) — working conventions, and the most detailed operational notes in the repo
- [`../server/tests/README.md`](../server/tests/README.md) — the test fixtures, and how unit and integration tests isolate
- [`../README.md`](../README.md), [`../server/README.md`](../server/README.md), [`../web-app/README.md`](../web-app/README.md) and each portal's `README.md` — the entry points for a person; they link here rather than restate what lives here
