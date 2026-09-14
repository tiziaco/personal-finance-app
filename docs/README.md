# Documentation

## Start here

| Doc | What it covers |
|---|---|
| [`setup/clerk.md`](./setup/clerk.md) | Clerk dashboard setup — organizations, the four role slugs, keys, `ALLOWED_ORIGINS`. **Do this first; nothing authenticates without it.** |
| [`setup/clerk-webhooks.md`](./setup/clerk-webhooks.md) | Webhook endpoint, signing secret, and the ngrok tunnel for local delivery |
| [`setup/infrastructure.md`](./setup/infrastructure.md) | The root `.env`, and the Prometheus/Grafana/cAdvisor stack — what it covers, and what production does not |
| [`setup/making-it-yours.md`](./setup/making-it-yours.md) | Renaming the template for your project — service identity, branding, deploy names, and replacing the example domain |

## Reference

| Doc | What it covers |
|---|---|
| [`RBAC/roles_definition.md`](./RBAC/roles_definition.md) | What the four roles mean and why the slugs are English while the labels are Italian |
| [`api-client-codegen-setup.md`](./api-client-codegen-setup.md) | Rebuild guide for the OpenAPI → orval → TanStack Query pipeline |

Service-level docs live next to their code:

- [`../server/docs/authentication.md`](../server/docs/authentication.md) — how the server verifies a token and provisions a user
- [`../server/docs/gdpr-compliance-guide.md`](../server/docs/gdpr-compliance-guide.md) and [`gdpr-erasure-findings.md`](../server/docs/gdpr-erasure-findings.md)
- [`../CLAUDE.md`](../CLAUDE.md), [`../server/CLAUDE.md`](../server/CLAUDE.md), [`../web-app/CLAUDE.md`](../web-app/CLAUDE.md) — working conventions, and the most detailed operational notes in the repo

## History

[`superpowers/`](./superpowers/) holds dated plans and specs — the design record for how
this repo reached its current shape. They are **not** current documentation:

- They describe decisions as of their date; some were later superseded.
- They retain the template's former product name **by design**. Rewriting a dated record
  to say something it did not say at the time would falsify it, so the old name survives
  there and nowhere else in the repo.

Read them for *why* something is the way it is. For *what is true now*, use the tables above.
