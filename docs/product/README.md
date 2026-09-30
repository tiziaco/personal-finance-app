# Product docs

What the product does and why, for the people deciding scope. The *how* lives in
[`../architecture/`](../architecture/).

| Doc | Scope | Status | Last updated |
|---|---|---|---|
| [`prd-mvp.md`](./prd-mvp.md) | The first release — account, suppliers, the assistant | draft (a skeleton; §4 pending) | 29 Sep 2026 |

### Features

How one feature behaves, in more depth than a milestone PRD can hold. One file per feature.

| Doc | Scope | Status | Last updated |
|---|---|---|---|
| [`features/account.md`](./features/account.md) | Getting in, organizations, the roles, the profile, deleting an account | shipped | 29 Sep 2026 |
| [`features/suppliers.md`](./features/suppliers.md) | The example domain — supplier companies, their portal contact, their documents | draft | 29 Sep 2026 |

The template ships these as worked examples: `account` is what a `shipped` feature doc
looks like, `suppliers` a `draft` one. A fork keeps the conventions below and replaces the
content ([`../setup/making-it-yours.md`](../setup/making-it-yours.md) §4).

## Conventions

- **One doc per milestone**, named for its scope: `prd-mvp.md` now, `prd-<scope>.md` for
  the next. No number prefixes — they imply an ordering that breaks the moment something
  is inserted.
- **A feature too large for its milestone PRD gets one file under `features/`**, named for
  the feature — `features/suppliers.md`, no subfolder. The PRD keeps the scope line and
  links to it; the feature doc says how the feature behaves. Neither holds the technical
  design — that is a spec, **written against the feature doc and its data-model doc**.
- **The current doc never carries a version in its name; only a superseded one does.**
  Links to `features/suppliers.md` survive every rewrite. A rewrite — a changed model, not
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
