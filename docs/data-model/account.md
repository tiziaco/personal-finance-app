# Account — Data Model

**Status:** shipped · **Owner:** Tiziano · **Last updated:** 29 Sep 2026
**Describes:** [`../product/features/account.md`](../product/features/account.md).
**Scope:** the `"user"` table — the platform's record of a person Clerk has told it about.
**Source of truth:** the code — `server/app/modules/account/models.py` and the Alembic
revisions `0c7838405158` (initial schema) and `b3f1c27a4e18` (`org_id` made nullable). The
sketch below was last brought in line with them on 29 Sep 2026; where the two disagree,
the code wins. The conventions every table follows are in [`README.md`](./README.md).

---

## 1. Approach

**One row per person Clerk has told the platform about.** A webhook usually creates it,
before the person signs in; JIT on the first request is the backstop. Webhooks keep it
current ([`../architecture/authentication.md`](../architecture/authentication.md)
§4).

**Two ids, two jobs.** `id` is the platform's own, and every relationship points at it;
`clerk_id` is used only at the authentication boundary, to find the row for a token.

**No role column.** The role lives in Clerk and arrives on the token
([`../architecture/authorization.md`](../architecture/authorization.md) §1), so there is nothing to keep in sync.

**Anonymised, not deleted, on erasure** — so every row that points at a person still points
at a valid one.

## 2. Schema sketch

```sql
CREATE TABLE "user" (
    id              VARCHAR     PRIMARY KEY,   -- str(uuid.uuid4()), app-side
    clerk_id        VARCHAR     NOT NULL,      -- unique; 'deleted_user_<first 8 chars of id>' after erasure
    org_id          VARCHAR,                   -- the active Clerk organization; NULL after erasure
    email           VARCHAR     NOT NULL,      -- unique; '<anonymous id>@anonymized.local' after erasure
    email_verified  BOOLEAN     NOT NULL,
    first_name      VARCHAR,
    last_name       VARCHAR,
    avatar_url      VARCHAR,
    last_synced_at  TIMESTAMPTZ NOT NULL,      -- Clerk's updated_at; orders webhook events
    anonymized_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL
);
```

## 3. Indexes

| Index | Unique | Serves |
|---|---|---|
| `ix_user_clerk_id` | yes | finding the row for a token — every authenticated request |
| `ix_user_email` | yes | one row per email |
| `ix_user_org_id` | no | the members of an organization |
| `ix_user_created_at` | no | recent sign-ups |
| `ix_user_anonymized_at` | no | finding erased rows |

## 4. Decisions

- **D1 — `org_id` is nullable** (`b3f1c27a4e18`). Erasure clears it: a supplier
  organization typically has a single portal contact, so an anonymised row that kept its
  organization would still single that person out. That is also why the table is on the
  tenancy allowlist in `test_tenant_tables.py` rather than carrying `TenantMixin`, whose
  `org_id` is `NOT NULL`.
- **D2 — anonymise, don't delete.** `conversation.user_id` keeps pointing at a valid row
  after erasure. `supplier.contact_id` is cleared, not kept: erasure unlinks the contact
  ([`supplier.md`](./supplier.md)).
- **D3 — `last_synced_at` is Clerk's timestamp, never the host clock.** Webhooks arrive in
  no guaranteed order, and an event older than the row is skipped; a host-clock value
  would make every later event look stale ([`../architecture/authentication.md`](../architecture/authentication.md)
  §4).

## 5. Deferred

- **A native `uuid` primary key** — [`../TODO.md`](../TODO.md), **Data model**.
- **A full-length `anonymous_id`** — today it uses 8 characters of the id;
  [`../TODO.md`](../TODO.md), **Erasure** (A6).
