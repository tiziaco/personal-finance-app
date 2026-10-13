# Product docs

What the product does and why, for the people deciding scope. The *how* lives in
[`../architecture/`](../architecture/).

| Doc | Scope | Status | Last updated |
|---|---|---|---|
| [`prd-mvp.md`](./prd-mvp.md) | The first release — account, transactions, CSV import, categorisation, analytics, insights, chat | agreed | 12 Oct 2026 |

### Features

How one feature behaves, in more depth than a milestone PRD can hold. One file per feature.
`shipped` means the legacy v1.0 app did it; the port rebuilds it in roadmap steps 2–7.

| Doc | Scope | Status | Last updated |
|---|---|---|---|
| [`features/account.md`](./features/account.md) | Signing up and in, the profile, deleting an account | shipped | 12 Oct 2026 |
| [`features/transactions.md`](./features/transactions.md) | Browsing, searching, filtering, adding, correcting and deleting transactions | shipped | 12 Oct 2026 |
| [`features/csv-import.md`](./features/csv-import.md) | Uploading a bank CSV, confirming the column mapping, importing | shipped | 12 Oct 2026 |
| [`features/categorisation.md`](./features/categorisation.md) | The fixed categories, AI labelling, correcting a category | shipped | 12 Oct 2026 |
| [`features/analytics.md`](./features/analytics.md) | The dashboard and the four analytics views | shipped | 12 Oct 2026 |
| [`features/insights.md`](./features/insights.md) | AI-written observations about spending | shipped | 12 Oct 2026 |
| [`features/chat.md`](./features/chat.md) | The assistant — conversations, messages, memory (backend only in v1.0) | shipped | 12 Oct 2026 |
| [`features/budgets.md`](./features/budgets.md) | Spending limits by category — not built, out of scope for the port | draft | 12 Oct 2026 |

The conventions below apply to every doc. A fork keeps them and replaces the content.

## Conventions

- **One doc per milestone**, named for its scope: `prd-mvp.md` now, `prd-<scope>.md` for
  the next. No number prefixes — they imply an ordering that breaks the moment something
  is inserted.
- **A feature too large for its milestone PRD gets one file under `features/`**, named for
  the feature — `features/transactions.md`, no subfolder. The PRD keeps the scope line and
  links to it; the feature doc says how the feature behaves. Neither holds the technical
  design — that is a spec, **written against the feature doc and its data-model doc**.
- **The current doc never carries a version in its name; only a superseded one does.**
  Links to `features/transactions.md` survive every rewrite. A rewrite — a changed model, not
  an edit — moves the old text to `archive/<feature>-v<n>.md` and replaces the feature doc
  in place; ordinary changes are made in place, and git holds the history. Nothing has
  been rewritten yet, so there is no `archive/`.
- **Every doc opens with a status block**: status · owner · last updated · scope · related
  docs. Update the date in the same commit as the change.
- **Status vocabulary:** `draft` (still moving) → `agreed` (signed off, changes need a
  reason) → `shipped` (the product does this; the doc is now history). `superseded` marks
  a doc replaced by a rewrite, and names its successor.
- **Product docs hold intent, never schema.** Where each field is stored lives in the
  data-model doc's field map ([`../data-model/`](../data-model/));
  the feature doc's field list is the seam it reads from.
- **Every feature doc links its data-model doc** under **Data model** in its status block,
  and the data-model doc links back under **Describes**.
- **Product decisions stay here; modelling decisions go to the data-model doc.** When a
  question is both — erasure usually is — state it here and cross-reference from there.
