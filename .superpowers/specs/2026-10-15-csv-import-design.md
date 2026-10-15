# CSV import, the labeller and recurring detection — design

**Roadmap:** step 4 · **Branch:** `feat/csv-import` → PR into `template-base` · **Date:** 15 Oct 2026
**Reads against:** [`csv-import.md`](../../docs/product/features/csv-import.md),
[`categorisation.md`](../../docs/product/features/categorisation.md),
[`data-model/transaction.md`](../../docs/data-model/transaction.md),
[`architecture/server.md`](../../docs/architecture/server.md).
**Built beside:** step 5a (analytics dashboard). The wave's conditions are in `.superpowers/BRIEF.md` §3; this
design keeps every one of them.

---

## 1. Outcome

One person takes a bank's CSV export — their own N26-style file or a German one
(`;`, `15.01.2026`, `-1.234,56`, Windows-1252) — from upload to categorised, deduplicated rows in
under a minute, and is told about every row that was not saved and why.

Decided before brainstorming (15 Oct), not reopened: the import lives in the `transaction`
module; no undo and no import-id column; step 4 owns recurring detection — a deterministic rule in
`transaction`'s domain, the stored `is_recurring` flag the one source of truth, a user's value never
overwritten, provenance stored; EUR only.

Decided in brainstorming (15 Oct):

| Question | Decision |
|---|---|
| Formats | Inferred per file: delimiter, encoding (UTF-8, fallback Windows-1252), date format and decimal style per column. Shown in the review, not chosen by hand. |
| Duplicates | Count-matched: a fingerprint the file holds *n* times and the user holds *k* active times imports `max(0, n−k)`. |
| Recurring rule | Thresholds in §4.3. |
| Manual add | Only a ticked Recurring box is a `user` assertion; unticked is `detected`. |
| Labeller failure | Partial failure files those rows under Miscellaneous at 0.3; total failure saves nothing, keeps the upload, answers 503. |
| Confirm UX | The dialog stays and can be closed; the import carries on and a toast reports it. |
| Layout | A feature sub-package `transaction/imports/` (§3). |
| Held uploads | One per user; a new upload replaces the held one. Multi-file selection is later work. |
| `merchant_key` | A stored column, normalised as §4.2. |
| Known-merchant confidence | 0.95, so 1.0 keeps meaning "the user chose it". |

## 2. Data model — one Alembic revision, down-revision `09aea922f9b1`

### 2.1 `transaction` — two new columns

```sql
merchant_key      VARCHAR(255) NOT NULL   -- normalise_merchant(merchant); recomputed with the fingerprint
recurring_source  VARCHAR(16)  NOT NULL   -- 'detected' | 'user'; validated by the app only (as D2)
-- index ix_transaction_user_id_merchant_key (user_id, merchant_key)
```

- The revision backfills `merchant_key` in Python (`normalise_merchant` over every row, soft-deleted
  ones too) and `recurring_source = 'detected'` through a server default it then drops — the app sets
  every value; there is no DB default. Existing `is_recurring` values stand until the rule next runs
  for their merchant.
- A change to `normalise_merchant` needs a backfill revision, as a slug rename does (D2).
- `TransactionImport.is_recurring` becomes `Optional[bool] = None`: `None` lets the rule decide, a
  bool is a `user` assertion. The seed script passes a bool from its CSV, so it is unchanged and its
  rows are `user` (condition 3).

### 2.2 `csv_mapping_profile` — a remembered mapping

```sql
CREATE TABLE csv_mapping_profile (
    id          UUID        PRIMARY KEY DEFAULT uuidv7(),
    user_id     UUID        NOT NULL REFERENCES "user"(id),
    column_key  CHAR(64)    NOT NULL,   -- sha256 of the header names: stripped, casefolded, sorted, joined by U+001F
    mapping     JSONB       NOT NULL,   -- {"Buchungsdatum": "date", "Betrag": "amount", "Notiz": "ignore", …}
    created_at  TIMESTAMPTZ NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL,
    UNIQUE (user_id, column_key)
);
```

