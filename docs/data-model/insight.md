# Insight — Data Model

**Status:** shipped · **Owner:** Tiziano · **Last updated:** 16 Oct 2026
**Describes:** [`../product/features/insights.md`](../product/features/insights.md).
**Scope:** the `insight_set` table — one user's current set of AI-written insights.
**Source of truth:** the code — `server/app/modules/insights/models.py` and the Alembic
revision `a4c8e1f27b36`. The sketch below was last brought in line with them on
16 Oct 2026; where the two disagree, the code wins. Conventions: [`README.md`](./README.md).

---

## 1. Approach

**One row per user, holding the whole set as one JSON document, replaced whole.** A
generation writes the set with a single `INSERT … ON CONFLICT (user_id) DO UPDATE`, so two
generations at once both succeed and the later write wins; no lock is needed for one user.
The set is always read whole and replaced whole, and its shape follows the prompt, so a row
per insight would add a join and a delete-then-insert for nothing.

**What makes a set stale is not stored here.** `GET /insights` compares `generated_at` with
the latest `updated_at` over the user's transaction rows, soft-deleted included
(`transaction_service.activity`), and with the calendar month.

## 2. Schema sketch

```sql
CREATE TABLE insight_set (
    id                     UUID         PRIMARY KEY DEFAULT uuidv7(),
    user_id                UUID         NOT NULL REFERENCES "user" (id),  -- unique: one set per user
    generated_at           TIMESTAMPTZ  NOT NULL,
    reference_month        VARCHAR(7)   NOT NULL,   -- YYYY-MM, the finished month the set is about
    baseline_months        INTEGER      NOT NULL,   -- how many earlier months with data were "the usual" (0–6)
    month_to_date_through  DATE,                    -- last day of the month-so-far figures; null when none
    prompt_version         VARCHAR(16)  NOT NULL,   -- the prompt that wrote it, e.g. 'v1'
    insights               JSONB        NOT NULL,   -- the array of insights, below
    created_at             TIMESTAMPTZ  NOT NULL,
    updated_at             TIMESTAMPTZ  NOT NULL
);
```

Each element of `insights`, as `InsightResponse` in `server/app/modules/insights/schemas.py`:

```json
{
  "section": "spending | recurring | savings | anomalies | comparisons",
  "severity": "info | low | medium | high | critical",
  "period": "month | month_to_date",
  "summary": "one sentence",
  "narrative": "one to three sentences",
  "key_figure": {"kind": "amount | percent | count", "value": "312.40", "qualifier": "in September"},
  "link": {"kind": "recurring | category | merchant", "category": "<slug>", "merchant": "<name>"}
}
```

`key_figure` and `link` may be null. An empty array is a valid set.

## 3. Indexes

| Index | Unique | Serves |
|---|---|---|
| `ix_insight_set_user_id` | yes | reading a user's set; the `ON CONFLICT` target |
| `ix_insight_set_created_at` | no | the `BaseModel` convention |

## 4. Decisions

- **D1 — JSONB, not a row per insight (16 Oct 2026).** The set is read and replaced as a
  unit and its shape is the prompt's; storing it as one document keeps a generation to one
  statement and lets the insight's fields change with the prompt without a migration.
- **D2 — `insight_set` carries `UserOwnedMixin`, its `user_id` redeclared unique** (one set
  per user).
- **D3 — hard-deleted, never anonymised (16 Oct 2026).** The set quotes merchants and
  amounts from the user's transactions. It is deleted with them:
  on Settings' "delete all transactions", by an inline subscriber to
  `transaction.all_deleted` ([`transaction.md`](./transaction.md) D4); and on account
  erasure, by an inline subscriber to `account.user_erasing`. Both run in the publisher's
  transaction, so the set cannot outlive the rows.
- **D4 — no history (16 Oct 2026).** A new generation overwrites the old set. A failed
  generation writes nothing, so the previous set stays.
- **D5 — the prompt version is stored with the set.** A set's wording can be traced to the
  prompt that produced it (`server/app/agents/insights/prompts/`).

## 5. Deferred

- **Past sets.** Nothing keeps them; a history would be a second table, brought back by a
  feature that shows how readings changed over time.
