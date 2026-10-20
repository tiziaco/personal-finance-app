# Transaction — Data Model

**Status:** shipped · **Owner:** Tiziano · **Last updated:** 15 Oct 2026
**Describes:** [`../product/features/transactions.md`](../product/features/transactions.md),
[`../product/features/categorisation.md`](../product/features/categorisation.md),
[`../product/features/csv-import.md`](../product/features/csv-import.md).
**Scope:** the `transaction` table — one movement of money — the category list its rows
point into, and the import's two tables.
**Source of truth:** the code — `server/app/modules/transaction/models.py`, `imports/models.py`,
`schemas.py` (`CATEGORIES`) and the Alembic revisions `09aea922f9b1` (add transaction) and
`5b7e2c9d4f10` (CSV import). The sketch below was
last brought in line with them on 15 Oct 2026; where the two disagree, the code wins. The
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
    is_recurring       BOOLEAN          NOT NULL,   -- the app defaults it to false; no DB default
    recurring_source   VARCHAR(16)      NOT NULL,   -- 'detected' | 'user'; validated by the app only, D6
    fingerprint        CHAR(64)         NOT NULL,   -- sha256 hex, D3
    merchant_key       VARCHAR(255)     NOT NULL,   -- normalise_merchant(merchant), D7
    created_at         TIMESTAMPTZ      NOT NULL,
    updated_at         TIMESTAMPTZ      NOT NULL,
    deleted_at         TIMESTAMPTZ
);

CREATE TABLE csv_mapping_profile (                  -- D8
    id          UUID        PRIMARY KEY DEFAULT uuidv7(),
    user_id     UUID        NOT NULL REFERENCES "user"(id),
    column_key  CHAR(64)    NOT NULL,   -- sha256 of the header names: stripped, casefolded, sorted, joined by U+001F
    mapping     JSONB       NOT NULL,   -- {"Buchungsdatum": "date", "Betrag": "amount", "Notiz": "ignore", …}
    created_at  TIMESTAMPTZ NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_csv_mapping_profile_user_id_column_key UNIQUE (user_id, column_key)
);

