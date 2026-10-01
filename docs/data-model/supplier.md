# Supplier — Data Model

**Status:** shipped — for the company row and the contact link; the rest of the feature is
not built · **Owner:** Tiziano · **Last updated:** 29 Sep 2026
**Describes:** [`../product/features/suppliers.md`](../product/features/suppliers.md).
**Scope:** the `supplier` table — an external company, and the user who acts for it. The
template's example domain: a fork replaces it.
**Source of truth:** the code — `server/app/modules/supplier/models.py` and the Alembic
revision `9bcca25cfef3`. The sketch below was last brought in line with them on
29 Sep 2026; where the two disagree, the code wins. Conventions: [`README.md`](./README.md).

---

## 1. Approach

**The role says what kind of user someone is; this row says which company they act for.**
A user with the `supplier` role is linked to one company through `contact_id`.

**The link is made from the invitation.** When the contact is first provisioned, the
`USER_SYNCED` subscriber (`server/app/modules/supplier/handlers.py`) reads the invitation's
metadata and sets `contact_id`. It is cleared on erasure, or when the contact leaves the
organization. `SupplierID` ([`../architecture/authorization.md`](../architecture/authorization.md) §2) resolves it
on every supplier request, and refuses a user with no link (`SUPPLIER_NOT_LINKED`).

## 2. Schema sketch

```sql
CREATE TABLE supplier (
    id          UUID        PRIMARY KEY DEFAULT uuidv7(),
    contact_id  UUID        REFERENCES "user" (id),         -- the portal contact; NULL until one exists
    name        VARCHAR     NOT NULL,
    code        VARCHAR     NOT NULL,                       -- unique
    vat_number  VARCHAR     NOT NULL,                       -- unique
    deleted_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL
);
```

## 3. Indexes

| Index | Unique | Serves |
|---|---|---|
| `ix_supplier_code` | yes | one company per code |
| `ix_supplier_vat_number` | yes | one company per VAT number |
| `ix_supplier_contact_id` | no | `SupplierID`: which company this user acts for |
| `ix_supplier_deleted_at` | no | the `deleted_at IS NULL` filter |
| `ix_supplier_created_at` | no | ordering by recency |

## 4. Decisions

- **D1 — soft delete.** A supplier is a business record, not personal data; its contact's
  personal data lives on `"user"` and is anonymised there.
- **D2 — no `org_id` yet.** Its entry in the tenancy allowlist (`test_tenant_tables.py`):
  no route writes the table yet. It adopts `TenantMixin` with the first write route, which
  needs a backfill of `org_id` on existing rows.

## 5. Deferred

- **`TenantMixin`** — with the first write route; [`../TODO.md`](../TODO.md),
  **Tenancy**.
- **Documents, orders and projects** — everything in the feature doc marked not built.
