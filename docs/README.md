# Documentation

**[`ROADMAP.md`](./ROADMAP.md) — where the work stands and what is next.** The only
file that records progress.

**One home per fact.** Each fact is written out in one doc and linked from the rest, so
a change is made once. File names are kebab-case, except the repo-level trackers —
`README`, `ROADMAP`, `TODO`, `BUGS` — which are uppercase so they read as what they are.

## Start here

| Doc | What it covers |
|---|---|
| [`setup/clerk.md`](./setup/clerk.md) | Clerk setup — instance settings, keys, webhooks, dev users. **Do this first; nothing authenticates without it.** |
| [`setup/infrastructure.md`](./setup/infrastructure.md) | The root `.env`, and the Prometheus/Grafana/cAdvisor stack — what it covers, and what production does not |
| [`setup/deploy-dokploy.md`](./setup/deploy-dokploy.md) | Dokploy/Traefik facts for a first deploy — what `make deploy-check` cannot exercise, and what to check when a clean build 404s |
| [`TODO.md`](./TODO.md) | Cross-cutting follow-ups no single doc owns — what each unblocks and where the reasoning lives. Nothing here is broken |
| [`BUGS.md`](./BUGS.md) | Known defects in merged code — what's broken, how to reproduce it, what fixing it involves |

## Product

What the product does, for the people deciding scope. Conventions are in
[`product/README.md`](./product/README.md).

| Doc | What it covers |
|---|---|
| [`product/prd-mvp.md`](./product/prd-mvp.md) | The first release's scope — a personal finance app for friends and family |
| [`product/features/account.md`](./product/features/account.md) | Signing up and in, the profile, deleting an account |
| [`product/features/transactions.md`](./product/features/transactions.md) | Browsing, searching, filtering, adding, correcting and deleting transactions |
| [`product/features/csv-import.md`](./product/features/csv-import.md) | Uploading a bank CSV, confirming the column mapping, importing |
| [`product/features/categorisation.md`](./product/features/categorisation.md) | The fixed categories, AI labelling, correcting a category |
| [`product/features/analytics.md`](./product/features/analytics.md) | The dashboard and the four analytics views |
| [`product/features/insights.md`](./product/features/insights.md) | AI-written observations about spending |
| [`product/features/chat.md`](./product/features/chat.md) | The assistant — conversations, messages, memory |
| [`product/features/budgets.md`](./product/features/budgets.md) | Spending limits by category — not built, out of scope for the port |

## Data model

What the platform stores — one doc per server module, each with the numbered modelling
decisions that record why its schema looks the way it does. Conventions are in
[`data-model/README.md`](./data-model/README.md).

| Doc | What it covers |
|---|---|
| [`data-model/account.md`](./data-model/account.md) | The `"user"` table — the platform's record of a person Clerk has told it about |
| [`data-model/conversation.md`](./data-model/conversation.md) | The `conversation` table — one row per chat thread with the assistant |
| [`data-model/insight.md`](./data-model/insight.md) | The `insight_set` table — one user's current set of AI-written insights |

## Architecture

How the platform is built. These describe the system as it stands and are kept current;
a document that plans one change is not architecture.

**An architecture doc states facts.** What the system is and does, with the reason in a
clause where a reader needs it — no Decisions or Seams sections, no rejected
alternatives, no history, and no links to the specs or plans that produced it. What is
still open lives in [`TODO.md`](./TODO.md), and the doc states only today's side of it.

| Doc | What it covers |
|---|---|
| [`architecture/server.md`](./architecture/server.md) | How `server/` is put together — the four layers and the modules, the rules between them and how they are enforced, startup, the middleware stack, the transaction, errors, events and ownership |
| [`architecture/web-app.md`](./architecture/web-app.md) | How `web-app/` is put together — one app over six packages, the access gate, the session boundary and the path to the API |
| [`architecture/authorization.md`](./architecture/authorization.md) | Ownership: the user is the tenant, 404 for another user's row |
| [`architecture/authentication.md`](./architecture/authentication.md) | The path from sign-in to the user row — app, Clerk, token, API — and where each step lives |

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
- [`../README.md`](../README.md), [`../server/README.md`](../server/README.md), [`../web-app/README.md`](../web-app/README.md) and the app's `README.md` — the entry points for a person; they link here rather than restate what lives here
