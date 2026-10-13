# Transactions — design

**Roadmap step:** 2 Transactions · **Branch:** `feat/transactions` (worktree slot 1) · **PR into:**
`template-base` · **Date:** 13 Oct 2026 · **Status:** approved 13 Oct 2026; amended with what the plan's code survey found

Built beside step 3, Chat screen (`feat/chat-screen`). The ownership split and the eight
conditions both steps follow are in `.superpowers/BRIEF.md`; this spec stays inside them.

---

## 1. Intent

The app's first finance table. A user can see every transaction they hold, find one, correct it
— above all its category, since the AI that will assign categories (step 4) is imperfect — and
remove junk, one at a time, in bulk, or all at once. Every later finance step reads or writes
this table and its category list, so both are defined once, here.

The same step fixes the email-uniqueness lockout (`BUGS.md`), because the fix changes a
migration and must land before the first table references `"user"`.

**Done when:** a PR into `template-base` is open with the server module, the web page, the
Settings action, the seed, the email fix and their tests; every gate is green (`make check`,
`make test-web`, the server suites, `make check-contract`); the docs in §9 are updated; this spec
and its plan are deleted; roadmap row 2 reads `complete` with the PR link.

### Decisions taken with the user (13 Oct 2026)

| # | Decision |
|---|---|
| U1 | Email uniqueness: option (a) — drop `unique=True`; Clerk owns uniqueness, `clerk_id` is the identity |
| U2 | Erasure (`USER_ERASING`) **hard-deletes** every transaction the user has |
| U3 | Settings "Delete all transactions" **hard-deletes**, soft-deleted rows included, in one call |
| U4 | A transaction has a **date**, not a date and time (`DATE`) |
| U5 | The UI is the legacy v1.0 screen's content, rebuilt on the template packages; deltas in §6 |
| U6 | Categories: a slug enum defined once on the server, stored as plain `VARCHAR` with **no DB constraint**; labels served by the API; the web holds no category list |
| U7 | Adding by hand **warns on a duplicate** (409 + "Add anyway") |
| U8 | Ship a dev seed: the 50% N26 export from the research repo, anonymised and categorised, dates shifted by whole months to end in the current month; the user reviews the file before it is committed |
| U9 | No legacy data is migrated; the legacy database can be discarded |
| — | Sidebar order Home, Transactions, Chat; only this step adds Settings content; whichever PR is ready first merges first (from the brief) |

### Not in this step

