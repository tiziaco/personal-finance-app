# Database Operations

All patterns below belong in the module's `repository.py`, never in `service.py` — see `references/services.md`.

## `session.get()` vs `select()`

`session.get()` is the by-primary-key lookup. `UserRepository.get_by_id` and `ConversationRepository.get_by_id` use
it. It bypasses every filter: it returns soft-deleted rows, and it does not scope by
owner. That makes it correct exactly when the caller does both checks — and in this codebase that caller is the
module's ownership dependency:

```python
# app/modules/conversation/dependencies.py
conversation = await conversation_service.get_conversation(db_session, conversation_id)  # session.get underneath

if not conversation or conversation.deleted_at is not None or conversation.user_id != user.id:
    raise ConversationNotFoundError(f"Conversation {conversation_id} not found", conversation_id=conversation_id)
```

A "helpful" `deleted_at` filter inside `get_by_id` would turn the dependency's check into dead code and change
nothing visible — until a caller that needs the row after soft-deletion (the service tests do) breaks.

Anything filtered, scoped or listed is `select()` with explicit `WHERE` clauses:

```python
# app/modules/conversation/repository.py — list_active_for_user
statement = (
    select(Conversation)
    .where(Conversation.user_id == user_id, Conversation.deleted_at.is_(None))
    .order_by(Conversation.created_at)
)
result = await session.execute(statement)
return list(result.scalars().all())
```

Wrong is `session.get()` reached from a route or a service with no ownership check in front of it. Use
`scalar_one_or_none()` when the record may not exist; `scalar_one()` only when you are certain it does and want an
exception otherwise.

---

## User-owned tables

A table whose rows belong to one user carries `UserOwnedMixin` (`app/models/base.py`: `user_id`, FK `user.id`), and
every query on it filters `user_id` — a list, a count, a bulk update. The by-id lookup is the exception only when the
module's ownership dependency checks `user_id` right after it (above); anywhere else `session.get()` is not enough.
The route gets the user from `CurrentUser`, exported by `account`. `conversation` carries the mixin;
`tests/unit/models/test_owned_tables.py` fails on a new table that neither carries it nor is allowlisted with a
reason (`docs/architecture/server.md`, R7 and §9).

---

## Bulk operations (avoid N+1)

Never fetch or mutate records one at a time in a loop. Load the set in one query, mutate, flush once —
`soft_delete_active_for_user` in `references/services.md` is the real shape.

When the rows you must touch are ones a `select()` would not load, issue one `UPDATE`. The real case is
`ConversationRepository.blank_names_for_user`: erasure must blank the name on every conversation a user owns,
including ones already soft-deleted, which the active-rows select never returns.

```python
# app/modules/conversation/repository.py
await session.execute(update(Conversation).where(Conversation.user_id == user_id).values(name=""))
```

For a batch keyed by ids — invented, no route does this yet — fetch with `WHERE id IN (...)`, validate that every
id was found before mutating anything, then flush once:

```python
stmt = select(Payment).where(
    Payment.id.in_(ids),
    Payment.user_id == user_id,
    Payment.deleted_at.is_(None),
)
payments = (await session.execute(stmt)).scalars().all()

missing = set(ids) - {p.id for p in payments}
if missing:
    raise PaymentNotFoundError(f"Payments not found: {missing}", missing_ids=list(missing))

for payment in payments:
    payment.soft_delete()
    session.add(payment)
await session.flush()
```

For a large batch, one statement scoped by owner beats loading every row — after the same found-check, or when
partial success is acceptable:

```python
await session.execute(
    update(Payment)
    .where(Payment.id.in_(ids), Payment.user_id == user_id, Payment.deleted_at.is_(None))
    .values(deleted_at=datetime.now(timezone.utc))
    .execution_options(synchronize_session="fetch")  # keep instances already in the session in step
)
```

---

## Relationship loading (avoid MissingGreenlet)

Lazy loading is disabled in async SQLAlchemy — accessing an unloaded relationship raises `MissingGreenlet`. Always
load relationships explicitly, in the same query.

**A relationship never crosses a module** (`docs/architecture/server.md`, R3). `User` has no
`.conversations`: the foreign key is declared by table name, and the other side is asked of the other module's
service. Relationships exist only between tables one module owns, and no module has two yet. The examples below are
the `transactions` module that `docs/architecture/server.md` §2 sketches — a transaction and its splits, both
user-owned, so every query also filters `user_id`.

**`selectinload`** — one-to-many / many-to-many. Issues a second `SELECT ... WHERE id IN (...)`.

```python
from sqlalchemy.orm import selectinload

stmt = (
    select(Transaction)
    .where(Transaction.id == transaction_id, Transaction.user_id == user_id)
    .options(selectinload(Transaction.splits))
)
result = await session.execute(stmt)
transaction = result.scalar_one_or_none()
# transaction.splits is now safe to access
```

**`joinedload`** — many-to-one / one-to-one. A single `JOIN`. Avoid for collections — it duplicates rows.

```python
from sqlalchemy.orm import joinedload

stmt = (
    select(TransactionSplit)
    .where(TransactionSplit.id == split_id, TransactionSplit.user_id == user_id)
    .options(joinedload(TransactionSplit.transaction))
)
```

**Rule**: if a repository method accesses a relationship, it eagerly loads it in the same query. Don't rely on the
caller to pre-load it — that's fragile and breaks when the method is called from a different context.

---

## Database error handling

`get_db_session` (`app/database/dependencies.py`) translates SQLAlchemy errors — don't re-catch them in repository
or service code:

- `IntegrityError` → `DatabaseConflictError` (409)
- `OperationalError` → `DatabaseConnectionError` (503)
- `DBAPIError` → `DatabaseError` (500)

The one valid exception is resolving a **race condition** on insert: two requests JIT-provisioning the same user at
once. `UserRepository.create_or_get` (`app/modules/account/repository.py`) is the real one — it catches
`IntegrityError`, rolls back, re-queries by the unique key, and only if that also finds nothing raises
`UserAlreadyExistsError`, because then the collision was something else. Copy its shape rather than sketching a new
one.

---

## Count queries

When you need both a page of results and a total count, run the count against a subquery of the filtered statement
— don't run two separate queries with duplicated filter logic. Invented; no route paginates yet.

```python
ORDERING_COLUMNS = {"created_at": Payment.created_at, "amount": Payment.amount}

stmt = select(Payment).where(Payment.user_id == user_id, Payment.deleted_at.is_(None))
# apply filters here...
if search:
    escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    stmt = stmt.where(Payment.reference.ilike(f"%{escaped}%", escape="\\"))

field = (ordering or "-created_at").lstrip("-")
column = ORDERING_COLUMNS[field]
primary = column.desc() if (ordering or "-created_at").startswith("-") else column.asc()
stmt = stmt.order_by(primary, Payment.id).offset(offset).limit(limit)
result = await session.execute(stmt)
items = list(result.scalars().all())

count_stmt = select(func.count()).select_from(
    stmt.order_by(None).limit(None).offset(None).subquery()
)
total = (await session.execute(count_stmt)).scalar_one()
```

- **Ordering** maps the route's `Literal` field names to columns in one dict; a name missing from it is a `KeyError`,
  so the route's allow-list and the map cannot drift silently. A default applies when `ordering` is unset.
- **Always end with a unique tiebreaker** (`Payment.id`). Offset pages over a non-unique sort key are unstable: rows
  with equal values can swap between queries and appear on two pages or none.
- **Search** is `ilike` on named columns, with `%`, `_` and `\` escaped — unescaped, a user's `%` matches every row.
