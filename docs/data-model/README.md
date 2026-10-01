# Data model

**Status:** draft — each area's doc carries its own status · **Owner:** Tiziano ·
**Last updated:** 29 Sep 2026
**Scope:** what the platform stores, one doc per server module, and the conventions every
table follows. How a feature *behaves* is in [`../product/features/`](../product/features/).

---

## 1. The map

| Data-model doc | Describes | Module | Tables | State |
|---|---|---|---|---|
| [`account.md`](./account.md) | [`account`](../product/features/account.md) | `account` | `"user"` | built |
| [`conversation.md`](./conversation.md) | no feature doc yet | `conversation` | `conversation` | built |
| [`supplier.md`](./supplier.md) | [`suppliers`](../product/features/suppliers.md) | `supplier` | `supplier` | built — the company row and the contact link |

**A feature doc is named for the product area** (`suppliers.md`), **a data-model doc for the
server module that owns its tables** (`supplier.md`). The mapping is not one-to-one: a doc
covers the features that share its tables. A doc that outgrows one file splits by server
module ([`../architecture/server.md`](../architecture/server.md)) — every table belongs to exactly
one — **never by feature**.

**Links run both ways.** A feature doc names its data-model doc under **Data model** in its
status block; a data-model doc names the feature docs it serves under **Describes**.

## 2. What a data-model doc holds

- **Why this shape** — the approach, and the alternatives rejected.
- **A schema sketch** in SQL. It stays after the tables exist: it is the quickest way to
  read the model whole. It is not a migration.
- **Indexes**, and the query each one serves.
- **Modelling decisions**, numbered and dated.
- **What was deferred**, and what brings each item back.
- **A field map**, where the feature doc lists fields: each field to where it is stored.

**The code is the source of truth.** Once a table exists, its model and the Alembic
revisions win any disagreement with the sketch. Each doc's status block says so, and gives
the date the sketch was last brought in line with the code — a sketch that looks
authoritative and is not is worse than none.

## 3. Conventions

Every table follows these. A doc lists only its own table's exceptions.

- **Singular table names**, SQLModel's default — no model sets `__tablename__`. `user` is
  a reserved word in PostgreSQL: unquoted, `FROM user` returns the `current_user`
  function's row instead of erroring. Hand-written SQL writes `"user"`.
- **UUID v7 primary keys** in a native `uuid` column, from `UUIDPrimaryKeyMixin`
  (`server/app/models/base.py`): generated app-side with `uuid_utils.compat.uuid7()`, with
  `DEFAULT uuidv7()` as the backstop for raw SQL. `uuidv7()` needs **PostgreSQL 18**. Ids
  are `uuid.UUID` inside the server and text only where they leave it — `conversation.id`
  is also the LangGraph thread id, stored there as text.
- **Every table extends `BaseModel`** (`server/app/models/base.py`): `created_at` and
  `updated_at`, `TIMESTAMPTZ`, set app-side; `created_at` is indexed, `updated_at`
  refreshed on every write.
- **Personal data is anonymised, never soft-deleted.** `AnonymizableMixin` clears the
  personal fields, keeps the row id so foreign keys hold, and stamps `anonymized_at`.
  `SoftDeleteMixin` (`deleted_at`) is for rows that must be retained and hidden. Each doc
  says which its table uses, and why.
- **Tenancy is a test, not a convention.** A table owned by one organization carries
  `TenantMixin`, or sits in the allowlist of
  `server/tests/unit/models/test_tenant_tables.py` with a reason —
  [`../architecture/server.md`](../architecture/server.md) §9. Each doc states its own table's entry.
- **Clerk's user id is the external key**, stored on `"user".clerk_id` only. Every foreign
  key references the internal `user.id`.