CREATE TABLE csv_upload (                           -- D9
    id          UUID        PRIMARY KEY DEFAULT uuidv7(),   -- the upload_id confirm takes
    user_id     UUID        NOT NULL REFERENCES "user"(id),
    content     TEXT        NOT NULL,   -- the decoded file
    expires_at  TIMESTAMPTZ NOT NULL,   -- created + 30 minutes
    created_at  TIMESTAMPTZ NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_csv_upload_user_id UNIQUE (user_id)
);
```

`csv_mapping_profile` and `csv_upload` carry `UserOwnedMixin`, so `test_owned_tables.py` needs
no allowlist entry for them either. Their models are in `imports/models.py`.

## 3. Indexes

| Index | Unique | Serves |
|---|---|---|
| `ix_transaction_user_id_date` | no | the list: one user's active rows in date order, and the date-range filter |
| `ix_transaction_user_id_fingerprint` | no | the duplicate check on a manual add, and the import counting the rows it already holds |
| `ix_transaction_user_id_merchant_key` | no | re-running the recurring rule for a merchant (D6) |
| `ix_transaction_user_id` | no | every ownership filter (from `UserOwnedMixin`) |
| `ix_transaction_created_at` | no | the tiebreak of every ordering (from `BaseModel`) |
| `ix_transaction_deleted_at` | no | telling active rows from deleted ones (from `SoftDeleteMixin`) |
| `uq_csv_mapping_profile_user_id_column_key` | yes | one remembered mapping per user and column set; the upsert on confirm (D8) |
| `uq_csv_upload_user_id` | yes | one held upload per user; the upsert on upload (D9) |

The two import tables also carry the `user_id` and `created_at` indexes their mixins add.

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
    the contract, and the web then fails to type-check until the slug has an icon row in
    `apps/web/src/components/transactions/category-icon.tsx`.
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
  function in `domain/fingerprint.py` (`service.py` re-exports it), tested against fixed
  vectors, so the import cannot drift from it.

  *Addition (15 Oct 2026):* an import count-matches. A fingerprint the file holds *n* times and
  the user holds *k* active times imports `max(0, n−k)` rows: a fingerprint held *k* times
  keeps all but the file's first *k* copies. Two identical coffees in one file import as two,
  and re-importing a file adds nothing.
- **D4 — soft delete one or a batch, hard delete for delete-all and erasure (13 Oct 2026).**
  Deleting one transaction, or up to 100 at once, sets `deleted_at`: the row is hidden from every
  list, count, duplicate check and batch, and kept. "Delete all transactions" in Settings and
  account erasure (`USER_ERASING`) run the same repository method, a single
  `DELETE … WHERE user_id = …` that also removes soft-deleted rows. Nothing references a
  transaction, so no foreign key breaks, and a row that holds a person's finances is not kept
  once they ask for it to go — which is why this table is hard-deleted rather than anonymised
  ([`README.md`](./README.md) §3).
  The Settings delete-all (`delete_all_on_request`) then publishes `transaction.all_deleted`
  (`TRANSACTIONS_ALL_DELETED`, payload `user_id`); erasure does not, its subscribers
  listening to `USER_ERASING`. `insights` subscribes inline and deletes the stored set, which quotes
  the deleted rows ([`insight.md`](./insight.md) D3) — added 16 Oct 2026.
- **D5 — the duplicate check on a manual add (13 Oct 2026).** `POST /transactions` looks for an
  active row with the same `(user_id, fingerprint)`. On a match it answers 409
  `DUPLICATE_TRANSACTION`, its details carrying only `existing_transaction_id` — merchant text
  stays out of the error log. Sending `allow_duplicate: true` skips the check; the flag is not
  stored. A soft-deleted twin does not count. Edits do not check.
- **D6 — `recurring_source`, and a rule that sets `is_recurring` (15 Oct 2026).** The stored
  `is_recurring` flag is the one source of truth for "recurring"; a deterministic rule in
  `domain/recurring.py` sets it, and `recurring_source` (`detected` | `user`) says who did.
  The rule judges one `merchant_key`'s active rows, money in and money out apart. It clusters
  rows around fixed seeds (the most frequent absolute amounts first, then the smallest; a row
  joins the first cluster whose seed is within ±15 % of it, with at least €1 of slack — a fixed
  seed does not drift the way a running median does). Inside each cluster, the same rule
  clusters again at the fixed band below, giving **same-amount runs**. A cluster or a run is a
  series when at least 75 % of the gaps between its sorted dates fit one cadence — the window,
  or twice it, for one skipped period (not for two yearly rows) — and it has the rows the cadence needs:

  | Cadence | Window (days) | Minimum rows |
  |---|---|---|
  | weekly | 6–8 | 4 in a run only |
  | monthly | 26–35 | 3 in a cluster |
  | quarterly | 84–98 | 3 in a cluster |
  | yearly | 350–380 | 3 in a cluster, or 2 in a run one window apart with no other row between them |

  A **run** holds the rows within 2 % of its seed, with at least €0.10 of slack; its seeds are
  chosen as a cluster's are. "Nothing between them" means no other row of the same merchant
  and side falls strictly between the run's first and last dates.

  A row is `true` when its cluster is a series or its run is; every other row is `false`.
  `user` rows are evidence — they count when judging a cluster or a run — and the rule never
  changes them.

  **Weekly and yearly changed on 19 Oct 2026**, for three reasons found on test data. A weekly
  series used to need three rows within ±15 %, and Lidl's weekly baskets, which vary but often
  land close, were flagged; they now need four at a fixed amount, which a basket does not
  repeat. A yearly series used to need three rows, so an annual subscription seen twice was
  missed; two rows at a fixed amount, a year apart with nothing between them, now count. The
  "nothing between" condition exists because two €7.42 visits to a leisure venue a year apart
  matched at a fixed amount while the user went there in between. The 2 % / €0.10 band is
  tight on purpose: Regional Rail fares of €5.68 and €5.94 would be admitted only by a €0.50
  floor, and they are not one charge. The same day, after the final review, the fixed amount
  moved from the whole cluster to each run inside it, so one odd row no longer undoes a series
  beside it: a weekly €3.00 that rises to €3.20 is recurring at both amounts, and thirty weekly
  €60 charges stay recurring while one €65 purchase among them does not. Lidl's baskets still
  form no run of four weekly rows at one amount. Two rows at one amount may not skip a year:
  two €100 withdrawals two years apart are a coincidence of round amounts, not a series. Flags
  already stored were not re-judged, because only dev data existed; re-seed or re-import to see
  the new rules. A database seeded or imported earlier also stored every `false` cell as the
  user's, which now reads as an untick and keeps those merchants out of hidden subscriptions
  until then.

  The rule runs in `transaction_service`, in the writing session, before the flush, and updates
  only `detected` rows whose value changed: one `UPDATE` per new value, so at most two
  statements. It judges each affected merchant key separately. Which write sets which
  provenance:

  | Write | Keys re-judged | `recurring_source` written |
  |---|---|---|
  | create | the new row's | `user` if `is_recurring` is true, else `detected` |
  | update | the old key, and the new one if the merchant changed | `user` if the patch includes `is_recurring` |
  | delete one, batch delete | the deleted rows' | — |
  | batch recategorise | none | — |
  | `import_many` | every key in the batch | `user` where a mapped recurring cell is true, else `detected` |
  | delete all, erasure | none | — |

  Only a ticked Recurring box on a manual add is a `user` assertion; unticked is `detected`. In
  an import, likewise, only a true cell of a mapped recurring column (`true`, `yes`, `x`, …) is
  the user's assertion; a false, blank or unrecognised cell lets the rule decide (amended
  19 Oct 2026). An untick in the app is the one way to keep a merchant out of hidden
  subscriptions. In the seed script, a `true` cell is `user`; any other is left to the rule. The migration followed the same
  rule for rows that already existed: a recurring one became `user`, since only a ticked box or
  the seed could have set it, and every other row `detected`.
- **D7 — `merchant_key`, a stored normalised merchant (15 Oct 2026).** The rule needs "the same
  merchant" to mean more than equal text, since a bank prints `PAYPAL *NETFLIX 4029357733` one
  month and `NETFLIX.COM` the next. `normalise_merchant` (in `domain/merchant.py`) runs, in
  order: Unicode NFKC and casefold; keep the part before a `|`; strip a payment-processor
  prefix (`paypal *`, `sumup *`, `zettle_`, `lsp*`, `spc*`, `sq *`; `ubr*` becomes `uber`);
  strip a web-domain suffix (`.com`, `.de`, `.eu`, `.it`, `.co.uk`) and a legal-form suffix
  (`gmbh`, `ag`, `se`, `kg`, `bv`, `b.v.`, `ltd`, `inc`, `srl`, `spa`); drop trailing tokens
  holding three or more digits; turn punctuation other than `&` into spaces and collapse
  whitespace (an empty result falls back to the casefolded raw text), and cut to the
  column's 255 characters, since folding can lengthen text (`ß` → `ss`). **Conservative by
  design:** no fuzzy matching, because a missed merge loses a series and a wrong merge invents
  one. The column is stored, indexed with `user_id`, and recomputed with the fingerprint.
  It is the one definition of a merchant: analytics groups every merchant analysis by it too
  (`AnalysisRow.merchant_key`).
  **A change to the normaliser changes stored keys and needs a backfill revision**, as a slug
  rename does (D2); the revision `5b7e2c9d4f10` backfilled every row, soft-deleted ones too, by
  calling the live normaliser, not a frozen copy.
- **D8 — mapping profiles (15 Oct 2026).** A confirmed column mapping is remembered so the next
  file with the same columns skips the LLM. `csv_mapping_profile` is keyed per user and column
  set — `column_key` is the sha256 of the header names, stripped, casefolded, sorted and joined
  — not per bank name, so two banks with identical headers share a profile and a bank that adds
  a column starts afresh. Names match by case and spacing. Every successful confirm upserts the
  profile with the confirmed mapping, so a correction is remembered. Nothing references it.
- **D9 — held uploads (15 Oct 2026).** Between the two steps the file waits in `csv_upload`:
  one row per user, for 30 minutes. Each new upload replaces the held one in a single upsert on
  `user_id` and gets a new id, so a confirm against the replaced id is a 404, as is one after
  expiry. A confirm hard-deletes the row, as does erasure (`USER_ERASING`, inline beside the
  transaction delete). It holds the decoded text only; the delimiter, formats and mapping are
  re-inferred on confirm, deterministically, so there is no second copy to keep in line with the
  parser.

## 5. Deferred

- **An index on `category`, or a partial index on active rows.** One person's rows number in
  the thousands. Brought back by a filter that is measurably slow.
- **Undo, or a "recently deleted" view.** Soft delete keeps the row, but nothing in the product
  restores it. Brought back by the product question in
  [`transactions.md`](../product/features/transactions.md) §6.
- **A sweep of abandoned uploads.** An unconfirmed upload's text stays until the user's next
  upload or erasure; a sweep across users needs the worker in `../TODO.md` (Server — events
  beyond the request).

## 6. Field map

| Field in [`transactions.md`](../product/features/transactions.md) §3 | Stored in |
|---|---|
| date | `date` |
| merchant | `merchant` |
| amount | `amount` — signed; a string on the wire |
| description | `description` |
| original category | `original_category` — set by the import and the seed |
| category | `category` — a slug; the label comes from `GET /transactions/categories` |
| confidence | `confidence` — 1 on every manual write |
| recurring | `is_recurring`, with `recurring_source` |
| the import fingerprint | `fingerprint` — never sent to the web |
| created and updated times | `created_at`, `updated_at` |
| deleted | `deleted_at` — never sent to the web |
