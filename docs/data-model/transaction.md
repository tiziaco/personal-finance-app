# Transaction — Data Model

**Status:** shipped · **Owner:** Tiziano · **Last updated:** 13 Oct 2026
**Describes:** [`../product/features/transactions.md`](../product/features/transactions.md),
[`../product/features/categorisation.md`](../product/features/categorisation.md).
**Scope:** the `transaction` table — one movement of money — and the category list its rows
point into.
**Source of truth:** the code — `server/app/modules/transaction/models.py`, `schemas.py`
(`CATEGORIES`) and the Alembic revision `09aea922f9b1` (add transaction). The sketch below was
last brought in line with them on 13 Oct 2026; where the two disagree, the code wins. The
conventions every table follows are in [`README.md`](./README.md).

---

## 1. Approach

**One row per movement of money.** A bank line, or a transaction typed in by hand. Nothing
references a transaction, and a transaction is never split.

**User-owned.** The row carries `UserOwnedMixin`, so `test_owned_tables.py` needs no allowlist
entry, and every query filters by `user_id`. Another user's row is a missing one.

**The category list lives on the server, in code.** `CATEGORIES` in
`server/app/modules/transaction/schemas.py` is an ordered list of `(slug, label)` pairs; the
`Category` enum is built from it. The web reads it from `GET /transactions/categories` and holds
no list of its own. The database stores the slug and knows no list (D2).

**Personal data is hard-deleted, not anonymised** — see D4.

## 2. Schema sketch

```sql
CREATE TABLE transaction (
    id                 UUID             PRIMARY KEY DEFAULT uuidv7(),
    user_id            UUID             NOT NULL REFERENCES "user"(id),
    date               DATE             NOT NULL,
    merchant           VARCHAR(255)     NOT NULL,
    amount             NUMERIC(12,2)    NOT NULL,   -- money out < 0, money in > 0
    description        VARCHAR(1000),
    original_category  VARCHAR(255),                -- the bank's, as imported
    category           VARCHAR(64)      NOT NULL,   -- a Category slug; validated by the app only
    confidence         DOUBLE PRECISION NOT NULL,   -- 0..1; 1 for anything entered or edited by hand
    is_recurring       BOOLEAN          NOT NULL DEFAULT false,
    fingerprint        CHAR(64)         NOT NULL,   -- sha256 hex, D3
    created_at         TIMESTAMPTZ      NOT NULL,
    updated_at         TIMESTAMPTZ      NOT NULL,
    deleted_at         TIMESTAMPTZ
);
```

## 3. Indexes

| Index | Unique | Serves |
|---|---|---|
| `ix_transaction_user_id_date` | no | the list: one user's active rows in date order, and the date-range filter |
| `ix_transaction_user_id_fingerprint` | no | the duplicate check on a manual add, and step 4's import skipping rows it already holds |
| `ix_transaction_user_id` | no | every ownership filter (from `UserOwnedMixin`) |
| `ix_transaction_created_at` | no | the tiebreak of every ordering (from `BaseModel`) |
| `ix_transaction_deleted_at` | no | telling active rows from deleted ones (from `SoftDeleteMixin`) |

## 4. Decisions

- **D1 — a date, not a date and time (13 Oct 2026).** A bank statement gives a day, and the
  product groups and filters by day. `DATE` keeps a time zone out of the model: a timestamp
  would shift a transaction across midnight for a user who travels. Legacy stored a
  `timestamptz`; no data is migrated.
- **D2 — slugs in `VARCHAR`, no database constraint (13 Oct 2026).** `category` holds a slug
  such as `food_groceries`; the app validates it on the way in and the API serves the labels.
  Rejected: a Postgres enum, which turns every change of the list into a migration and cannot
  drop a value; a `CHECK` constraint, which has the same cost; a `category` table, a join and a
  second source of truth for a list that is twenty entries long and changes with the code that
  reads it.
  - *Add a category:* one new `(slug, label)` in `CATEGORIES`. The pre-commit hook regenerates
    the contract; the web needs nothing.
  - *Rename a label:* edit the label. Nothing else moves.
  - *Rename or remove a slug:* edit `CATEGORIES`, and add an Alembic revision with
    `UPDATE transaction SET category = '<new>' WHERE category = '<old>'` for the rows that hold
    it. That is the data, not the schema.
- **D3 — the fingerprint (13 Oct 2026).** A duplicate is recognised by a hash, not forbidden by
  a constraint:

  ```
  sha256(f"{user_id}|{date:%Y-%m-%d}|{merchant.strip().casefold()}|{amount:.2f}|{(description or '').strip().casefold()}")
  ```

  `amount` is the `Decimal` quantised to two places, never a float — a float holds most
  cent values only approximately, so the text the hash is taken over could differ between
  paths. `-0.00`
  hashes as `0.00`. Computed on create and recomputed on every edit that changes date, merchant,
  amount or description. Not unique: the user may add a twin on purpose (D5). It is a pure
  function in `service.py`, tested against fixed vectors, so step 4's import cannot drift from it.
- **D4 — soft delete one or a batch, hard delete for delete-all and erasure (13 Oct 2026).**
  Deleting one transaction, or up to 100 at once, sets `deleted_at`: the row is hidden from every
  list, count, duplicate check and batch, and kept. "Delete all transactions" in Settings and
  account erasure (`USER_ERASING`) run the same repository method, a single
  `DELETE … WHERE user_id = …` that also removes soft-deleted rows. Nothing references a
  transaction, so no foreign key breaks, and a row that holds a person's finances is not kept
  once they ask for it to go — which is why this table is hard-deleted rather than anonymised
  ([`README.md`](./README.md) §3).
- **D5 — the duplicate check on a manual add (13 Oct 2026).** `POST /transactions` looks for an
  active row with the same `(user_id, fingerprint)`. On a match it answers 409
  `DUPLICATE_TRANSACTION`, its details carrying only `existing_transaction_id` — merchant text
  stays out of the error log. Sending `allow_duplicate: true` skips the check; the flag is not
  stored. A soft-deleted twin does not count. Edits do not check.

## 5. Deferred

- **An index on `category`, or a partial index on active rows.** One person's rows number in
  the thousands. Brought back by a filter that is measurably slow.
- **Undo, or a "recently deleted" view.** Soft delete keeps the row, but nothing in the product
  restores it. Brought back by the product question in
  [`transactions.md`](../product/features/transactions.md) §6.

## 6. Field map

| Field in [`transactions.md`](../product/features/transactions.md) §3 | Stored in |
|---|---|
| date | `date` |
| merchant | `merchant` |
| amount | `amount` — signed; a string on the wire |
| description | `description` |
| original category | `original_category` — set by the import and the seed only |
| category | `category` — a slug; the label comes from `GET /transactions/categories` |
| confidence | `confidence` — 1 on every manual write |
| recurring | `is_recurring` |
| the import fingerprint | `fingerprint` — never sent to the web |
| created and updated times | `created_at`, `updated_at` |
| deleted | `deleted_at` — never sent to the web |
