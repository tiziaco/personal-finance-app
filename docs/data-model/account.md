# Account — Data Model

**Status:** shipped · **Owner:** Tiziano · **Last updated:** 13 Oct 2026
**Describes:** [`../product/features/account.md`](../product/features/account.md).
**Scope:** the `"user"` table — the platform's record of a person Clerk has told it about.
**Source of truth:** the code — `server/app/modules/account/models.py` and the Alembic
revisions `0c7838405158` (the initial schema) and `ab81d9d078e3` (email no longer unique). The
sketch below was last brought in line with them on 13 Oct 2026; where the two disagree,
the code wins. The conventions every table follows are in [`README.md`](./README.md).

---

## 1. Approach

**One row per person Clerk has told the platform about.** A webhook usually creates it,
before the person signs in; JIT on the first request is the backstop. Webhooks keep it
current ([`../architecture/authentication.md`](../architecture/authentication.md)
§4).

**Two ids, two jobs.** `id` is the platform's own, and every relationship points at it;
`clerk_id` is used only at the authentication boundary, to find the row for a token.

**No role: every user is equal**
([`../architecture/authorization.md`](../architecture/authorization.md) §1), and no organisation either — the row is the tenant.

**Anonymised, not deleted, on erasure** — so every row that points at a person still points
at a valid one.

## 2. Schema sketch

```sql
CREATE TABLE "user" (
    id              UUID        PRIMARY KEY DEFAULT uuidv7(),
    clerk_id        VARCHAR     NOT NULL,      -- unique; 'deleted_user_<id>' after erasure
    email           VARCHAR     NOT NULL,      -- not unique: Clerk owns uniqueness; '<anonymous id>@anonymized.local' after erasure
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
| `ix_user_email` | no | looking a row up by email by hand — nothing on the server does |
| `ix_user_created_at` | no | recent sign-ups |
| `ix_user_anonymized_at` | no | finding erased rows |

## 4. Decisions

- **D1 — anonymise, don't delete.** `conversation.user_id` keeps pointing at a valid row
  after erasure.
- **D2 — `last_synced_at` is Clerk's timestamp, never the host clock.** Webhooks arrive in
  no guaranteed order, and an event older than the row is skipped; a host-clock value
  would make every later event look stale ([`../architecture/authentication.md`](../architecture/authentication.md)
  §4).
- **D3 — email is not unique (13 Oct 2026).** Clerk owns email uniqueness and `clerk_id` is the
  identity. A unique `email` let a stale row — a deletion or an email change whose webhook was
  missed — lock the next account with that address out with a 401. Nothing on the server looks a
  user up by email, so nothing depends on it being unique. Rejected: reclaiming the stale row in
  JIT when Clerk no longer has its `clerk_id`, which costs a Clerk call on a collision for a
  guarantee nothing reads.