Splitting, multiple currencies, inline editing, undo or a "recently deleted" view, export, bank
connections (feature doc §5). CSV upload and the AI labeler (step 4). Recurring *detection* —
`is_recurring` is a flag the user sets (step 5a detects). A `GET /transactions/{id}` (nothing
needs it). Searching the description (the feature doc searches the merchant). An index on
`category` or a partial index on active rows (one person's rows number in the thousands).

---

## 2. Data model

### `transaction`

Owned by the new `transaction` module. Model extends `BaseModel, UUIDPrimaryKeyMixin,
UserOwnedMixin, SoftDeleteMixin`.

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
    fingerprint        CHAR(64)         NOT NULL,   -- sha256 hex, §2.3
    created_at         TIMESTAMPTZ      NOT NULL,
    updated_at         TIMESTAMPTZ      NOT NULL,
    deleted_at         TIMESTAMPTZ
);
CREATE INDEX ix_transaction_user_id_date        ON transaction (user_id, date);
CREATE INDEX ix_transaction_user_id_fingerprint ON transaction (user_id, fingerprint);
-- plus ix_transaction_created_at, ix_transaction_deleted_at, ix_transaction_user_id from the mixins
```

Against legacy: `id` int → UUID v7; `user_id` str → UUID FK; `date` timestamptz → DATE (U4);
`category` native enum storing member names → `VARCHAR` slug (U6); `confidence_score` →
`confidence`; `fingerprint` nullable and stale after an edit → not null, recomputed on edit.
`merchant`, `amount`, `description`, `original_category`, `is_recurring` are unchanged.

### 2.1 Deletes

- **One or a batch:** soft (`deleted_at`). A soft-deleted row is invisible to every list, count,
  duplicate check and batch.
- **Delete all and erasure:** hard — one `DELETE FROM transaction WHERE user_id = :id`, soft-deleted
  rows included. Both call the same repository method (U2, U3). Nothing references a
  transaction, so removing rows breaks no foreign key; `SoftDeleteMixin`'s own docstring says
  personal data is hard-deleted.

### 2.2 Categories

Defined once, in `app/modules/transaction/schemas.py`:

- `CATEGORIES: list[tuple[str, str]]` — ordered `(slug, label)` pairs, the display order. The
  twenty of `categorisation.md` §3, e.g. `("income", "Income")`, `("food_groceries", "Food &
  Groceries")`, `("bars_restaurants", "Bars & Restaurants")`, …, `("miscellaneous",
  "Miscellaneous")`.
- `Category = StrEnum("Category", [(slug, slug) for slug, _ in CATEGORIES])` — built from it, so
  the two cannot disagree. Request and response schemas type the field as `Category`; OpenAPI
  publishes the enum and orval generates one TS `Category` union.
- The model's column is `str`; the database knows no list (U6).
- `CATEGORIES`, `Category` and the label lookup are exported from the module root (the seed and
  step 4 import them).

**Changing the list** is one edit to `CATEGORIES`; the pre-commit hook regenerates the
contract; the web needs nothing. Renaming a *label* touches nothing else. Renaming or removing a
*slug* also needs an `UPDATE transaction SET category = … WHERE category = …` revision for the
rows that hold it — that is the data, not the schema.

### 2.3 Fingerprint

```
sha256(f"{user_id}|{date:%Y-%m-%d}|{merchant.strip().casefold()}|{amount:.2f}|{(description or '').strip().casefold()}")
```

`amount` is the `Decimal` quantised to two places — never a float. Computed on create; recomputed
on every update that changes date, merchant, amount or description. Not unique. Uses: the
manual-add duplicate check (§3.3) and, in step 4, the import's skip-duplicates. A pure function in
the module, unit-tested against fixed vectors so step 4 cannot drift from it.

### 2.4 `"user".email`

`User.email` loses `unique=True`; `ix_user_email` stays, non-unique. Clerk owns email uniqueness
and `clerk_id` is the identity; nothing on the server looks a user up by email. No reclaim, no
Clerk call in JIT. `UserRepository.create_or_get`'s docstring drops the email-collision case;
`UserAlreadyExistsError` stays for its remaining cause (a `clerk_id` race whose re-fetch finds
nothing). `UserRepository.get_by_email` is removed: it was used only by its own tests, and with
duplicates allowed its `scalar_one_or_none` would raise.

### 2.5 Migrations

Two hand-checked autogenerated revisions, chained off `0c7838405158`:

1. `user_email_not_unique` — drop the unique index `ix_user_email`, recreate it non-unique.
   Downgrade restores the unique index (and fails if duplicates exist — acceptable for a dev
   downgrade).
2. `add_transaction` — the table and its indexes.

Each reverts on its own. On merging step 3 after this, nothing collides (step 3 adds no revision).

---

## 3. Server

### 3.1 The module

`app/modules/transaction/`:

| Slot | Holds |
|---|---|
| `__init__.py` | public surface: `router`, `transaction_service`, `Category`, `CATEGORIES`, `category_label`, `TransactionResponse`, `UserTransaction`, the exceptions; imports `handlers` for its side effect |
| `models.py` | `Transaction` |
| `schemas.py` | categories (§2.2), request/response schemas, `TransactionFilters`, `TransactionOrdering` |
| `repository.py` | every query, all filtered by `user_id` |
| `service.py` | orchestration, fingerprinting, confidence = 1 on manual writes, the duplicate check, batch count check |
| `dependencies.py` | `get_user_transaction` / `UserTransaction` — missing, soft-deleted or another user's → `TransactionNotFoundError` (404) |
| `exceptions.py` | `TransactionNotFoundError(NotFoundError)` `TRANSACTION_NOT_FOUND`; `DuplicateTransactionError(ConflictError)` `DUPLICATE_TRANSACTION` |
| `handlers.py` | `USER_ERASING` subscriber, inline → the hard delete-all |
| `router.py` | §3.2 |

The fingerprint function lives in `service.py`. No `domain` slot: creating one brings the R9
contract from `TODO.md` with it, and one pure function does not warrant that.

The service has one bulk-insert method that takes `confidence` and `original_category` (the
manual paths force `confidence = 1` and leave `original_category` null). The seed uses it now,
step 4's import later; it computes each row's fingerprint like every other write.

**Wiring** (each gated by a test): `app/api/v1/api.py` includes `transaction.router`;
`app/main.py` imports the module; `alembic/env.py` imports `app.modules.transaction.models`;
`pyproject.toml` gains `transaction`'s R1 contract forbidding `account.*` and `conversation.*`,
and `"app.modules.transaction.*"` is appended to the `account` and `conversation` R1 lists; R6
becomes

```toml
layers = [
    "app.modules.conversation | app.modules.transaction",
    "app.modules.account",
]
```

**Rate limit:** a `TRANSACTIONS` entry in the endpoint rate-limit settings
(`app/core/config.py`), used by every route. Step 3 edits other sections of that file
(`LLMSettings`, `MemorySettings`, `EvaluationSettings`); the second PR to merge takes a union.

### 3.2 Routes

`APIRouter(prefix="/transactions", tags=["transactions"])`. Named paths declared before
`/{transaction_id}`.

| Method, path | `operation_id` | Request → response |
|---|---|---|
| `GET /categories` | `listTransactionCategories` | → `list[CategoryResponse]` (`value: Category`, `label: str`), display order |
| `GET ""` | `listTransactions` | query §3.2.1 → `TransactionListResponse {items, total, offset, limit}` |
| `POST ""` | `createTransaction` | `TransactionCreate` → `TransactionResponse`, 201; 409 on a duplicate |
| `PATCH /batch` | `batchUpdateTransactionCategory` | `{ids, category}` → `{updated}` |
| `DELETE /batch` | `batchDeleteTransactions` | `{ids}` → `{deleted}` (soft) |
| `DELETE ""` | `deleteAllTransactions` | → `{deleted}` (hard) |
| `PATCH /{transaction_id}` | `updateTransaction` | `TransactionUpdate` → `TransactionResponse` |
| `DELETE /{transaction_id}` | `deleteTransaction` | → 204 (soft) |

`TransactionResponse`: `id`, `date`, `merchant`, `amount` (string), `description`,
`original_category`, `category`, `confidence`, `is_recurring`, `created_at`, `updated_at`. Not
`user_id`, `fingerprint` or `deleted_at`. Every field carries a `description`.

#### 3.2.1 List query

| Param | Type | Meaning |
|---|---|---|
| `date_from`, `date_to` | date | inclusive both ends |
| `category` | `list[Category]`, repeatable | any of |
| `amount_min`, `amount_max` | Decimal | inclusive, on the signed amount |
| `is_recurring` | bool | |
| `search` | str, ≤ 100 | merchant, case-insensitive substring; `%`, `_` and `\` escaped |
| `ordering` | `Literal["date","-date","amount","-amount","merchant","-merchant"]` | default `-date` |
| `offset`, `limit` | int | 0; 20, 1–100 |

Every ordering ends with `created_at DESC, id DESC` so pages are stable. `total` counts the
filtered, active rows.

#### 3.2.2 Input rules

- `merchant`: stripped, then 1–255. `description`: ≤ 1,000, stripped, empty → null.
- `amount`: `Decimal`, `max_digits=12`, `decimal_places=2`, no NaN/∞; a string on the wire in both
  directions.
- `category`: `Category`. `date`: ISO date.
- `confidence` and `original_category` are not in `TransactionCreate` or `TransactionUpdate`: only
  the seed and step 4 set them, through the service.
- `TransactionUpdate` is partial and reads `model_fields_set`: an omitted field is untouched, an
  explicit `null` on `description` clears it (a required field sent as `null` is a 422).
- `TransactionCreate` also takes `allow_duplicate: bool = false` (§3.3); it is not stored.
- Every manual write sets `confidence = 1`.

### 3.3 Duplicate check (U7)

`POST /transactions` computes the fingerprint and looks for an **active** row with the same
`(user_id, fingerprint)`. On a match and `allow_duplicate` false (the default) it raises
`DuplicateTransactionError` → 409, `details` carrying only `existing_transaction_id`. A fingerprint
match means date, merchant, amount and description already equal what the caller sent, so the
dialog words the notice from its own input; and an exception's context is logged, so merchant
text stays out of it. `allow_duplicate: true` in the body skips the check. Soft-deleted rows do not count.
Edits do not check.

### 3.4 Batches

`ids`: 1–100, distinct (a duplicate id is a 422). One statement:
`UPDATE … WHERE id = ANY(:ids) AND user_id = :me AND deleted_at IS NULL RETURNING id` (the batch
category update also sets `confidence = 1`; the batch delete sets `deleted_at`). If fewer ids
come back than were sent, the service raises `TransactionNotFoundError`, the session dependency
rolls back, and nothing changed — all or nothing, one query, the count real.

---

## 4. Web

### 4.1 Route and nav

- `apps/web/src/app/(dashboard)/transactions/page.tsx` (Server Component rendering the client
  view) and `loading.tsx` (skeleton).
- `apps/web/src/lib/hub-nav.ts`: `{ title: "Transactions", url: "/transactions", icon:
  ArrowLeftRightIcon }` directly after Home.
- The `(dashboard)/layout.tsx` inset container is untouched (condition 5); the only layout edit is
  the Settings tab (§4.5).

### 4.2 Components — `apps/web/src/components/transactions/`

| File | Does |
|---|---|
| `transactions-view.tsx` | `useUrlTableState` (filters, search, ordering, page in the URL), `useListTransactions`, toolbar + table/cards + pager, empty states, the bulk bar's actions |
| `transaction-columns.tsx` | selection, date, merchant, amount (negative red, positive green, EUR), category chip → category picker, confidence % (warning colour below 70%), row menu (Edit, Delete) |
| `transaction-filters.tsx` | `FilterPanel` fields: `DateFilterControl` presets (today, this week, this month, last month, custom), category multi-select, amount min/max, recurring switch; `FilterChip`s for active filters |
| `transaction-card.tsx` | the phone card: date, merchant, amount, category; no selection, no confidence |
| `transaction-form-dialog.tsx` | add and edit: date (`DatePicker`), merchant, amount, category, description, recurring; edit sends only changed fields; add mode handles the 409 (§4.4) |
| `bulk-category-dialog.tsx` | pick a category for the selection |
| `delete-transaction-dialog.tsx` | `AlertDialog` confirm, single or bulk |
| `use-categories.ts` | `useListTransactionCategories` with `staleTime: Infinity`; returns the ordered list and `label(slug)`, falling back to the slug while loading |

Empty states: no transactions at all → "No transactions yet" + **Add a transaction**; a filter
with no match → "No transactions match your filters" + **Clear filters**.

Against legacy (U5): filters in the URL, not `useState`; numbered pages of 20, not Prev/Next of
25; category filter takes several; the empty CTA adds rather than uploads (step 4 swaps it); bulk
delete is one batch call, not `Promise.allSettled`.

### 4.3 `@app/data-table` additions (generic — no transaction knowledge)

- **Row selection:** opt-in `enableRowSelection` on the shared table props; the core adds the
  checkbox column itself (as it does the expander). Selection holds only rows on screen: a page,
  filter, ordering or search change that removes a row deselects it, so a bulk action touches
  only visible rows and the 100 cap holds by construction.
- **`DataTableBulkBar`:** "N selected", Clear, and the page's actions from
  `renderBulkActions(selected, clear)`; shown while rows are selected, desktop only.
- **Phone layout:** a `renderCard(row)` prop; below 768px (`useIsMobile`, the app's one
  breakpoint) the body is a card list. Toolbar, chips and pager stay.
- **Filters:** `DateFilterControl` gains `presets` (today, this week — Monday first —, this
  month, last month, as a closed range); a new `FilterCheckboxGroup` picks several values from a
  fixed list (the category filter).

### 4.4 Mutations and errors

Every mutation invalidates the transaction list query on success. Errors toast through
`QueryProvider`, except the add dialog's 409 `DUPLICATE_TRANSACTION`, which it handles inline.
`QueryProvider`'s mutation cache toasts every failure today, so it gains an opt-out: a mutation
whose `meta.silentStatuses` lists a status is not toasted for it (`@app/api-client`,
`query-provider.tsx`). The notice:
"You already have a transaction on 3 Mar 2026 at Späti for −€4.50." with **Add anyway** (resend
with `allow_duplicate: true`) and **Cancel**. Changing any field clears the notice.

### 4.5 Settings

A **Data** tab in `SETTINGS_TABS` (`(dashboard)/layout.tsx`), its content an app component
`components/settings/data-settings.tsx`: **Delete all transactions** → `AlertDialog`
"Permanently deletes all N transactions. This cannot be undone." → `deleteAllTransactions` →
invalidate. Step 3 also edits `layout.tsx`; the second to merge takes a union.

### 4.6 `@app/ui` primitives

`alert-dialog`, `calendar` (the shadcn Base UI calendar), `checkbox`, `switch`, `textarea`. The
add/edit dialog's date is a `DatePicker` in `@app/components/forms/` — the shadcn Date Picker
pattern, `Popover` + `Calendar`, its value a local ISO date (decided with the user, 13 Oct 2026).
The filter's date bounds stay `DateFilterControl`'s native inputs. Condition 6 asks for the shadcn CLI;
`components.md` says the CLI cannot resolve this repo's alias and primitives are installed by
hand. The CLI is tried first; if it fails, they are installed by hand from the Base UI docs, and
the orchestrator is told so step 3 does the same. If step 3 merges one first, take
`template-base`'s copy.

---

## 5. Seed (U8)

### 5.1 The data

`server/data/transactions-seed.csv` (`server/CLAUDE.md`: seed data lives in `server/data/`, which
`.dockerignore` keeps out of the image) — columns `date, merchant, amount, description,
category, confidence, is_recurring, original_category`; `category` in slugs; `original_category`
the N26 `Type` (`Presentment`, `Direct Debit`, …).

Source: `personal-finance-reaserch/src/data/transactions_50pct.csv` (1,067 rows, Feb 2023 – Jan
2026, a raw N26 export). Prepared once by a script kept in the session scratchpad, **never
committed** (it must name what it masks):

- **Dropped:** `Partner Iban`, `Value Date`, `Account Name`, `Original Amount`, `Original
  Currency`, `Exchange Rate`.
- **Transfers, debits, MoneyBeam (~105 rows):** each counterpart a consistent stand-in
  ("Employer GmbH", "Landlord", "Friend A"); payment references made generic ("Salary
  02/2023").
- **Card payments (945 rows):** chains and online merchants keep their names; local shops lose
  street and number ("Späti Alt Moabit 106" → "Späti").
- **Amounts:** every amount × one random factor in [0.8, 1.2], drawn once, re-quantised to cents.
- **Categories:** from the merchant → category map of `pf-legacy/server/tests/data/test_transactions_400.csv`
  (covers 699 rows), the remaining 314 merchants assigned once by hand; `confidence` from that
  file, 0.9 for hand-assigned.
- **Recurring:** a short merchant list (salary, rent, subscriptions, insurance) set `true`.

**Gate:** the user reviews the finished file before it is committed — the repo is public.

### 5.2 The script

`server/scripts/seed_transactions.py`; `make -C server seed-transactions CLERK_ID=user_…`, and a
root `make seed-transactions` that delegates (listed in `make help`).

- Refuses unless `APP_ENV=development`. Resolves the user as a request does
  (`user_service.resolve_user`), so a Clerk user who has never signed in is JIT-provisioned.
- Replaces: the hard delete-all, then a bulk insert — rerunning resets rather than duplicates.
- Date shift: `months = (today.year*12 + today.month) − (newest.year*12 + newest.month)`; each row
  moves forward that many months, its day clamped to the month's length; rows after today are
  dropped.
- A slug the server no longer knows → `miscellaneous`, with one warning listing the slugs and row
  counts.
- Writes through `transaction_service` (fingerprints computed exactly as in-app); one statement
  per batch.

---

## 6. Testing

Server (load `server-testing`; one test file per slot file, R5):

- **account:** a second `clerk_id` provisioned onto a held email → 200, not 401 (written first,
  failing); a `user.created` webhook with that email succeeds.
- **repository/service (integration):** each filter and combinations; inclusive date bounds;
  repeated `category`; search escaping; every ordering and the tiebreak; soft-deleted rows never
  listed; fingerprint recomputed on edit, unchanged on a category-only edit; 409 and
  `allow_duplicate`; a soft-deleted twin is no duplicate; a batch with one missing or foreign id
  changes nothing; delete-all removes soft-deleted rows too.
- **fingerprint (unit):** fixed vectors.
- **routes:** another user's transaction → 404 on update, delete and both batches; 422 for
  `limit` > 100, 101 ids, duplicate ids, three decimal places, a blank merchant; amounts are
  strings both ways.
- **handler:** `USER_ERASING` leaves the user no `transaction` rows.
- **seed (unit):** month shift — clamping, year boundary, future rows dropped; CSV parsing,
  unknown slugs. **(integration):** seeds the container DB; row count and date range.
- **existing gates:** `test_module_contracts.py`, `test_owned_tables.py` (the mixin, no allowlist
  row), `test_openapi_contract.py`.

Web (load `web-app-testing`; every component with a branch):

- data-table: selection clears on page/filter change; bulk bar visibility; card layout below `sm`.
- filters → list query, multi-category included; confidence threshold colour; both empty states;
  form dialog add/edit diff and the duplicate notice; Settings delete-all confirm; `use-categories`
  label fallback.

---

## 7. Merge points with step 3

| File | Resolution when the second PR merges |
|---|---|
| `web-app/apps/web/src/lib/hub-nav.ts` | union: Home, Transactions, Chat |
| `web-app/apps/web/src/app/(dashboard)/layout.tsx` | union: step 3's chat-route treatment, this step's Settings tab |
| `server/app/core/config.py` | union: step 3's LLM/memory/eval settings, this step's `TRANSACTIONS` rate limit |
| `server/CLAUDE.md` | union: step 3's OpenRouter lines, this step's two GDPR lines |
| `web-app/packages/api-client/src/query-provider.tsx` | this step's `silentStatuses` opt-out; step 3 is not expected to touch it |
| `web-app/packages/ui` primitives and barrel | take `template-base`'s copy of any shared primitive |
| `server/openapi.json`, `generated/`, `uv.lock`, `pnpm-lock.yaml` | never hand-merged: `make gen-contract`, `uv lock`, `pnpm install` |

Untouched by this step: `server/app/modules/conversation/`, the chat UI, existing `conftest.py`
fixtures, `version` in `server/pyproject.toml`.

---

## 8. Risks

- **Seed data privacy.** The source is a real-looking bank export and the repo is public; the
  review gate in §5.1 is the control. Nothing from the source is committed before it.
- **No DB guard on `category`.** A writer bypassing the service could store an unknown slug. Every
  writer today (routes, seed) and in step 4 goes through the service; the web shows an unknown
  slug as itself.
- **`DELETE /transactions` is destructive.** Behind a confirm dialog and the user's own auth;
  rate-limited.

---

## 9. Docs moved in the PR

- **New** `docs/data-model/transaction.md`: why this shape, the sketch (§2), indexes, decisions
  (date only; slugs in `VARCHAR`, no DB constraint, list on the server, labels by API; the
  fingerprint recipe; soft one-by-one, hard for all and erasure; the manual duplicate check),
  deferred items, field map. `docs/data-model/README.md` gains the map row.
- `docs/data-model/account.md`: `ix_user_email` non-unique; decision D3 — Clerk owns email
  uniqueness, `clerk_id` is the identity.
- `docs/product/features/transactions.md`: date, not date and time; multi-category filter; the
  duplicate rule in §4 and §6's question closed; delete-all is permanent; empty-state CTA until
  step 4; Data model link.
- `docs/product/features/categorisation.md`: the list lives on the server and is served to the
  web; changing it is one edit plus an `UPDATE` for a renamed or removed slug; Data model link.
- `docs/BUGS.md`: the email-lockout entry removed. `docs/TODO.md`: the email-uniqueness entry
  removed; a step-4 entry added — the empty state's CTA becomes "Upload a CSV".
- `.claude/skills/web-app-patterns/references/data-tables.md`: row selection, the bulk bar,
  `renderCard`, date presets, `FilterCheckboxGroup`.
- `docs/architecture/server.md`: the module tree and the `USER_ERASING` subscriber row.
- `server/CLAUDE.md` GDPR section: `transaction` hard-deletes on erasure; a PII model whose rows
  nothing references may be hard-deleted by its subscriber instead of anonymised.
- `docs/ROADMAP.md`: row 2 → `complete` with the PR link.

Then this spec and its plan are deleted.
