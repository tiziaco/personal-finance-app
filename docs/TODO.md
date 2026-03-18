# TODO

## Performance

### N+1 Query Issues

#### [HIGH] `batch_update` — bulk fetch before update
**File:** `server/app/services/transaction/service.py:248`

Currently executes one `SELECT` per item to fetch each transaction before updating it (100 items = 100 queries).

**Fix:** Fetch all records in a single `WHERE id IN (...)` query, then perform a bulk `UPDATE`.

---

#### [HIGH] `batch_delete` — bulk fetch before soft-delete
**File:** `server/app/services/transaction/service.py:286`

Same pattern as `batch_update` — one `SELECT` per ID before soft-deleting.

**Fix:** Fetch all records in a single `WHERE id IN (...)` query, then perform a bulk soft-delete.

---

#### [MEDIUM] `anonymize_user` — fragile lazy-load mitigation
**File:** `server/app/api/v1/auth.py:98`

`conversations` is pre-loaded via `refresh()` before calling `anonymize_user()`, which loops over `user.conversations`. The mitigation works but is fragile — if `anonymize_user()` is called outside that context, it will trigger lazy loading and throw a `MissingGreenlet` error.

**Fix:** Move eager loading into `anonymize_user()` itself, or enforce it at the ORM relationship level.