`UserOwnedMixin`. Upserted by every successful confirm with the confirmed mapping. Keyed per user and
column set, not per bank name: two banks with identical headers share a profile.

### 2.3 `csv_upload` — the held upload

```sql
CREATE TABLE csv_upload (
    id          UUID        PRIMARY KEY DEFAULT uuidv7(),   -- the upload_id confirm takes
    user_id     UUID        NOT NULL UNIQUE REFERENCES "user"(id),
    content     TEXT        NOT NULL,   -- the decoded file
    expires_at  TIMESTAMPTZ NOT NULL,   -- created + 30 minutes
    created_at  TIMESTAMPTZ NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL
);
```

- `UserOwnedMixin`. One per user: an upload upserts on `user_id` with a new `id`, so the previous
  upload's confirm answers 404. A confirm hard-deletes the row; an expired row answers 404 on read.
- Nothing derived is stored: delimiter, formats and the mapping are re-inferred on confirm
  (deterministic).
- **Deferred:** an abandoned upload's text stays until the user's next upload or erasure. A sweep
  across users breaks R7 and needs the worker in `TODO.md` ("Server — events beyond the request");
  that worker brings it back.

### 2.4 Erasure

`transaction`'s `USER_ERASING` subscriber also hard-deletes the user's `csv_mapping_profile` and
`csv_upload` rows, inline, beside the transaction delete. Nothing references either table.

## 3. Layout

`transaction` grows a feature sub-package. Every root slot stays a file: `service.py`, `repository.py`
and `schemas.py` must (condition 2), and `router.py` and `models.py` have no need to change shape.

```
app/modules/transaction/
  __init__.py            # + the imports router; + the exceptions another module may catch
  service.py             # + recurring re-run on every write; count_active_by_fingerprints; import_many
  repository.py          # + count_active_by_fingerprints, rows for merchant keys, set_recurring_for_ids
  schemas.py             # TransactionImport.is_recurring Optional
  models.py              # + merchant_key, recurring_source
  handlers.py            # + delete profiles and held uploads on USER_ERASING
  domain/                # pure (R9)
    __init__.py
    fingerprint.py       # moved from service.py; service.py re-exports `fingerprint`
    merchant.py          # normalise_merchant
    recurring.py         # detect_recurring
    dedupe.py            # plan_count_matched
  imports/               # the feature sub-package
    __init__.py          # router, import_service
    router.py            # tag "transaction-imports"
    service.py           # upload, confirm
    repository.py        # csv_upload, csv_mapping_profile
    schemas.py           # ImportPreview, ImportResult, ImportConfirm, …
    models.py            # CsvUpload, CsvMappingProfile
    domain.py            # pure (R9): decode, sniff, parse, column profiles, sample rows, value parsers
    exceptions.py
```

**Direction.** `imports` calls the transaction core (`transaction_service`, the domain); the core
never imports `imports`. Rows are written only through `transaction_service.import_many`, so an import
cannot create a row a manual add could not.

**Wiring.**
- `alembic/env.py` imports `app.modules.transaction.imports.models` (R8).
- `test_owned_tables.py` sees both tables through `UserOwnedMixin` (R7).
- The R1 contracts already cover `app.modules.transaction.*`; check that `test_module_contracts.py`
  does not mistake the sub-package for a module.
- **R9 contract** (condition 9): added with `TODO.md`'s wording — `app.modules.*.domain` may not import
  `sqlmodel`, `sqlalchemy` or `fastapi` — plus `app.modules.*.*.domain` as a second source pattern
  in the same contract (approved by the orchestrator, 15 Oct). Delete the `TODO.md` entry. Send the
  exact `pyproject.toml` block to `orchestrator` once written.
- `docs/architecture/server.md` §2 gains one paragraph: a feature sub-package as a third way a module
  grows (approved by the orchestrator, 15 Oct; §2 is step 4's for this wave). §8's events table gains
  the new erasure work.

## 4. Domain rules (pure, `transaction/domain/`)

### 4.1 Fingerprint

Unchanged (D3). Moves to `domain/fingerprint.py`; `service.fingerprint` stays importable.

### 4.2 `normalise_merchant(raw) -> str`

In order:

1. Unicode NFKC, then casefold.
2. Keep the part before a `|`.
3. Strip a payment-processor prefix: `paypal *`, `sumup *` (any spacing before `*`), `zettle_`,
   `lsp*`, `spc*`, `sq *`; `ubr*` becomes `uber`.
4. Strip a web-domain suffix (`.com`, `.de`, `.eu`, `.it`, `.co.uk`) and a legal-form suffix
   (`gmbh`, `ag`, `se`, `kg`, `bv`, `b.v.`, `ltd`, `inc`, `srl`, `spa`).
5. Drop trailing tokens containing three or more digits.
6. Punctuation other than `&` becomes a space; whitespace collapses; trim. Empty → the casefolded raw
   text.

Fixed vectors (the test table):

| Raw | Key |
|---|---|
| `PAYPAL *NETFLIX 4029357733` | `netflix` |
| `NETFLIX.COM` | `netflix` |
| `Netflix` | `netflix` |
| `FEATHER - INSURANCE` | `feather insurance` |
| `REWE Markt GmbH 3112` | `rewe markt` |
| `REWE` | `rewe` |
| `Netflix International B.V.` | `netflix international` |
| `1&1 Telecom` | `1&1 telecom` |

Conservative by design: no fuzzy matching. A missed merge loses a series; a wrong merge invents one.

### 4.3 `detect_recurring(rows) -> dict[id, bool]`

Input: one merchant key's active rows as plain values `(id, date, amount, is_recurring, source)`.

1. Split by sign: money in and money out are judged apart.
2. **Amount clusters.** Sort by amount; a row joins a cluster when it is within ±15 % of the
   cluster's median, with at least €1 of slack.
3. **Cadence.** Sort a cluster by date and take the gaps between consecutive rows. A gap fits a
   cadence when it falls in the cadence's window, or in twice that window (one skipped period). The
   cluster is a series when at least 75 % of its gaps fit one cadence:

   | Cadence | Window (days) | Minimum rows |
   |---|---|---|
   | weekly | 6–8 | 3 |
   | monthly | 26–35 | 3 |
   | quarterly | 84–98 | 3 |
   | yearly | 350–380 | 2 |

4. Every row in a qualifying cluster is `true`; every other row is `false`.
5. `user` rows count as evidence in steps 2–3, and are left out of the output, so never changed.

### 4.4 `plan_count_matched(fingerprints, existing_counts) -> list[bool]`

For each fingerprint in file order, keep the row while fewer than `n − k` of its copies have been
kept. Two identical coffees in a file import as two; re-importing the same file imports nothing.

### 4.5 When the rule runs

In `transaction_service`, in the writing session, before the flush. It loads the active rows for the
affected keys, calls `detect_recurring`, and updates only `detected` rows whose value changed, in one
statement. A response that returns the written row returns its value after the rule.

| Write | Keys re-judged | `recurring_source` written |
|---|---|---|
| create | the new row's | `user` if `is_recurring` is true, else `detected` |
| update | the old key, and the new one if the merchant changed | `user` if the patch includes `is_recurring` |
| delete one, batch delete | the deleted rows' | — |
| batch recategorise | none | — |
| `import_many` | every key in the batch | `user` where the row carries a bool, else `detected` |
| delete all, erasure | none | — |

## 5. The import flow

### 5.1 Routes

`transaction/imports/router.py`, tag `transaction-imports`, mounted before `/{transaction_id}`. Both
routes are limited to 10 a minute per user: the decorator's `key_func` keys on the caller's
`request.state.clerk_id` (set by `AuthMiddleware`). Every other route keeps the limiter's IP key.

| Route | operationId | Answers |
|---|---|---|
| `POST /transactions/imports` (multipart `file`) | `uploadTransactionsCsv` | 201 `ImportPreview` |
| `POST /transactions/imports/{upload_id}/confirm` | `confirmTransactionsImport` | 200 `ImportResult` |

`ImportPreview`: `upload_id`, `filename`, `row_count`, `mapping_source` (`remembered` | `proposed` |
`none`), `columns[]` — `name`, `proposed_field` (`date` | `merchant` | `amount` | `description` |
`original_category` | `recurring` | `ignore`), `empty_rate` (0–1), `date_format` (nullable, e.g.
`dd.mm.yyyy`), `amount_style` (nullable, `1.234,56` | `1,234.56`) — and `sample_rows` (≤ 3, each a
list of cells in column order).

`ImportConfirm`: `mapping: {column: field}`.

`ImportResult`: `imported`, `skipped_duplicates`, `uncategorised`, `rejected[]` — `row` (1-based, the
header is row 1), `reason`.

### 5.2 Upload

1. Refuse with 422 `INVALID_IMPORT_FILE` and the reason: a name not ending `.csv` (any case); more
   than 5 MB.
2. Decode UTF-8 (BOM-aware), falling back to Windows-1252.
3. Sniff the delimiter among `,` `;` tab `|`; parse with the stdlib `csv` module.
4. Refuse: no header; blank or duplicate header names; no data rows; more than 3,000 data rows. A
   trailing column with no name and no values is dropped.
5. Profile each column: empty rate; the best date format and its parse share; the amount style and
   its parse share.
6. Mapping: the user's profile for this `column_key` → `remembered`. Otherwise the mapping agent
   (§6.2) → `proposed`, validated: known fields only, each non-`ignore` field at most once, an omitted
   column is `ignore`. Agent failure → every column `ignore`, `none`.
7. Upsert `csv_upload` (30-minute expiry) and answer the preview.

### 5.3 Confirm

The route takes no `DbSession`. It opens short sessions from `request.app.state.session_factory` so
no pool connection idles through the model calls.

1. **Read** (session 1): the held upload, or 404 `IMPORT_UPLOAD_NOT_FOUND` (missing, expired,
   another user's). Validate the mapping or 422 `INVALID_IMPORT_MAPPING`: date, merchant and amount
   mapped; each field at most once; only columns the file has. Re-parse.
2. **Rows.** Parse each row with the column's inferred date format and amount style. Reject, into
   `rejected[]`, a row with an unreadable date, an unreadable amount or an empty merchant. A recurring
   cell reads `true/yes/ja/si/sì/1/x` as true and `false/no/nein/0` as false, case-insensitive;
   anything else, blank included, is `None` for that row, and the rule decides.
3. **Dedupe.** Fingerprint each row; one query (`transaction_service.count_active_by_fingerprints`)
   counts the user's active rows per fingerprint;
   `plan_count_matched` keeps the rest. Done before labelling.
4. **Label** (no session): §6.3. All batches failed → 503 `CATEGORISATION_UNAVAILABLE`; nothing saved,
   the upload kept.
5. **Write** (session 2, one transaction): `DELETE … RETURNING` the held upload — none returned is a
   404 (a second confirm); `transaction_service.import_many`; upsert the profile; the rule re-runs
   inside `import_many` (§4.5); commit.
6. Answer `ImportResult`. Log `transactions_imported` with counts only.

Dates: a value with a time keeps its date as written. EUR only: a currency symbol or code in an amount
cell is stripped; a column of another currency is not detected.

### 5.4 Value parsing (`imports/domain.py`)

- **Dates**, tried per column: `%Y-%m-%d`, `%d.%m.%Y`, `%d.%m.%y`, `%d/%m/%Y`, `%m/%d/%Y`, `%Y/%m/%d`,
  `%d-%m-%Y`, and ISO date-times. The format that parses the most non-empty cells wins; a tie goes
  day-first.
- **Amounts**: strip spaces, `€` and `EUR`; a trailing minus (`12,50-`) is a leading one. Style per
  column: the one that parses the most non-empty cells (`1.234,56` or `1,234.56`). Quantised to two
  places.
- **Sample rows**: up to three, chosen greedily to cover the most still-uncovered non-empty columns,
  ties to the earliest row, filled in file order, returned in file order (legacy's rule).

### 5.5 Exceptions (`imports/exceptions.py`)

| Exception | Status | Code |
|---|---|---|
| `InvalidImportFileError` | 422 | `INVALID_IMPORT_FILE` |
| `InvalidImportMappingError` | 422 | `INVALID_IMPORT_MAPPING` |
| `ImportUploadNotFoundError` | 404 | `IMPORT_UPLOAD_NOT_FOUND` |
| `CategorisationUnavailableError` | 503 | `CATEGORISATION_UNAVAILABLE` |

No file content and no merchant text in an error's details.

## 6. The agents (`server/app/agents/`)

### 6.1 Shared

- Plain async functions, not graphs. Neither imports `transaction` (R2): inputs and outputs are
  plain values.
- A tool-less `LLMService` instance, not the chatbot's singleton: the registry, tenacity retries and
  model fallback. Closes the `TODO.md` entry "Direct `ChatOpenAI` use".
- Answers parsed as JSON and validated with Pydantic; invalid JSON is a failed attempt.
- Every call traced in Langfuse with the user id and the upload id, through a `create_trace_config`
  helper beside `create_graph_config`. Same exposure as chat (`TODO.md`, erasure finding A2).

### 6.2 `agents/csv_mapping/` — `propose_mapping(columns, samples) -> dict[str, str] | None`

Input: column names with empty rates and inferred formats; up to three sample rows, each cell capped
at 100 characters. Output: `{column: field}`, or `None` on failure. Validation is the import's (§5.2).

### 6.3 `agents/transaction_labeler/` — `label(merchants, categories) -> LabelResult`

- **Input:** one item per `merchant_key` — a representative raw merchant, a sample description, the
  bank's original category, a typical signed amount (a decimal, not legacy's int). `categories` is the
  `(slug, label)` list from `CATEGORIES`.
- **Known merchants** first: legacy's 129 entries as `key → slug`, matched on whole tokens of the
  merchant key. Confidence 0.95.
- **The LLM** for the rest: 50 merchants a batch, at most 5 batches at once. One prompt, legacy's v2
  wording, versioned `v2` on the trace; v1 is dropped. The model answers slugs; a label is accepted and
  mapped.
- **Fallbacks** — `miscellaneous` at 0.3, counted in `uncategorised`: an unknown category, a merchant
  the model skipped, every merchant of a failed batch.
- **`LabelResult`:** `key → (slug, confidence)`, the fallback count, and whether every LLM batch
  failed. No batches (everything known) is not a failure.
- No `is_recurring`; no learning from corrections.

## 7. Web — `/transactions`

All inside `components/transactions/` and the page; no new `@app/ui` primitive; no hand-written
`api-client` file changes (conditions 5–7).

- **Entry points.** An **Import CSV** button (upload icon) beside **Add transaction**. The empty state
  leads with **Upload a CSV**, then "or add a transaction" (closes the `TODO.md` entry).
- **`ImportCsvDialog`**, four steps:
  1. **Choose** — a drop zone, `accept=".csv"`. The client refuses a non-`.csv` name or more than
     5 MB before sending. "Reading your file…" while uploading. A 422 shows inline
     (`meta.silentError`).
  2. **Review** — file name, row count, and where the mapping came from ("Using your saved mapping
     for these columns" / "Suggested by AI — check it" / "Couldn't suggest a mapping — pick the
     columns yourself"). One row per file column: name, up to two example values with the inferred
     format beneath, empty rate when above 0, and a **Maps to** select. Picking a field another column
     holds moves it; that column becomes Ignore. **Import N rows** is disabled, with "Map a date, a
     merchant and an amount", until those three are mapped. **Choose another file** returns to step 1.
     Rows stack as cards on a phone.
  3. **Importing** — "Importing and categorising N rows… You can close this; the import carries on."
  4. **Result** — Imported, Skipped as duplicates, Filed under Miscellaneous, Rejected; the rejected
     rows as "Row 14: unreadable date `31.02.2026`", the first 100 and "+N more"; **Done**.
- **Closing mid-import.** The confirm mutation has a `mutationKey` and hook-level callbacks; it
  finishes after unmount, refetches the list through `useRefreshTransactionsOnSuccess` (condition 4),
  and toasts the counts with a **View details** action that reopens the dialog on the result, read
  from the mutation cache with `useMutationState`.
- **Confirm errors, inline:** 404 → "This upload has expired — choose the file again", back to step 1;
  503 → "Categorisation isn't available right now. Your file is kept for 30 minutes", **Try again**;
  422 → the message, on step 2.

## 8. Testing

**Server unit** (pure):
- `domain/test_merchant.py`: §4.2's table.
- `domain/test_recurring.py`: each cadence at its window edges; the ±15 % band; a skipped period; 2
  vs 3 rows; yearly with 2; `user` rows unchanged but counted; income and expense apart; legacy's
  400-row fixture (`pf-legacy/server/tests/data/test_transactions_400.csv`, copied) — BVG, the
  insurance, rent and salary flagged, a café not.
- `domain/test_fingerprint.py`: the existing vectors, moved.
- `domain/test_dedupe.py`: (n, k) cases.
- `imports/test_domain.py`: delimiter sniffing; UTF-8, BOM and Windows-1252; each date format and the
  day-first tie; amount styles, trailing minus, `€`; recurring cells; sample selection (legacy's cases).
- `tests/unit/agents/`: whole-token known-merchant matching; batching; each fallback; the all-failed
  flag; mapping-answer validation. The LLM stubbed.

**Server integration** (testcontainers Postgres):
- `imports/test_router.py`: upload → confirm end to end; a remembered mapping skips the agent; each
  422; 404 for expired, another user's, and a second confirm; 503 keeps the upload; partial failure
  counted; count-matched duplicates across a re-import; a new upload replaces the held one; the
  per-user limit.
- `test_service.py`: the rule after create, update (both keys on a merchant change), delete, batch
  delete and import; provenance per §4.5.
- `test_handlers.py`: erasure removes profiles and held uploads.
- Gates: `test_owned_tables.py`, `test_openapi_contract.py`, `test_module_contracts.py`,
  `lint-imports` with the R9 contract, `make check-contract`.

**Web** (Vitest): `import-csv-dialog.test.tsx` — the client refusal; review rendering every column
with examples and formats; moving a taken field; Import disabled until the three are mapped; the
result; 404, 503 and 422 inline. `transactions-table.test.tsx` — the empty state offers Upload a CSV.

**By hand**, on this worktree's stack: a German-format file, an N26-style file, then the second one
again (all skipped as duplicates).

## 9. Docs that move before the PR

- `docs/data-model/transaction.md`: the two tables and two columns in the sketch and indexes; D6
  (`recurring_source` and the rule), D7 (`merchant_key`), D8 (mapping profiles), D9 (held uploads, one
  per user, and the deferred sweep); D3 gains count-matching; D5 is unchanged. The field map gains
  the import's fields.
- `docs/data-model/README.md` §1: the `transaction` row lists the new tables.
- `docs/product/features/csv-import.md`: Data model line; formats inferred and Windows-1252 accepted
  (§4); count-matched duplicates; required-field check at confirm; the result screen; "Not built"
  gains multi-file selection; the European-amounts open question closes.
- `docs/product/features/categorisation.md` §4: 0.95 for known merchants; one prompt version;
  failure behaviour; a mapped recurring column is honoured.
- `docs/architecture/server.md`: §2 the sub-package paragraph; §8 the erasure row.
- `docs/TODO.md`: delete the R9 entry, the transactions empty-state entry, and the two step-4 port
  entries ("Services returning `None`", "Direct `ChatOpenAI` use").
- `docs/ROADMAP.md` row 4: `complete — [PR #N](url) into template-base; reaches main at Cutover`.
- Then delete this spec and the plan.
