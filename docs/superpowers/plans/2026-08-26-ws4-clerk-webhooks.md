# WS4 Clerk Webhooks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Clerk the push source of truth for user state — profile edits, org membership changes, and deletions performed in the Clerk dashboard reach the database without the user logging in.

**Architecture:** A FastAPI dependency owns svix signature verification and returns a validated `ClerkEvent`; a `ClerkWebhookService` maps event type to handler; handlers call the existing repositories. No dedup table — handlers are idempotent, ordered by a monotonic `last_synced_at` guard running on Clerk's clock.

**Tech Stack:** FastAPI, SQLModel, pydantic-settings, `svix` (new), pytest, Docker Compose, ngrok.

**Spec:** `docs/superpowers/specs/2026-08-26-ws4-clerk-webhooks-design.md`

## Global Constraints

- All commands run from `server/` unless stated otherwise.
- `async def` everywhere; no blocking I/O. Type hints on every signature.
- All imports at the top of the file — never inside functions.
- Services raise domain exceptions extending `ServiceError`. **Never** raise `HTTPException` from a service. **Never** add try/except in a route handler.
- structlog events are `lowercase_with_underscores`; variables passed as kwargs, never f-string interpolated. Use `logger.exception()` where a traceback matters.
- Unpack `SecretStr` with `.get_secret_value()`.
- Tests mirror `app/` structure. Unit tests carry `pytestmark = pytest.mark.unit`, integration tests `pytest.mark.integration`.
- Run tests as `APP_ENV=test uv run pytest ...`.
- Membership event type strings: the Clerk dashboard catalog uses `organizationMembership.*` (camelCase); the application-log docs use `organization_membership.*`. Register **both** — a wrong key fails silently.
- Handlers invalidate caches; they never call `user_cache.set_org_role()`. Populating before commit can serve a value for a transaction that later rolls back.
- Commit after every task. Tasks 1–3 are pure refactors and must leave behaviour unchanged.

---

### Task 1: Extract `erase_user()` from the delete route

Pure refactor, no webhook code. The GDPR cascade currently lives inline in a route handler; the webhook will need the identical sequence, and duplicating it would guarantee drift.

**Files:**
- Modify: `app/services/user/service.py` (add method)
- Modify: `app/api/v1/auth.py:80-119` (call it)
- Test: `tests/unit/services/test_user_erasure.py` (create)

**Interfaces:**
- Consumes: `conversation_service.soft_delete_all_user_conversations(session, user_id) -> list[str]`, `delete_user_memory(user_id)`, `UserService.unlink_supplier_contact(user_id, session) -> Optional[str]`, `User.anonymize_user()`, `user_cache.invalidate_user(clerk_id=..., user_id=...)`
- Produces: `UserService.erase_user(user: User, session: AsyncSession, agent: BaseAgent) -> None`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/services/test_user_erasure.py`:

```python
"""Tests for UserService.erase_user — the shared GDPR cascade.

Used by both DELETE /api/v1/auth/me and the user.deleted webhook, so the
ordering of its steps is contractual: checkpoints and memories must be
cleared before the row is anonymised, because anonymisation destroys the
identifiers those systems are keyed by.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.user import User
from app.services.user.service import UserService

pytestmark = pytest.mark.unit


def make_user() -> User:
    user = User(
        id="11111111-2222-3333-4444-555555555555",
        clerk_id="user_abc",
        email="person@example.com",
        org_id="org_1",
    )
    user.conversations = []
    return user


@pytest.fixture
def session() -> AsyncMock:
    s = AsyncMock()
    s.add = MagicMock()
    return s


async def test_erase_user_runs_full_cascade(session):
    user = make_user()
    agent = AsyncMock()

    with (
        patch(
            "app.services.user.service.conversation_service.soft_delete_all_user_conversations",
            new=AsyncMock(return_value=["conv_1", "conv_2"]),
        ),
        patch("app.services.user.service.delete_user_memory", new=AsyncMock()) as mem,
        patch.object(UserService, "unlink_supplier_contact", new=AsyncMock(return_value="sup_1")),
        patch("app.services.user.service.user_cache.invalidate_user", new=AsyncMock()) as invalidate,
    ):
        await UserService().erase_user(user, session, agent)

    assert agent.clear_chat_history.await_count == 2
    mem.assert_awaited_once_with("11111111-2222-3333-4444-555555555555")
    invalidate.assert_awaited_once_with(
        clerk_id="user_abc", user_id="11111111-2222-3333-4444-555555555555"
    )
    session.commit.assert_awaited_once()


async def test_erase_user_anonymizes_the_row(session):
    user = make_user()

    with (
        patch(
            "app.services.user.service.conversation_service.soft_delete_all_user_conversations",
            new=AsyncMock(return_value=[]),
        ),
        patch("app.services.user.service.delete_user_memory", new=AsyncMock()),
        patch.object(UserService, "unlink_supplier_contact", new=AsyncMock(return_value=None)),
        patch("app.services.user.service.user_cache.invalidate_user", new=AsyncMock()),
    ):
        await UserService().erase_user(user, session, AsyncMock())

    assert user.clerk_id != "user_abc"
    assert user.email.endswith("@anonymized.local")
    assert user.org_id is None
    assert user.anonymized_at is not None


async def test_erase_user_invalidates_with_pre_anonymisation_clerk_id(session):
    """The cache is keyed by the original clerk_id, which anonymize_user destroys."""
    user = make_user()

    with (
        patch(
            "app.services.user.service.conversation_service.soft_delete_all_user_conversations",
            new=AsyncMock(return_value=[]),
        ),
        patch("app.services.user.service.delete_user_memory", new=AsyncMock()),
        patch.object(UserService, "unlink_supplier_contact", new=AsyncMock(return_value=None)),
        patch("app.services.user.service.user_cache.invalidate_user", new=AsyncMock()) as invalidate,
    ):
        await UserService().erase_user(user, session, AsyncMock())

    assert invalidate.await_args.kwargs["clerk_id"] == "user_abc"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `APP_ENV=test uv run pytest tests/unit/services/test_user_erasure.py -v`
Expected: FAIL with `AttributeError: 'UserService' object has no attribute 'erase_user'`

- [ ] **Step 3: Add the imports to `app/services/user/service.py`**

Add to the top-of-file import block (all imports at top, per the project convention):

```python
from app.agents.base.agent import BaseAgent
from app.agents.shared.memory.factory import delete_user_memory
from app.services.conversation import conversation_service
```

No circular import: `conversation_service` imports only models and its own exceptions, and `app.agents.base.agent` imports `app.services.llm`, never `app.services.user`.

- [ ] **Step 4: Add `erase_user()` to `UserService`**

```python
    async def erase_user(
        self,
        user: User,
        session: AsyncSession,
        agent: BaseAgent,
    ) -> None:
        """Run the GDPR erasure cascade for one user.

        Shared by DELETE /api/v1/auth/me and the user.deleted webhook. The
        caller is responsible for deleting the user from Clerk — the webhook
        path must not, because a Clerk-side deletion is what produced the
        event.

        Step order is contractual. Checkpoints and memories are keyed by
        identifiers that anonymize_user() destroys, so they must be cleared
        first. Cache invalidation happens after the commit, using the
        clerk_id captured before anonymisation rewrote it.

        Idempotent: on a second run the conversation list is empty, mem0
        deletion is a no-op, and the row is already anonymised.

        Args:
            user: The user to erase. Must be attached to `session`.
            session: Database session. Committed by this method.
            agent: Agent whose checkpoint store holds the conversation history.
        """
        original_clerk_id = user.clerk_id

        conversation_ids = await conversation_service.soft_delete_all_user_conversations(
            session, user.id
        )
        for conv_id in conversation_ids:
            await agent.clear_chat_history(conv_id)

        await delete_user_memory(user.id)
        await self.unlink_supplier_contact(user.id, session)

        # Eagerly load conversations so anonymize_user() can iterate them
        # without a synchronous lazy load on an async session (MissingGreenlet).
        await session.refresh(user, attribute_names=["conversations"])
        user.anonymize_user()
        session.add(user)
        await session.commit()

        await user_cache.invalidate_user(clerk_id=original_clerk_id, user_id=user.id)

        logger.info(
            "user_erased",
            user_id=user.id,
            conversation_count=len(conversation_ids),
        )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `APP_ENV=test uv run pytest tests/unit/services/test_user_erasure.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Replace the inline cascade in the route**

In `app/api/v1/auth.py`, replace the body of `delete_me` after the docstring with:

```python
    original_clerk_id = user.clerk_id  # captured before erase_user anonymises it

    # Delete from Clerk first so the JWT cannot re-provision the account.
    # The webhook path skips this step — there, Clerk's deletion is the trigger.
    await user_service.delete_user_from_clerk(original_clerk_id)

    await user_service.erase_user(user, db_session, agent)
```

Then remove the now-unused imports from `app/api/v1/auth.py`: `delete_user_memory`, `conversation_service`, and `user_cache` if nothing else in the file uses them. Leave `logger` — `erase_user` logs `user_erased`, so the route's own `user_deleted_gdpr_compliant` line goes away with the inline code.

- [ ] **Step 7: Verify nothing regressed**

Run: `APP_ENV=test uv run pytest tests/ -v -k "auth or user or erase"`
Expected: PASS. Then `make lint`.

- [ ] **Step 8: Commit**

```bash
git add app/services/user/service.py app/api/v1/auth.py tests/unit/services/test_user_erasure.py
git commit -m "refactor(user): extract erase_user() from the delete route

The GDPR cascade lived inline in delete_me. The user.deleted webhook
needs the identical sequence, and the step order is contractual —
checkpoints and mem0 memories are keyed by identifiers anonymize_user()
destroys. Duplicating that in a second call site would guarantee drift.

erase_user() deliberately excludes the Clerk deletion: on the webhook
path a Clerk-side deletion is what produced the event."
```

---

### Task 2: Extract `link_supplier_from_metadata()`

Pure refactor. The supplier-linking block is inline in `resolve_user`; three call sites will need it.

**Files:**
- Modify: `app/services/user/service.py:104-155` (extract), plus a module-level helper
- Test: `tests/unit/services/test_supplier_linking.py` (create)

**Interfaces:**
- Consumes: `supplier_repository.get_by_id(session, supplier_id)`, `supplier_repository.set_contact_id(session, supplier, contact_id)`, `user_cache.invalidate_user(user_id=...)`
- Produces:
  - `UserService.link_supplier_from_metadata(user: User, metadata: dict, session: AsyncSession) -> Optional[str]`
  - `merge_clerk_metadata(clerk_user) -> dict` (module-level in `app/services/user/service.py`)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/services/test_supplier_linking.py`:

```python
"""Tests for supplier linking extracted from JIT provisioning.

The linker is called from three places (JIT, user.created, and
organization_membership.created), so it must be idempotent: linking an
already-linked supplier to the same user changes nothing.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.models.supplier import Supplier
from app.models.user import User
from app.services.user.service import UserService, merge_clerk_metadata

pytestmark = pytest.mark.unit


def make_user(user_id: str = "user-uuid-1") -> User:
    return User(id=user_id, clerk_id="user_abc", email="a@b.com", org_id="org_1")


def make_supplier(contact_id=None) -> Supplier:
    return Supplier(
        id="sup_1", name="Acme", code="ACME", vat_number="IT123", contact_id=contact_id
    )


async def test_links_unlinked_supplier():
    user, supplier = make_user(), make_supplier(contact_id=None)
    session = AsyncMock()

    with (
        patch(
            "app.services.user.service.supplier_repository.get_by_id",
            new=AsyncMock(return_value=supplier),
        ),
        patch(
            "app.services.user.service.supplier_repository.set_contact_id",
            new=AsyncMock(side_effect=lambda s, sup, cid: setattr(sup, "contact_id", cid) or sup),
        ),
        patch("app.services.user.service.user_cache.invalidate_user", new=AsyncMock()),
    ):
        result = await UserService().link_supplier_from_metadata(
            user, {"supplier_id": "sup_1"}, session
        )

    assert result == "sup_1"
    assert supplier.contact_id == "user-uuid-1"


async def test_does_not_steal_an_already_linked_supplier():
    user, supplier = make_user(), make_supplier(contact_id="someone-else")
    session = AsyncMock()

    with patch(
        "app.services.user.service.supplier_repository.get_by_id",
        new=AsyncMock(return_value=supplier),
    ):
        result = await UserService().link_supplier_from_metadata(
            user, {"supplier_id": "sup_1"}, session
        )

    assert result is None
    assert supplier.contact_id == "someone-else"


async def test_replace_flag_relinks_and_invalidates_the_displaced_contact():
    user, supplier = make_user(), make_supplier(contact_id="displaced-user")
    session = AsyncMock()

    with (
        patch(
            "app.services.user.service.supplier_repository.get_by_id",
            new=AsyncMock(return_value=supplier),
        ),
        patch(
            "app.services.user.service.supplier_repository.set_contact_id",
            new=AsyncMock(side_effect=lambda s, sup, cid: setattr(sup, "contact_id", cid) or sup),
        ),
        patch("app.services.user.service.user_cache.invalidate_user", new=AsyncMock()) as inval,
    ):
        result = await UserService().link_supplier_from_metadata(
            user, {"supplier_id": "sup_1", "replace": True}, session
        )

    assert result == "sup_1"
    invalidated = {c.kwargs.get("user_id") for c in inval.await_args_list}
    assert invalidated == {"displaced-user", "user-uuid-1"}


async def test_relinking_same_user_is_idempotent():
    """A retried webhook must not thrash the cache for an unchanged link."""
    user, supplier = make_user(), make_supplier(contact_id="user-uuid-1")
    session = AsyncMock()

    with (
        patch(
            "app.services.user.service.supplier_repository.get_by_id",
            new=AsyncMock(return_value=supplier),
        ),
        patch(
            "app.services.user.service.supplier_repository.set_contact_id",
            new=AsyncMock(return_value=supplier),
        ),
        patch("app.services.user.service.user_cache.invalidate_user", new=AsyncMock()),
    ):
        result = await UserService().link_supplier_from_metadata(
            user, {"supplier_id": "sup_1", "replace": True}, session
        )

    assert result == "sup_1"
    assert supplier.contact_id == "user-uuid-1"


async def test_no_metadata_is_a_noop():
    session = AsyncMock()
    assert await UserService().link_supplier_from_metadata(make_user(), {}, session) is None


class FakeMembership:
    def __init__(self, metadata):
        self.public_metadata = metadata


class FakeClerkUser:
    def __init__(self, top, memberships):
        self.public_metadata = top
        self.organization_memberships = memberships


def test_merge_prefers_top_level_over_membership_metadata():
    clerk_user = FakeClerkUser(
        {"supplier_id": "top"}, [FakeMembership({"supplier_id": "membership"})]
    )
    assert merge_clerk_metadata(clerk_user)["supplier_id"] == "top"


def test_merge_falls_back_to_membership_metadata():
    clerk_user = FakeClerkUser({}, [FakeMembership({"supplier_id": "membership", "replace": True})])
    merged = merge_clerk_metadata(clerk_user)
    assert merged["supplier_id"] == "membership"
    assert merged["replace"] is True


def test_merge_tolerates_missing_attributes():
    class Bare:
        pass

    assert merge_clerk_metadata(Bare()) == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `APP_ENV=test uv run pytest tests/unit/services/test_supplier_linking.py -v`
Expected: FAIL with `ImportError: cannot import name 'merge_clerk_metadata'`

- [ ] **Step 3: Add the module-level metadata merger**

Add to `app/services/user/service.py`, above the `UserService` class:

```python
def merge_clerk_metadata(clerk_user: Any) -> dict:
    """Flatten a Clerk user's public metadata, top level winning over memberships.

    Invitation metadata may be stamped on the user or on the organisation
    membership, depending on how the invite was issued. Callers should not
    have to know which, so this collapses both into one dict with top-level
    values taking precedence.

    Args:
        clerk_user: A Clerk SDK user object.

    Returns:
        A merged metadata dict; empty if the object carries none.
    """
    merged: dict = {}

    top_level = getattr(clerk_user, "public_metadata", None) or {}
    if isinstance(top_level, dict):
        merged.update(top_level)

    for membership in getattr(clerk_user, "organization_memberships", None) or []:
        membership_md = getattr(membership, "public_metadata", None) or {}
        if not isinstance(membership_md, dict):
            continue
        for key in ("supplier_id", "replace"):
            if not merged.get(key) and membership_md.get(key):
                merged[key] = membership_md[key]

    return merged
```

Add `Any` to the existing `typing` import.

- [ ] **Step 4: Add `link_supplier_from_metadata()` to `UserService`**

```python
    async def link_supplier_from_metadata(
        self,
        user: User,
        metadata: dict,
        session: AsyncSession,
    ) -> Optional[str]:
        """Link a supplier to this user based on invitation metadata.

        Called from JIT provisioning and from two webhook handlers, so it must
        be safely repeatable. Only an unlinked supplier is claimed, unless the
        metadata carries a truthy `replace` flag — so a retried event, or a
        second invite for an already-linked supplier, changes nothing.

        Cache invalidation is safe before the caller's commit: dropping an
        entry can only cost a DB read, never serve a wrong value.

        Args:
            user: The user to link.
            metadata: Merged public metadata; read for `supplier_id` and `replace`.
            session: DB session. Flushed, not committed.

        Returns:
            The linked Supplier.id, or None if nothing was linked.
        """
        supplier_id = metadata.get("supplier_id")
        if not supplier_id:
            return None

        replace_flag = bool(metadata.get("replace"))

        supplier = await supplier_repository.get_by_id(session, supplier_id)
        if supplier is None:
            logger.warning("supplier_link_target_missing", supplier_id=supplier_id, user_id=user.id)
            return None
        if supplier.contact_id is not None and not replace_flag:
            return None

        # Capture BEFORE overwriting. With replace_flag this is a RE-LINK: the
        # displaced contact holds a cached user_id -> supplier_id entry that is
        # now wrong, and once the old id is gone that entry is unreachable.
        previous_contact_id = supplier.contact_id
        supplier = await supplier_repository.set_contact_id(session, supplier, user.id)

        if previous_contact_id and previous_contact_id != user.id:
            await user_cache.invalidate_user(user_id=previous_contact_id)
        await user_cache.invalidate_user(user_id=user.id)

        logger.info(
            "supplier_linked",
            supplier_id=supplier.id,
            user_id=user.id,
            previous_contact_id=previous_contact_id,
            replace=replace_flag,
        )
        return supplier.id
```

- [ ] **Step 5: Replace the inline block in `resolve_user`**

Delete the whole supplier-linking section of `resolve_user` (from the `# Supplier-linking on JIT creation:` comment through the `logger.info("supplier_linked_on_jit", ...)` call) and replace it with:

```python
        await self.link_supplier_from_metadata(user, merge_clerk_metadata(clerk_user), session)
```

- [ ] **Step 6: Run tests**

Run: `APP_ENV=test uv run pytest tests/unit/services/test_supplier_linking.py tests/ -k "supplier or resolve or jit" -v`
Expected: PASS. Any existing test asserting the `supplier_linked_on_jit` event name must be updated to `supplier_linked` — the event is no longer JIT-specific.

Then `make lint`.

- [ ] **Step 7: Commit**

```bash
git add app/services/user/service.py tests/unit/services/test_supplier_linking.py
git commit -m "refactor(user): extract link_supplier_from_metadata()

resolve_user carried ~50 lines of inline supplier linking that two
webhook handlers now need. Extracted with the metadata merge split into
its own function, since 'top level wins over membership' is a rule about
Clerk's invite shapes, not about linking.

Renames the log event supplier_linked_on_jit -> supplier_linked; it is
no longer JIT-specific."
```

---

### Task 3: Put `last_synced_at` on Clerk's clock

Independent fix and the precondition for the ordering guard. `last_synced_at` currently receives our wall clock, which makes any comparison against a Clerk timestamp hostage to host clock skew.

**Files:**
- Create: `app/utils/clerk.py`
- Modify: `app/services/user/repository.py` (`create`, `create_or_get`, `update_from_clerk`)
- Modify: `app/services/user/service.py` (`resolve_user` passes Clerk's timestamp)
- Test: `tests/unit/utils/test_clerk_timestamps.py` (create), `tests/unit/services/test_user_repository_sync.py` (create)

**Interfaces:**
- Produces:
  - `clerk_timestamp_to_datetime(value: Optional[int]) -> Optional[datetime]` in `app/utils/clerk.py`
  - `UserRepository.create(..., last_synced_at: Optional[datetime] = None)`
  - `UserRepository.create_or_get(..., org_id: Optional[str], last_synced_at: Optional[datetime] = None)`
  - `UserRepository.update_from_clerk(..., last_synced_at: Optional[datetime] = None)`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/utils/test_clerk_timestamps.py`:

```python
"""Clerk sends millisecond epoch integers; the DB column is aware UTC."""

from datetime import UTC, datetime

import pytest

from app.utils.clerk import clerk_timestamp_to_datetime

pytestmark = pytest.mark.unit


def test_converts_millisecond_epoch_to_aware_utc():
    result = clerk_timestamp_to_datetime(1654012591835)
    assert result == datetime(2022, 5, 31, 15, 56, 31, 835000, tzinfo=UTC)
    assert result.tzinfo is not None


def test_none_passes_through():
    assert clerk_timestamp_to_datetime(None) is None


def test_non_integer_input_returns_none():
    """Defensive: a payload field of an unexpected type must not raise."""
    assert clerk_timestamp_to_datetime("1654012591835") is None
```

Create `tests/unit/services/test_user_repository_sync.py`:

```python
"""last_synced_at must carry Clerk's clock, not ours.

The ordering guard compares an event's updated_at against this column. If
one side is our wall clock and the other is Clerk's, host clock skew
silently corrupts every comparison — and skew in one direction drops
legitimate updates indefinitely.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.user import User
from app.services.user.repository import UserRepository

pytestmark = pytest.mark.unit

CLERK_TS = datetime(2022, 5, 31, 15, 56, 31, tzinfo=UTC)


@pytest.fixture
def session() -> AsyncMock:
    s = AsyncMock()
    s.add = MagicMock()
    return s


async def test_create_uses_supplied_clerk_timestamp(session):
    user = await UserRepository.create(
        session=session,
        clerk_id="user_abc",
        email="a@b.com",
        org_id="org_1",
        last_synced_at=CLERK_TS,
    )
    assert user.last_synced_at == CLERK_TS


async def test_create_falls_back_to_now_when_absent(session):
    before = datetime.now(UTC)
    user = await UserRepository.create(
        session=session, clerk_id="user_abc", email="a@b.com", org_id="org_1"
    )
    assert user.last_synced_at >= before


async def test_create_accepts_a_null_org_id(session):
    """user.created carries no organisation — Clerk models membership separately."""
    user = await UserRepository.create(
        session=session, clerk_id="user_abc", email="a@b.com", org_id=None
    )
    assert user.org_id is None


async def test_update_from_clerk_uses_supplied_timestamp(session):
    user = User(clerk_id="user_abc", email="a@b.com", org_id="org_1")
    user.last_synced_at = CLERK_TS - timedelta(days=1)

    await UserRepository.update_from_clerk(
        session=session, user=user, first_name="New", last_synced_at=CLERK_TS
    )
    assert user.last_synced_at == CLERK_TS


async def test_update_from_clerk_falls_back_to_now(session):
    user = User(clerk_id="user_abc", email="a@b.com", org_id="org_1")
    before = datetime.now(UTC)

    await UserRepository.update_from_clerk(session=session, user=user, first_name="New")
    assert user.last_synced_at >= before
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `APP_ENV=test uv run pytest tests/unit/utils/test_clerk_timestamps.py tests/unit/services/test_user_repository_sync.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.utils.clerk'` and `TypeError: create() got an unexpected keyword argument 'last_synced_at'`

- [ ] **Step 3: Create `app/utils/clerk.py`**

```python
"""Helpers for Clerk payload values.

Clerk expresses every timestamp as a millisecond epoch integer, in both the
Backend API objects and the webhook payloads. The database stores aware UTC
datetimes, so one conversion function serves every caller.
"""

from datetime import UTC, datetime
from typing import Optional


def clerk_timestamp_to_datetime(value: Optional[int]) -> Optional[datetime]:
    """Convert a Clerk millisecond epoch timestamp to an aware UTC datetime.

    Deliberately tolerant: webhook payloads are attacker-influenced up to the
    signature boundary, and a field of an unexpected type must degrade to
    "unknown" rather than raise inside a handler.

    Args:
        value: Milliseconds since the Unix epoch, or None.

    Returns:
        An aware UTC datetime, or None if the value is absent or not an int.
    """
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    return datetime.fromtimestamp(value / 1000, tz=UTC)
```

- [ ] **Step 4: Thread `last_synced_at` through the repository**

In `app/services/user/repository.py`:

`create()` — change the `org_id` annotation to `Optional[str]`, add the parameter, and use it:

```python
    @staticmethod
    async def create(
        session: AsyncSession,
        clerk_id: str,
        email: str,
        org_id: Optional[str],
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        avatar_url: Optional[str] = None,
        email_verified: bool = False,
        last_synced_at: Optional[datetime] = None,
    ) -> User:
```

and in the body:

```python
        user = User(
            clerk_id=clerk_id,
            email=email,
            org_id=org_id,
            first_name=first_name,
            last_name=last_name,
            avatar_url=avatar_url,
            email_verified=email_verified,
            # Clerk's clock when we have it. Passing None explicitly would
            # bypass the field default, so fall back here.
            last_synced_at=last_synced_at or datetime.now(UTC),
        )
```

`create_or_get()` — same two signature changes (`org_id: Optional[str]`, add `last_synced_at: Optional[datetime] = None`) and forward `last_synced_at=last_synced_at` in its call to `UserRepository.create`.

`update_from_clerk()` — add `last_synced_at: Optional[datetime] = None` and change the assignment:

```python
        user.updated_at = now
        user.last_synced_at = last_synced_at or now
```

- [ ] **Step 5: Make JIT write Clerk's timestamp**

In `app/services/user/service.py`, add the import:

```python
from app.utils.clerk import clerk_timestamp_to_datetime
```

and in `resolve_user`, add the argument to the `create_or_get` call:

```python
            last_synced_at=clerk_timestamp_to_datetime(getattr(clerk_user, "updated_at", None)),
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `APP_ENV=test uv run pytest tests/unit/utils/test_clerk_timestamps.py tests/unit/services/test_user_repository_sync.py -v`
Expected: PASS (8 tests)

Then the full suite: `APP_ENV=test uv run pytest tests/ -v` and `make lint`.

- [ ] **Step 7: Commit**

```bash
git add app/utils/clerk.py app/services/user/repository.py app/services/user/service.py tests/unit/utils/test_clerk_timestamps.py tests/unit/services/test_user_repository_sync.py
git commit -m "fix(user): record last_synced_at from Clerk's clock

The column existed but only ever received datetime.now() from the field
default, and was never written again after creation. The webhook ordering
guard compares an event's updated_at against it, so with our wall clock on
one side and Clerk's on the other, host clock skew would silently corrupt
every comparison — and skew in one direction drops valid updates forever.

Also relaxes org_id to Optional on create/create_or_get: Clerk's
user.created payload carries no organisation, because membership is a
separate resource with its own events."
```

---

### Task 4: Webhook signature verification

The security boundary. Everything downstream trusts this.

**Files:**
- Modify: `pyproject.toml` (add `svix`)
- Modify: `app/core/config.py:110-124` (`AuthSettings`)
- Modify: `scripts/docker-entrypoint.sh:57` (`REQUIRED_ENV_VARS` default)
- Modify: `.env.example`, `.env.development`, `.env.test`
- Create: `app/schemas/webhook.py`
- Create: `app/services/clerk/webhooks/__init__.py`, `app/services/clerk/webhooks/exceptions.py`
- Create: `app/api/dependencies/webhook.py`
- Test: `tests/unit/api/test_webhook_dependency.py`

**Interfaces:**
- Produces:
  - `ClerkEvent` (fields: `type: str`, `data: dict`, `timestamp: Optional[int]`, `instance_id: Optional[str]`)
  - `verify_clerk_webhook(request: Request) -> ClerkEvent`
  - `MAX_WEBHOOK_BODY_BYTES: int`
  - `InvalidWebhookSignatureError` (401), `WebhookPayloadTooLargeError` (413)

- [ ] **Step 1: Add the dependency**

```bash
uv add svix
```

- [ ] **Step 2: Add the setting and the env vars**

In `app/core/config.py`, add to `AuthSettings`:

```python
    # Per-endpoint signing secret from the Clerk dashboard (whsec_...).
    # Enforced at container start by REQUIRED_ENV_VARS in
    # scripts/docker-entrypoint.sh, NOT by making this field required:
    # alembic/env.py imports this module, so a required field would force the
    # one-shot migrate service to carry a secret it never uses and would
    # defeat its deliberate REQUIRED_ENV_VARS= opt-out.
    WEBHOOK_SIGNING_SECRET: SecretStr = Field(default=SecretStr(""))
```

`server/.env.example` already carries the placeholder line as of commit `fa60bd1`:

```env
CLERK_WEBHOOK_SIGNING_SECRET="your-webhook-signing-secret"
```

Add the same key to `.env.development` with the real value from the Clerk dashboard (see `docs/setup/clerk-webhooks.md`).

Add to `.env.test` — a syntactically valid but fake secret, since svix base64-decodes it:

```env
CLERK_WEBHOOK_SIGNING_SECRET=whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw
```

In `scripts/docker-entrypoint.sh`, change both occurrences of the default on line 57-59 from `OPENAI_API_KEY` to `OPENAI_API_KEY,CLERK_WEBHOOK_SIGNING_SECRET`:

```bash
if [[ -n "${REQUIRED_ENV_VARS-OPENAI_API_KEY,CLERK_WEBHOOK_SIGNING_SECRET}" ]]; then
    IFS=',' read -r -a required_vars <<<"${REQUIRED_ENV_VARS-OPENAI_API_KEY,CLERK_WEBHOOK_SIGNING_SECRET}"
fi
```

Leave the `migrate` service's `REQUIRED_ENV_VARS=` override in both compose files exactly as it is — that opt-out is what keeps a webhook secret from being a migration prerequisite.

- [ ] **Step 3: Write the failing tests**

Create `tests/unit/api/test_webhook_dependency.py`:

```python
"""Adversarial tests for Clerk webhook signature verification.

This dependency is the entire security boundary for the webhook endpoint —
no JWT, no session, nothing else authenticates the caller. Every test here
is an attack the endpoint must reject.
"""

import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import Request
from svix.webhooks import Webhook

from app.api.dependencies.webhook import MAX_WEBHOOK_BODY_BYTES, verify_clerk_webhook
from app.services.clerk.webhooks.exceptions import (
    InvalidWebhookSignatureError,
    WebhookPayloadTooLargeError,
)

pytestmark = pytest.mark.unit

TEST_SECRET = "whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw"
OTHER_SECRET = "whsec_TG9yZW1JcHN1bURvbG9yU2l0QW1ldENvbnM="

PAYLOAD = {
    "type": "user.created",
    "object": "event",
    "timestamp": 1654012591835,
    "instance_id": "ins_123",
    "data": {"id": "user_abc", "updated_at": 1654012591835},
}


def signed_headers(body: str, secret: str = TEST_SECRET, msg_id: str = "msg_1", ts=None) -> dict:
    ts = ts or datetime.now(tz=UTC)
    return {
        "svix-id": msg_id,
        "svix-timestamp": str(int(ts.timestamp())),
        "svix-signature": Webhook(secret).sign(msg_id, ts, body),
    }


def make_request(body: bytes, headers: dict) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/webhooks/clerk",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    from app.core.config import settings
    from pydantic import SecretStr

    monkeypatch.setattr(settings.auth, "WEBHOOK_SIGNING_SECRET", SecretStr(TEST_SECRET))


async def test_valid_signature_returns_parsed_event():
    body = json.dumps(PAYLOAD)
    event = await verify_clerk_webhook(make_request(body.encode(), signed_headers(body)))

    assert event.type == "user.created"
    assert event.data["id"] == "user_abc"


async def test_tampered_body_is_rejected():
    body = json.dumps(PAYLOAD)
    headers = signed_headers(body)
    tampered = json.dumps({**PAYLOAD, "data": {"id": "user_attacker"}})

    with pytest.raises(InvalidWebhookSignatureError):
        await verify_clerk_webhook(make_request(tampered.encode(), headers))


async def test_reserialised_body_is_rejected():
    """Proves we verify raw bytes. Re-serialising reorders keys and breaks the HMAC."""
    body = json.dumps(PAYLOAD)
    headers = signed_headers(body)
    reserialised = json.dumps(json.loads(body), sort_keys=True, separators=(", ", ": "))

    assert reserialised != body
    with pytest.raises(InvalidWebhookSignatureError):
        await verify_clerk_webhook(make_request(reserialised.encode(), headers))


async def test_signature_from_a_different_secret_is_rejected():
    body = json.dumps(PAYLOAD)
    headers = signed_headers(body, secret=OTHER_SECRET)

    with pytest.raises(InvalidWebhookSignatureError):
        await verify_clerk_webhook(make_request(body.encode(), headers))


async def test_stale_timestamp_is_rejected():
    """svix enforces a five-minute tolerance; this is the replay window bound."""
    body = json.dumps(PAYLOAD)
    old = datetime.now(tz=UTC) - timedelta(minutes=10)

    with pytest.raises(InvalidWebhookSignatureError):
        await verify_clerk_webhook(make_request(body.encode(), signed_headers(body, ts=old)))


async def test_future_timestamp_is_rejected():
    body = json.dumps(PAYLOAD)
    future = datetime.now(tz=UTC) + timedelta(minutes=10)

    with pytest.raises(InvalidWebhookSignatureError):
        await verify_clerk_webhook(make_request(body.encode(), signed_headers(body, ts=future)))


@pytest.mark.parametrize("missing", ["svix-id", "svix-timestamp", "svix-signature"])
async def test_missing_svix_header_is_rejected(missing):
    body = json.dumps(PAYLOAD)
    headers = signed_headers(body)
    del headers[missing]

    with pytest.raises(InvalidWebhookSignatureError):
        await verify_clerk_webhook(make_request(body.encode(), headers))


async def test_no_headers_at_all_is_rejected():
    body = json.dumps(PAYLOAD)
    with pytest.raises(InvalidWebhookSignatureError):
        await verify_clerk_webhook(make_request(body.encode(), {}))


async def test_oversized_body_is_rejected_before_verification():
    """The size check must precede the HMAC so abuse costs us nothing."""
    body = b"x" * (MAX_WEBHOOK_BODY_BYTES + 1)

    with pytest.raises(WebhookPayloadTooLargeError):
        await verify_clerk_webhook(make_request(body, {}))
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `APP_ENV=test uv run pytest tests/unit/api/test_webhook_dependency.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.api.dependencies.webhook'`

- [ ] **Step 5: Create the exceptions**

`app/services/clerk/webhooks/__init__.py`:

```python
"""Clerk webhook ingestion — verification errors and event handlers."""

from app.services.clerk.webhooks.exceptions import (
    InvalidWebhookSignatureError,
    WebhookError,
    WebhookPayloadTooLargeError,
)

__all__ = [
    "InvalidWebhookSignatureError",
    "WebhookError",
    "WebhookPayloadTooLargeError",
]
```

`app/services/clerk/webhooks/exceptions.py`:

```python
"""Clerk webhook exceptions."""

from app.exceptions.base import (
    AuthenticationError,
    ServiceError,
)


class WebhookError(ServiceError):
    """Base exception for webhook ingestion errors."""

    status_code = 400
    error_code = "WEBHOOK_ERROR"


class InvalidWebhookSignatureError(AuthenticationError):
    """Raised when svix verification fails, for any reason.

    Deliberately covers a forged signature, a missing svix header, and a
    timestamp outside the tolerance window alike. Distinguishing them in the
    response would tell an attacker which check they failed.
    """

    error_code = "WEBHOOK_INVALID_SIGNATURE"


class WebhookPayloadTooLargeError(WebhookError):
    """Raised when the request body exceeds the accepted size."""

    status_code = 413
    error_code = "WEBHOOK_PAYLOAD_TOO_LARGE"
```

- [ ] **Step 6: Create the event schema**

`app/schemas/webhook.py`:

```python
"""Clerk webhook event envelope.

Every Clerk webhook shares this shape: a `type` discriminator, a `data`
payload whose contents depend on the type, and delivery metadata. Payload
bodies are left as dicts rather than modelled per event — Clerk adds fields
without notice, and a strict model would reject deliveries for additions we
do not read.
"""

from typing import (
    Any,
    Optional,
)

from pydantic import (
    BaseModel,
    ConfigDict,
)


class ClerkEvent(BaseModel):
    """A verified Clerk webhook event."""

    model_config = ConfigDict(extra="ignore")

    type: str
    data: dict[str, Any]
    timestamp: Optional[int] = None
    instance_id: Optional[str] = None
```

- [ ] **Step 7: Create the verification dependency**

`app/api/dependencies/webhook.py`:

```python
"""Clerk webhook signature verification.

This is the only thing authenticating the webhook endpoint — there is no
JWT and no session. AuthMiddleware runs permissively and sets no identity
for these requests, by design: the svix signature is the credential.
"""

from typing import Final

from fastapi import Request
from svix.webhooks import Webhook
from svix.webhooks import WebhookVerificationError as SvixWebhookVerificationError

from app.core.config import settings
from app.core.logging import logger
from app.schemas.webhook import ClerkEvent
from app.services.clerk.webhooks.exceptions import (
    InvalidWebhookSignatureError,
    WebhookPayloadTooLargeError,
)

# Clerk payloads are a few KB. Starlette buffers the whole body in memory, so
# without a ceiling an unauthenticated caller can make us allocate and hash
# arbitrary input. Checked before the HMAC so abuse costs nothing.
MAX_WEBHOOK_BODY_BYTES: Final[int] = 256 * 1024


async def verify_clerk_webhook(request: Request) -> ClerkEvent:
    """Verify a Clerk webhook signature and return the parsed event.

    Args:
        request: The incoming request. Its raw body is read exactly once.

    Returns:
        The verified event.

    Raises:
        WebhookPayloadTooLargeError: Body exceeds MAX_WEBHOOK_BODY_BYTES.
        InvalidWebhookSignatureError: Signature invalid, headers missing, or
            timestamp outside svix's five-minute tolerance.
    """
    body = await request.body()

    if len(body) > MAX_WEBHOOK_BODY_BYTES:
        logger.warning("webhook_payload_too_large", size=len(body))
        raise WebhookPayloadTooLargeError("Webhook payload too large", size=len(body))

    secret = settings.auth.WEBHOOK_SIGNING_SECRET.get_secret_value()

    try:
        # The raw bytes are the signed artifact. Parsing and re-serialising
        # would change key order or whitespace and break the HMAC.
        payload = Webhook(secret).verify(body, dict(request.headers))
    except (SvixWebhookVerificationError, ValueError) as exc:
        # One error for every failure mode: bad signature, missing header,
        # stale timestamp, malformed secret. Never reveal which.
        logger.warning("webhook_verification_failed", reason=type(exc).__name__)
        raise InvalidWebhookSignatureError("Invalid webhook signature") from exc

    event = ClerkEvent.model_validate(payload)
    logger.debug("webhook_verified", event_type=event.type)
    return event
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `APP_ENV=test uv run pytest tests/unit/api/test_webhook_dependency.py -v`
Expected: PASS (12 tests, including the 3 parametrized header cases)

- [ ] **Step 9: Verify the entrypoint change**

```bash
REQUIRED_ENV_VARS= bash -c 'source scripts/docker-entrypoint.sh true' 2>&1 | tail -3
```
Expected: no "required environment variables are missing" error — the migrate service's opt-out still works.

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml uv.lock app/core/config.py app/schemas/webhook.py app/services/clerk/webhooks/ app/api/dependencies/webhook.py scripts/docker-entrypoint.sh .env.example .env.development .env.test tests/unit/api/test_webhook_dependency.py
git commit -m "feat(webhooks): verify Clerk webhook signatures

The svix signature is the only credential on this endpoint, so the
dependency is written defensively and tested adversarially: raw-byte
verification, a size cap ahead of the HMAC, and a single opaque error for
every failure mode so a caller cannot learn which check they failed.

The secret is enforced by REQUIRED_ENV_VARS rather than a required
pydantic field. alembic/env.py imports app.core.config, so a required
field would force the one-shot migrate service to carry a webhook secret
it never uses and would surface a missing secret as a failed migration."
```

---

### Task 5: Route and dispatch skeleton

An endpoint that verifies, dispatches to an empty registry, and returns 204. Handlers arrive in Tasks 6 and 7.

**Files:**
- Create: `app/services/clerk/webhooks/service.py`
- Create: `app/api/v1/webhooks.py`
- Modify: `app/api/v1/api.py`
- Test: `tests/integration/api/test_webhooks.py` (create)

**Interfaces:**
- Consumes: `verify_clerk_webhook`, `ClerkEvent`, `DbSession`, `ChatbotAgentDep`
- Produces:
  - `WebhookHandler = Callable[[dict, AsyncSession, BaseAgent], Awaitable[None]]`
  - `ClerkWebhookService.dispatch(event: ClerkEvent, session: AsyncSession, agent: BaseAgent) -> None`
  - `ClerkWebhookService.register(event_type: str, handler: WebhookHandler) -> None`
  - module singleton `clerk_webhook_service`

- [ ] **Step 1: Write the failing test**

Create `tests/integration/api/test_webhooks.py`:

```python
"""End-to-end webhook route tests against a real database."""

import json
from datetime import UTC, datetime

import pytest
from svix.webhooks import Webhook

pytestmark = pytest.mark.integration

TEST_SECRET = "whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw"
WEBHOOK_URL = "/api/v1/webhooks/clerk"


def signed(body: str, msg_id: str = "msg_1") -> dict:
    ts = datetime.now(tz=UTC)
    return {
        "svix-id": msg_id,
        "svix-timestamp": str(int(ts.timestamp())),
        "svix-signature": Webhook(TEST_SECRET).sign(msg_id, ts, body),
        "content-type": "application/json",
    }


def envelope(event_type: str, data: dict) -> str:
    return json.dumps(
        {
            "type": event_type,
            "object": "event",
            "timestamp": int(datetime.now(tz=UTC).timestamp() * 1000),
            "instance_id": "ins_test",
            "data": data,
        }
    )


async def test_unknown_event_type_returns_204(client):
    """Unhandled types must never error — Clerk retries errors and then
    disables the endpoint."""
    body = envelope("session.created", {"id": "sess_1"})
    response = client.post(WEBHOOK_URL, content=body, headers=signed(body))
    assert response.status_code == 204


async def test_unsigned_request_is_rejected(client):
    body = envelope("user.created", {"id": "user_1"})
    response = client.post(WEBHOOK_URL, content=body, headers={"content-type": "application/json"})
    assert response.status_code == 401


async def test_tampered_body_is_rejected(client):
    body = envelope("user.created", {"id": "user_1"})
    headers = signed(body)
    tampered = envelope("user.created", {"id": "user_attacker"})
    response = client.post(WEBHOOK_URL, content=tampered, headers=headers)
    assert response.status_code == 401


async def test_endpoint_requires_no_bearer_token(client):
    """The signature is the credential; no JWT is involved."""
    body = envelope("session.created", {"id": "sess_1"})
    response = client.post(WEBHOOK_URL, content=body, headers=signed(body))
    assert response.status_code == 204
```

Check `tests/integration/api/` for the existing `client` fixture name and reuse it verbatim; if the fixture is named differently in `tests/conftest.py`, use that name instead.

- [ ] **Step 2: Run test to verify it fails**

Run: `APP_ENV=test uv run pytest tests/integration/api/test_webhooks.py -v`
Expected: FAIL with 404 — the route does not exist.

- [ ] **Step 3: Create the dispatch service**

`app/services/clerk/webhooks/service.py`:

```python
"""Clerk webhook dispatch.

Handlers are registered by event type rather than selected with a chain of
conditionals, so each one stays independently testable and the registry
doubles as the list of events this app subscribes to.

Every handler must be idempotent. There is no dedup table: svix supplies
signature validity and a five-minute timestamp tolerance, and within that
window a replay must converge rather than duplicate. See the design spec
for the trigger to revisit that decision.
"""

from typing import (
    Awaitable,
    Callable,
    Dict,
)

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base.agent import BaseAgent
from app.core.logging import logger
from app.schemas.webhook import ClerkEvent

WebhookHandler = Callable[[dict, AsyncSession, BaseAgent], Awaitable[None]]


class ClerkWebhookService:
    """Routes verified Clerk events to their handlers."""

    def __init__(self) -> None:
        """Build an empty registry."""
        self._handlers: Dict[str, WebhookHandler] = {}

    def register(self, event_type: str, handler: WebhookHandler) -> None:
        """Register a handler for one Clerk event type.

        Args:
            event_type: The Clerk event string, e.g. "user.created".
            handler: Coroutine taking (data, session, agent).
        """
        self._handlers[event_type] = handler

    async def dispatch(
        self,
        event: ClerkEvent,
        session: AsyncSession,
        agent: BaseAgent,
    ) -> None:
        """Run the handler registered for this event's type.

        An unregistered type is logged and ignored. It must not raise: Clerk
        retries failed deliveries and disables endpoints that keep failing, so
        an error here would eventually cost us the events we do handle.

        Args:
            event: The verified event.
            session: DB session, committed by the request dependency.
            agent: Agent used by handlers that clear conversation history.
        """
        handler = self._handlers.get(event.type)

        if handler is None:
            logger.info("webhook_event_unhandled", event_type=event.type)
            return

        await handler(event.data, session, agent)
        logger.info("webhook_event_processed", event_type=event.type)


clerk_webhook_service = ClerkWebhookService()
```

- [ ] **Step 4: Create the route**

`app/api/v1/webhooks.py`:

```python
"""Clerk webhook endpoint.

Deliberately carries no rate limit. svix bursts on retry, and a 429 reads as
a failed delivery, provoking further retries. The signature check is the gate
and it is cheap.

RLS note: get_db_session calls set_session_context(session, request.state.user_id),
which is None here because AuthMiddleware initialises it so and nothing
authenticates a webhook. That is inert today — set_config is strict, so a NULL
is a no-op, and the same already happens on every unauthenticated request. But
this session carries no app.current_user_id. If RLS policies are ever enforced
on the user table, this path is blocked and needs an explicit system-context
escape hatch.
"""

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
)

from app.api.dependencies.agent import ChatbotAgentDep
from app.api.dependencies.database import DbSession
from app.api.dependencies.webhook import verify_clerk_webhook
from app.schemas.webhook import ClerkEvent
from app.services.clerk.webhooks.service import clerk_webhook_service

router = APIRouter()


@router.post(
    "/clerk",
    status_code=204,
    operation_id="clerkWebhook",
    summary="Clerk webhook receiver",
    include_in_schema=False,
)
async def clerk_webhook(
    event: Annotated[ClerkEvent, Depends(verify_clerk_webhook)],
    session: DbSession,
    agent: ChatbotAgentDep,
) -> None:
    """Receive a verified Clerk webhook event and dispatch it.

    Args:
        event: The verified event, produced by the signature dependency.
        session: Database session.
        agent: Agent used by the deletion handler to clear chat history.
    """
    await clerk_webhook_service.dispatch(event, session, agent)
```

- [ ] **Step 5: Register the router**

In `app/api/v1/api.py`, add the import and the include:

```python
from app.api.v1.webhooks import router as webhooks_router
```

```python
api_router.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `APP_ENV=test uv run pytest tests/integration/api/test_webhooks.py -v`
Expected: PASS (4 tests)

- [ ] **Step 7: Commit**

```bash
git add app/services/clerk/webhooks/service.py app/api/v1/webhooks.py app/api/v1/api.py tests/integration/api/test_webhooks.py
git commit -m "feat(webhooks): add the Clerk webhook route and dispatch registry

Handlers are registered by event type rather than selected with a chain of
conditionals, so the registry doubles as the list of subscribed events.

Unregistered types return 204 rather than an error: Clerk retries failed
deliveries and disables endpoints that keep failing, so erroring on an
event we simply do not handle would eventually cost us the ones we do."
```

---

### Task 6: `user.*` handlers

**Files:**
- Create: `app/services/clerk/webhooks/user_handlers.py`
- Modify: `app/services/clerk/webhooks/service.py` (register them)
- Test: `tests/unit/services/test_webhook_user_handlers.py`

**Interfaces:**
- Consumes: `user_repository.get_by_clerk_id/create_or_get/update_from_clerk`, `user_service.erase_user/link_supplier_from_metadata`, `clerk_timestamp_to_datetime`
- Produces:
  - `primary_email_from_payload(data: dict) -> Optional[str]`
  - `is_primary_email_verified(data: dict) -> bool`
  - `handle_user_created / handle_user_updated / handle_user_deleted` — all `(data: dict, session: AsyncSession, agent: BaseAgent) -> None`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/services/test_webhook_user_handlers.py`:

```python
"""Tests for the user.* webhook handlers.

Two invariants are load-bearing and tested explicitly:

1. Idempotency. There is no dedup table, so a replay within svix's
   five-minute tolerance must converge, not duplicate.
2. Never resurrect. user.updated for an unknown clerk_id is ambiguous —
   the create event may not have landed, or the user may have been erased
   (anonymize_user rewrites clerk_id, so the two are indistinguishable).
   The handler must never create a row.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.user import User
from app.services.clerk.webhooks.user_handlers import (
    handle_user_created,
    handle_user_deleted,
    handle_user_updated,
    is_primary_email_verified,
    primary_email_from_payload,
)

pytestmark = pytest.mark.unit

NOW_MS = 1754000000000
NOW_DT = datetime.fromtimestamp(NOW_MS / 1000, tz=UTC)

USER_PAYLOAD = {
    "id": "user_abc",
    "first_name": "Ada",
    "last_name": "Lovelace",
    "image_url": "https://img.clerk.com/x",
    "public_metadata": {},
    "primary_email_address_id": "idn_1",
    "email_addresses": [
        {
            "id": "idn_1",
            "email_address": "ada@example.com",
            "verification": {"status": "verified"},
        },
        {
            "id": "idn_2",
            "email_address": "other@example.com",
            "verification": {"status": "unverified"},
        },
    ],
    "updated_at": NOW_MS,
}


@pytest.fixture
def session() -> AsyncMock:
    s = AsyncMock()
    s.add = MagicMock()
    return s


def existing_user(last_synced_at: datetime = NOW_DT) -> User:
    user = User(id="uuid-1", clerk_id="user_abc", email="ada@example.com", org_id="org_1")
    user.last_synced_at = last_synced_at
    return user


def test_primary_email_picks_the_primary_address():
    assert primary_email_from_payload(USER_PAYLOAD) == "ada@example.com"


def test_primary_email_returns_none_when_absent():
    assert primary_email_from_payload({"email_addresses": []}) is None


def test_email_verified_reads_the_primary_address_only():
    assert is_primary_email_verified(USER_PAYLOAD) is True
    unverified = {
        **USER_PAYLOAD,
        "email_addresses": [
            {"id": "idn_1", "email_address": "a@b.c", "verification": {"status": "unverified"}}
        ],
    }
    assert is_primary_email_verified(unverified) is False


async def test_user_created_inserts_with_null_org_and_clerk_timestamp(session):
    with (
        patch(
            "app.services.clerk.webhooks.user_handlers.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.clerk.webhooks.user_handlers.user_repository.create_or_get",
            new=AsyncMock(return_value=existing_user()),
        ) as create,
        patch(
            "app.services.clerk.webhooks.user_handlers.user_service.link_supplier_from_metadata",
            new=AsyncMock(return_value=None),
        ),
    ):
        await handle_user_created(USER_PAYLOAD, session, AsyncMock())

    kwargs = create.await_args.kwargs
    assert kwargs["org_id"] is None
    assert kwargs["email"] == "ada@example.com"
    assert kwargs["last_synced_at"] == NOW_DT


async def test_user_created_on_existing_row_applies_as_update(session):
    user = existing_user(last_synced_at=NOW_DT - timedelta(hours=1))
    with (
        patch(
            "app.services.clerk.webhooks.user_handlers.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.services.clerk.webhooks.user_handlers.user_repository.create_or_get",
            new=AsyncMock(),
        ) as create,
        patch(
            "app.services.clerk.webhooks.user_handlers.user_repository.update_from_clerk",
            new=AsyncMock(return_value=user),
        ) as update,
        patch(
            "app.services.clerk.webhooks.user_handlers.user_service.link_supplier_from_metadata",
            new=AsyncMock(return_value=None),
        ),
    ):
        await handle_user_created(USER_PAYLOAD, session, AsyncMock())

    create.assert_not_awaited()
    update.assert_awaited_once()


async def test_user_created_without_an_email_is_skipped(session):
    with patch(
        "app.services.clerk.webhooks.user_handlers.user_repository.create_or_get",
        new=AsyncMock(),
    ) as create:
        await handle_user_created({"id": "user_abc", "email_addresses": []}, session, AsyncMock())

    create.assert_not_awaited()


async def test_user_updated_applies_the_profile(session):
    user = existing_user(last_synced_at=NOW_DT - timedelta(hours=1))
    with (
        patch(
            "app.services.clerk.webhooks.user_handlers.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.services.clerk.webhooks.user_handlers.user_repository.update_from_clerk",
            new=AsyncMock(return_value=user),
        ) as update,
    ):
        await handle_user_updated(USER_PAYLOAD, session, AsyncMock())

    assert update.await_args.kwargs["first_name"] == "Ada"
    assert update.await_args.kwargs["last_synced_at"] == NOW_DT


async def test_user_updated_never_creates_a_row(session):
    """The never-resurrect invariant."""
    with (
        patch(
            "app.services.clerk.webhooks.user_handlers.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.clerk.webhooks.user_handlers.user_repository.create_or_get",
            new=AsyncMock(),
        ) as create,
        patch(
            "app.services.clerk.webhooks.user_handlers.user_repository.update_from_clerk",
            new=AsyncMock(),
        ) as update,
    ):
        await handle_user_updated(USER_PAYLOAD, session, AsyncMock())

    create.assert_not_awaited()
    update.assert_not_awaited()


async def test_stale_event_is_dropped(session):
    """An event older than what we have synced must not overwrite newer data."""
    user = existing_user(last_synced_at=NOW_DT + timedelta(hours=1))
    with (
        patch(
            "app.services.clerk.webhooks.user_handlers.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.services.clerk.webhooks.user_handlers.user_repository.update_from_clerk",
            new=AsyncMock(),
        ) as update,
    ):
        await handle_user_updated(USER_PAYLOAD, session, AsyncMock())

    update.assert_not_awaited()


async def test_same_timestamp_still_applies(session):
    """Strict `<` — an identical timestamp is applied rather than risking a
    dropped distinct event. Safe because the write is idempotent."""
    user = existing_user(last_synced_at=NOW_DT)
    with (
        patch(
            "app.services.clerk.webhooks.user_handlers.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.services.clerk.webhooks.user_handlers.user_repository.update_from_clerk",
            new=AsyncMock(return_value=user),
        ) as update,
    ):
        await handle_user_updated(USER_PAYLOAD, session, AsyncMock())

    update.assert_awaited_once()


async def test_user_deleted_runs_the_erasure_cascade(session):
    user = existing_user()
    with (
        patch(
            "app.services.clerk.webhooks.user_handlers.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.services.clerk.webhooks.user_handlers.user_service.erase_user",
            new=AsyncMock(),
        ) as erase,
    ):
        await handle_user_deleted({"id": "user_abc", "deleted": True}, session, AsyncMock())

    erase.assert_awaited_once()


async def test_user_deleted_for_unknown_user_is_a_noop(session):
    """The echo of our own DELETE /me, and any replay, lands here."""
    with (
        patch(
            "app.services.clerk.webhooks.user_handlers.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.clerk.webhooks.user_handlers.user_service.erase_user",
            new=AsyncMock(),
        ) as erase,
    ):
        await handle_user_deleted({"id": "user_abc", "deleted": True}, session, AsyncMock())

    erase.assert_not_awaited()


async def test_no_handler_populates_the_role_cache(session):
    """Populating before commit could serve a value for a rolled-back
    transaction. Handlers invalidate; they never set."""
    user = existing_user(last_synced_at=NOW_DT - timedelta(hours=1))
    with (
        patch(
            "app.services.clerk.webhooks.user_handlers.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.services.clerk.webhooks.user_handlers.user_repository.update_from_clerk",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.services.user.cache.UserCache.set_org_role", new=AsyncMock()
        ) as set_role,
    ):
        await handle_user_updated(USER_PAYLOAD, session, AsyncMock())

    set_role.assert_not_awaited()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `APP_ENV=test uv run pytest tests/unit/services/test_webhook_user_handlers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.clerk.webhooks.user_handlers'`

- [ ] **Step 3: Create the handlers**

`app/services/clerk/webhooks/user_handlers.py`:

```python
"""Handlers for Clerk user.* webhook events.

All three are idempotent. There is no dedup table, so a replay inside
svix's five-minute tolerance window must converge rather than duplicate.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base.agent import BaseAgent
from app.core.logging import logger
from app.models.user import User
from app.services.user import (
    user_repository,
    user_service,
)
from app.utils.clerk import clerk_timestamp_to_datetime


def primary_email_from_payload(data: dict) -> Optional[str]:
    """Extract the primary email address from a Clerk user payload.

    The SDK helper takes an SDK object; webhook payloads are plain dicts, so
    this is the dict equivalent.

    Args:
        data: A Clerk user payload.

    Returns:
        The primary email address, or None if the payload has none.
    """
    primary_id = data.get("primary_email_address_id")
    for entry in data.get("email_addresses") or []:
        if entry.get("id") == primary_id:
            return entry.get("email_address")
    return None


def is_primary_email_verified(data: dict) -> bool:
    """Report whether the primary email address is verified.

    Args:
        data: A Clerk user payload.

    Returns:
        True only when the primary address exists and is verified.
    """
    primary_id = data.get("primary_email_address_id")
    for entry in data.get("email_addresses") or []:
        if entry.get("id") == primary_id:
            return (entry.get("verification") or {}).get("status") == "verified"
    return False


async def _apply_profile(
    session: AsyncSession,
    user: User,
    data: dict,
    event_ts: Optional[datetime],
) -> None:
    """Apply a profile snapshot, unless the event predates our last sync.

    Clerk guarantees no ordering, so two updates can arrive reversed. The
    comparison is strict: an identical timestamp is applied rather than
    dropped, because the write is idempotent and a same-millisecond distinct
    event is the worse thing to lose.

    Args:
        session: DB session.
        user: The user to update.
        data: The Clerk user payload.
        event_ts: The payload's updated_at, or None if absent.
    """
    if event_ts is not None and event_ts < user.last_synced_at:
        logger.info(
            "webhook_event_stale",
            clerk_id=user.clerk_id,
            event_ts=event_ts.isoformat(),
            last_synced_at=user.last_synced_at.isoformat(),
        )
        return

    await user_repository.update_from_clerk(
        session=session,
        user=user,
        email=primary_email_from_payload(data),
        first_name=data.get("first_name"),
        last_name=data.get("last_name"),
        avatar_url=data.get("image_url"),
        email_verified=is_primary_email_verified(data),
        last_synced_at=event_ts,
    )


async def handle_user_created(data: dict, session: AsyncSession, agent: BaseAgent) -> None:
    """Create the user row, or apply the payload as an update if it exists.

    Inserts with a null org_id: Clerk's user.created payload carries no
    organisation, because membership is a separate resource with its own
    events. organization_membership.created fills it in, and JIT fills it in
    at first login as a second backstop.

    Safe to handle unconditionally only because the Clerk instance is
    invitation-only. If public sign-up is ever enabled this becomes an
    unauthenticated row-creation vector and must be gated on membership.

    Args:
        data: The Clerk user payload.
        session: DB session.
        agent: Unused; present for a uniform handler signature.
    """
    clerk_id = data.get("id")
    email = primary_email_from_payload(data)

    if not clerk_id or not email:
        logger.warning("webhook_user_created_incomplete", clerk_id=clerk_id, has_email=bool(email))
        return

    event_ts = clerk_timestamp_to_datetime(data.get("updated_at"))
    user = await user_repository.get_by_clerk_id(session, clerk_id)

    if user is None:
        user = await user_repository.create_or_get(
            session=session,
            clerk_id=clerk_id,
            email=email,
            org_id=None,
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            avatar_url=data.get("image_url"),
            email_verified=is_primary_email_verified(data),
            last_synced_at=event_ts,
        )
        logger.info("webhook_user_created", user_id=user.id, clerk_id=clerk_id)
    else:
        # A replay, or a create arriving after an update. Converge rather
        # than conflict.
        await _apply_profile(session, user, data, event_ts)

    await user_service.link_supplier_from_metadata(
        user, data.get("public_metadata") or {}, session
    )


async def handle_user_updated(data: dict, session: AsyncSession, agent: BaseAgent) -> None:
    """Apply a profile update. Never creates a row.

    An unknown clerk_id has two indistinguishable causes: the create event has
    not landed, or the user was erased — anonymize_user() rewrites clerk_id,
    so an erased user looks exactly like one who never existed. Creating here
    would resurrect deleted users, so the handler declines.

    Args:
        data: The Clerk user payload.
        session: DB session.
        agent: Unused; present for a uniform handler signature.
    """
    clerk_id = data.get("id")
    if not clerk_id:
        logger.warning("webhook_user_updated_incomplete")
        return

    user = await user_repository.get_by_clerk_id(session, clerk_id)
    if user is None:
        logger.warning("webhook_user_updated_unknown", clerk_id=clerk_id)
        return

    await _apply_profile(session, user, data, clerk_timestamp_to_datetime(data.get("updated_at")))


async def handle_user_deleted(data: dict, session: AsyncSession, agent: BaseAgent) -> None:
    """Run the full GDPR erasure cascade.

    Anonymising the row alone would orphan LangGraph checkpoints and mem0
    memories with no user row left pointing at them, so nothing would ever
    clean them up — a hole that opens only on the dashboard-initiated path.

    No ordering guard: the payload is a DeletedObjectJSON with no updated_at,
    and deletion is self-protecting. After erasure clerk_id is rewritten, so
    any later event for the original id finds no row.

    Args:
        data: The Clerk deleted-object payload.
        session: DB session.
        agent: Agent whose checkpoints hold the conversation history.
    """
    clerk_id = data.get("id")
    if not clerk_id:
        logger.warning("webhook_user_deleted_incomplete")
        return

    user = await user_repository.get_by_clerk_id(session, clerk_id)
    if user is None:
        # Either the echo of our own DELETE /me, or a replay. Both benign.
        logger.info("webhook_user_deleted_noop", clerk_id=clerk_id)
        return

    await user_service.erase_user(user, session, agent)
    logger.info("webhook_user_erased", clerk_id=clerk_id)
```

- [ ] **Step 4: Register the handlers**

Append to `app/services/clerk/webhooks/service.py`, after the singleton:

```python
clerk_webhook_service.register("user.created", handle_user_created)
clerk_webhook_service.register("user.updated", handle_user_updated)
clerk_webhook_service.register("user.deleted", handle_user_deleted)
```

and add the import at the top of that file:

```python
from app.services.clerk.webhooks.user_handlers import (
    handle_user_created,
    handle_user_deleted,
    handle_user_updated,
)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `APP_ENV=test uv run pytest tests/unit/services/test_webhook_user_handlers.py -v`
Expected: PASS (13 tests)

Then `make lint`.

- [ ] **Step 6: Commit**

```bash
git add app/services/clerk/webhooks/user_handlers.py app/services/clerk/webhooks/service.py tests/unit/services/test_webhook_user_handlers.py
git commit -m "feat(webhooks): handle user.created, user.updated, user.deleted

user.updated is deliberately update-only. An unknown clerk_id is
ambiguous — the create event may not have landed, or the user may have
been erased, and anonymize_user() rewrites clerk_id so the two cases are
indistinguishable. Creating there would resurrect deleted users, so the
handler declines and takes the GDPR-safe side.

user.deleted runs the full erasure cascade rather than anonymising alone,
which would orphan LangGraph checkpoints and mem0 memories with no user
row left pointing at them."
```

---

### Task 7: `organization_membership.*` handlers

**Files:**
- Create: `app/services/clerk/webhooks/membership_handlers.py`
- Modify: `app/services/clerk/webhooks/service.py` (register them)
- Modify: `app/services/user/service.py:171` (drop the superseded TODO)
- Test: `tests/unit/services/test_webhook_membership_handlers.py`

**Interfaces:**
- Consumes: `user_repository.get_by_clerk_id/create_or_get/update_org_id`, `user_service.link_supplier_from_metadata/unlink_supplier_contact`, `user_cache.invalidate_user`
- Produces: `handle_membership_created / handle_membership_updated / handle_membership_deleted` — all `(data: dict, session: AsyncSession, agent: BaseAgent) -> None`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/services/test_webhook_membership_handlers.py`:

```python
"""Tests for the organization_membership.* webhook handlers.

The membership payload carries public_user_data, which is what lets these
handlers create a missing user row themselves rather than returning an error
and relying on a retry. That is the answer to Clerk delivering
organization_membership.created before user.created.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.user import User
from app.services.clerk.webhooks.membership_handlers import (
    handle_membership_created,
    handle_membership_deleted,
    handle_membership_updated,
)

pytestmark = pytest.mark.unit

MEMBERSHIP_PAYLOAD = {
    "id": "orgmem_1",
    "role": "org:supplier",
    "organization": {"id": "org_1", "name": "Acme"},
    "public_user_data": {
        "user_id": "user_abc",
        "identifier": "ada@example.com",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "image_url": "https://img.clerk.com/x",
    },
    "public_metadata": {},
    "updated_at": 1754000000000,
}


@pytest.fixture
def session() -> AsyncMock:
    s = AsyncMock()
    s.add = MagicMock()
    return s


def make_user(org_id=None) -> User:
    return User(id="uuid-1", clerk_id="user_abc", email="ada@example.com", org_id=org_id)


async def test_created_sets_org_id_on_existing_user(session):
    user = make_user(org_id=None)
    with (
        patch(
            "app.services.clerk.webhooks.membership_handlers.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.services.clerk.webhooks.membership_handlers.user_repository.update_org_id",
            new=AsyncMock(return_value=user),
        ) as update_org,
        patch(
            "app.services.clerk.webhooks.membership_handlers.user_cache.invalidate_user",
            new=AsyncMock(),
        ),
        patch(
            "app.services.clerk.webhooks.membership_handlers.user_service.link_supplier_from_metadata",
            new=AsyncMock(return_value=None),
        ),
    ):
        await handle_membership_created(MEMBERSHIP_PAYLOAD, session, AsyncMock())

    update_org.assert_awaited_once()
    assert update_org.await_args.args[2] == "org_1"


async def test_created_builds_the_user_when_it_does_not_exist(session):
    """Handles organization_membership.created arriving before user.created,
    without a Clerk API call and without relying on a retry."""
    created = make_user(org_id="org_1")
    with (
        patch(
            "app.services.clerk.webhooks.membership_handlers.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.clerk.webhooks.membership_handlers.user_repository.create_or_get",
            new=AsyncMock(return_value=created),
        ) as create,
        patch(
            "app.services.clerk.webhooks.membership_handlers.user_cache.invalidate_user",
            new=AsyncMock(),
        ),
        patch(
            "app.services.clerk.webhooks.membership_handlers.user_service.link_supplier_from_metadata",
            new=AsyncMock(return_value=None),
        ),
    ):
        await handle_membership_created(MEMBERSHIP_PAYLOAD, session, AsyncMock())

    kwargs = create.await_args.kwargs
    assert kwargs["clerk_id"] == "user_abc"
    assert kwargs["email"] == "ada@example.com"
    assert kwargs["org_id"] == "org_1"


async def test_created_without_an_identifier_is_skipped(session):
    payload = {**MEMBERSHIP_PAYLOAD, "public_user_data": {"user_id": "user_abc"}}
    with (
        patch(
            "app.services.clerk.webhooks.membership_handlers.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.clerk.webhooks.membership_handlers.user_repository.create_or_get",
            new=AsyncMock(),
        ) as create,
    ):
        await handle_membership_created(payload, session, AsyncMock())

    create.assert_not_awaited()


async def test_created_is_idempotent_when_org_already_matches(session):
    user = make_user(org_id="org_1")
    with (
        patch(
            "app.services.clerk.webhooks.membership_handlers.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.services.clerk.webhooks.membership_handlers.user_repository.update_org_id",
            new=AsyncMock(),
        ) as update_org,
        patch(
            "app.services.clerk.webhooks.membership_handlers.user_cache.invalidate_user",
            new=AsyncMock(),
        ),
        patch(
            "app.services.clerk.webhooks.membership_handlers.user_service.link_supplier_from_metadata",
            new=AsyncMock(return_value=None),
        ),
    ):
        await handle_membership_created(MEMBERSHIP_PAYLOAD, session, AsyncMock())

    update_org.assert_not_awaited()


async def test_updated_invalidates_the_role_cache(session):
    user = make_user(org_id="org_1")
    with (
        patch(
            "app.services.clerk.webhooks.membership_handlers.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.services.clerk.webhooks.membership_handlers.user_cache.invalidate_user",
            new=AsyncMock(),
        ) as invalidate,
    ):
        await handle_membership_updated(MEMBERSHIP_PAYLOAD, session, AsyncMock())

    invalidate.assert_awaited_once_with(clerk_id="user_abc", user_id="uuid-1")


async def test_updated_never_populates_the_role_cache(session):
    """The event hands us the new role, but writing it before the request's
    commit could serve a value for a transaction that rolls back."""
    user = make_user(org_id="org_1")
    with (
        patch(
            "app.services.clerk.webhooks.membership_handlers.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.services.clerk.webhooks.membership_handlers.user_cache.invalidate_user",
            new=AsyncMock(),
        ),
        patch("app.services.user.cache.UserCache.set_org_role", new=AsyncMock()) as set_role,
    ):
        await handle_membership_updated(MEMBERSHIP_PAYLOAD, session, AsyncMock())

    set_role.assert_not_awaited()


async def test_deleted_clears_org_and_unlinks_the_supplier(session):
    user = make_user(org_id="org_1")
    with (
        patch(
            "app.services.clerk.webhooks.membership_handlers.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.services.clerk.webhooks.membership_handlers.user_service.unlink_supplier_contact",
            new=AsyncMock(return_value="sup_1"),
        ) as unlink,
        patch(
            "app.services.clerk.webhooks.membership_handlers.user_cache.invalidate_user",
            new=AsyncMock(),
        ) as invalidate,
    ):
        await handle_membership_deleted(MEMBERSHIP_PAYLOAD, session, AsyncMock())

    assert user.org_id is None
    unlink.assert_awaited_once()
    invalidate.assert_awaited_once_with(clerk_id="user_abc", user_id="uuid-1")


async def test_deleted_is_idempotent(session):
    """A replay finds org_id already cleared and no supplier to unlink."""
    user = make_user(org_id=None)
    with (
        patch(
            "app.services.clerk.webhooks.membership_handlers.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.services.clerk.webhooks.membership_handlers.user_service.unlink_supplier_contact",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.clerk.webhooks.membership_handlers.user_cache.invalidate_user",
            new=AsyncMock(),
        ),
    ):
        await handle_membership_deleted(MEMBERSHIP_PAYLOAD, session, AsyncMock())

    assert user.org_id is None


@pytest.mark.parametrize(
    "event_type",
    ["organizationMembership.created", "organization_membership.created"],
)
async def test_both_event_spellings_dispatch(event_type):
    """A wrong registry key fails silently, so both spellings are registered."""
    from app.services.clerk.webhooks.service import clerk_webhook_service

    assert clerk_webhook_service._handlers.get(event_type) is not None


async def test_deleted_for_unknown_user_is_a_noop(session):
    with (
        patch(
            "app.services.clerk.webhooks.membership_handlers.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.clerk.webhooks.membership_handlers.user_service.unlink_supplier_contact",
            new=AsyncMock(),
        ) as unlink,
    ):
        await handle_membership_deleted(MEMBERSHIP_PAYLOAD, session, AsyncMock())

    unlink.assert_not_awaited()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `APP_ENV=test uv run pytest tests/unit/services/test_webhook_membership_handlers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.clerk.webhooks.membership_handlers'`

- [ ] **Step 3: Create the handlers**

`app/services/clerk/webhooks/membership_handlers.py`:

```python
"""Handlers for Clerk organization_membership.* webhook events.

These close the role-revocation gap: without them a revoked role stays
honoured for up to UserCache.role_ttl seconds.

There is deliberately no ordering guard here and no membership sync column.
Reusing last_synced_at would conflate two unrelated clocks — a fresh
user.updated would begin dropping older-but-valid membership events. A
reversed membership pair that leaves a user org-less is instead repaired by
JIT, which re-syncs org_id from the JWT on the user's next request. That is
the stated role of JIT in this design, not an accident.
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base.agent import BaseAgent
from app.core.logging import logger
from app.models.user import User
from app.services.user import (
    user_cache,
    user_repository,
    user_service,
)
from app.utils.clerk import clerk_timestamp_to_datetime


def _organization_id(data: dict) -> Optional[str]:
    """Read the organisation id from a membership payload.

    Args:
        data: A Clerk organization membership payload.

    Returns:
        The organisation id, or None.
    """
    return (data.get("organization") or {}).get("id")


async def _resolve_or_create_user(data: dict, session: AsyncSession) -> Optional[User]:
    """Find the membership's user, creating the row if it is missing.

    The payload's public_user_data carries the clerk id, email, names and
    avatar, so a membership event arriving before user.created can build the
    row itself — no Clerk API call, and no error-and-retry cycle.

    Args:
        data: A Clerk organization membership payload.
        session: DB session.

    Returns:
        The user, or None if the payload lacks what a row requires.
    """
    public_user_data = data.get("public_user_data") or {}
    clerk_id = public_user_data.get("user_id")

    if not clerk_id:
        logger.warning("webhook_membership_missing_user_id", membership_id=data.get("id"))
        return None

    user = await user_repository.get_by_clerk_id(session, clerk_id)
    if user is not None:
        return user

    email = public_user_data.get("identifier")
    if not email:
        logger.warning("webhook_membership_missing_email", clerk_id=clerk_id)
        return None

    user = await user_repository.create_or_get(
        session=session,
        clerk_id=clerk_id,
        email=email,
        org_id=_organization_id(data),
        first_name=public_user_data.get("first_name"),
        last_name=public_user_data.get("last_name"),
        avatar_url=public_user_data.get("image_url"),
        # The membership payload does not report verification status. Start
        # false; user.created or user.updated corrects it.
        email_verified=False,
        last_synced_at=clerk_timestamp_to_datetime(data.get("updated_at")),
    )
    logger.info("webhook_user_created_from_membership", user_id=user.id, clerk_id=clerk_id)
    return user


async def _sync_org_and_invalidate(data: dict, session: AsyncSession, user: User) -> None:
    """Align org_id with the payload and drop the user's cached auth data.

    Invalidates rather than populates. The event carries the new role, but
    writing it before the request's commit could serve a value for a
    transaction that later rolls back; dropping an entry can only cost a
    DB read.

    Args:
        data: A Clerk organization membership payload.
        session: DB session.
        user: The membership's user.
    """
    org_id = _organization_id(data)
    if org_id and user.org_id != org_id:
        await user_repository.update_org_id(session, user, org_id)

    await user_cache.invalidate_user(clerk_id=user.clerk_id, user_id=user.id)


async def handle_membership_created(
    data: dict, session: AsyncSession, agent: BaseAgent
) -> None:
    """Attach a user to an organisation, creating the user row if needed.

    Args:
        data: The Clerk organization membership payload.
        session: DB session.
        agent: Unused; present for a uniform handler signature.
    """
    user = await _resolve_or_create_user(data, session)
    if user is None:
        return

    await _sync_org_and_invalidate(data, session, user)
    await user_service.link_supplier_from_metadata(
        user, data.get("public_metadata") or {}, session
    )
    logger.info(
        "webhook_membership_created",
        user_id=user.id,
        org_id=_organization_id(data),
        role=data.get("role"),
    )


async def handle_membership_updated(
    data: dict, session: AsyncSession, agent: BaseAgent
) -> None:
    """Apply a membership change — in practice, a role change.

    Args:
        data: The Clerk organization membership payload.
        session: DB session.
        agent: Unused; present for a uniform handler signature.
    """
    public_user_data = data.get("public_user_data") or {}
    clerk_id = public_user_data.get("user_id")

    if not clerk_id:
        logger.warning("webhook_membership_missing_user_id", membership_id=data.get("id"))
        return

    user = await user_repository.get_by_clerk_id(session, clerk_id)
    if user is None:
        logger.warning("webhook_membership_updated_unknown", clerk_id=clerk_id)
        return

    await _sync_org_and_invalidate(data, session, user)
    logger.info("webhook_membership_updated", user_id=user.id, role=data.get("role"))


async def handle_membership_deleted(
    data: dict, session: AsyncSession, agent: BaseAgent
) -> None:
    """Revoke access when a user is removed from, or leaves, an organisation.

    Clears org_id, unlinks any supplier this user was the contact for, and
    drops the cached role so revocation is immediate rather than bounded by
    the cache TTL.

    Unlinking the supplier leaves it contact-less with no signal to a project
    manager beyond this log line — a known cost, recorded in the design spec.

    Args:
        data: The Clerk organization membership payload.
        session: DB session.
        agent: Unused; present for a uniform handler signature.
    """
    public_user_data = data.get("public_user_data") or {}
    clerk_id = public_user_data.get("user_id")

    if not clerk_id:
        logger.warning("webhook_membership_missing_user_id", membership_id=data.get("id"))
        return

    user = await user_repository.get_by_clerk_id(session, clerk_id)
    if user is None:
        logger.info("webhook_membership_deleted_noop", clerk_id=clerk_id)
        return

    user.org_id = None
    session.add(user)
    await session.flush()

    supplier_id = await user_service.unlink_supplier_contact(user.id, session)
    await user_cache.invalidate_user(clerk_id=user.clerk_id, user_id=user.id)

    logger.info(
        "supplier_unlinked_on_offboarding",
        user_id=user.id,
        supplier_id=supplier_id,
        org_id=_organization_id(data),
    )
```

- [ ] **Step 4: Register the handlers**

Add to the import block in `app/services/clerk/webhooks/service.py`:

```python
from app.services.clerk.webhooks.membership_handlers import (
    handle_membership_created,
    handle_membership_deleted,
    handle_membership_updated,
)
```

and append to the registrations:

```python
# Clerk's dashboard webhook catalog names these in camelCase, while the
# application-log docs use snake_case. They are different taxonomies and the
# dashboard is what Svix actually registers — but a wrong key here fails
# SILENTLY: the handler simply never runs, with no error and no 4xx. Both
# spellings are registered so the subscription cannot miss.
for _prefix in ("organizationMembership", "organization_membership"):
    clerk_webhook_service.register(f"{_prefix}.created", handle_membership_created)
    clerk_webhook_service.register(f"{_prefix}.updated", handle_membership_updated)
    clerk_webhook_service.register(f"{_prefix}.deleted", handle_membership_deleted)
```

- [ ] **Step 5: Remove the superseded TODO**

In `app/services/user/service.py`, delete the `TODO(follow-up)` paragraph from the `resolve_org_role` docstring (it named `organizationMembership.updated/deleted`, which is not a real Clerk event string) and replace it with:

```python
        Revocation is now immediate in the common case: the
        organization_membership.updated and .deleted webhooks invalidate this
        entry. The TTL remains the bound for a dropped or delayed event.
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `APP_ENV=test uv run pytest tests/unit/services/test_webhook_membership_handlers.py -v`
Expected: PASS (9 tests)

Then the whole suite: `APP_ENV=test uv run pytest tests/ -v` and `make lint`.

- [ ] **Step 7: Commit**

```bash
git add app/services/clerk/webhooks/membership_handlers.py app/services/clerk/webhooks/service.py app/services/user/service.py tests/unit/services/test_webhook_membership_handlers.py
git commit -m "feat(webhooks): handle organization_membership.* events

Closes the role-revocation gap that resolve_org_role's TODO named — and
corrects the event strings while doing so: Clerk emits
organization_membership.*, not organizationMembership.*, so the TODO
described a subscription that would never have matched.

The created handler builds a missing user row from the payload's
public_user_data rather than erroring for a retry, which is what makes
organization_membership.created arriving before user.created harmless.

Handlers invalidate the role cache and never populate it: the event
carries the new role, but writing it before the request's commit could
serve a value for a transaction that rolls back."
```

---

### Task 8: End-to-end integration tests

Proves the whole path against a real database, including the ordering cases that unit tests mock away.

**Files:**
- Modify: `tests/integration/api/test_webhooks.py` (extend)

**Interfaces:**
- Consumes: everything from Tasks 4–7; the `client` and DB session fixtures from `tests/conftest.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/integration/api/test_webhooks.py`:

```python
USER_DATA = {
    "id": "user_e2e",
    "first_name": "Ada",
    "last_name": "Lovelace",
    "image_url": "https://img.clerk.com/x",
    "public_metadata": {},
    "primary_email_address_id": "idn_1",
    "email_addresses": [
        {"id": "idn_1", "email_address": "ada@e2e.test", "verification": {"status": "verified"}}
    ],
    "updated_at": 1754000000000,
}

MEMBERSHIP_DATA = {
    "id": "orgmem_e2e",
    "role": "org:supplier",
    "organization": {"id": "org_e2e"},
    "public_user_data": {
        "user_id": "user_e2e",
        "identifier": "ada@e2e.test",
        "first_name": "Ada",
        "last_name": "Lovelace",
    },
    "public_metadata": {},
    "updated_at": 1754000000000,
}


def post(client, event_type: str, data: dict, msg_id: str = "msg_e2e"):
    body = envelope(event_type, data)
    return client.post(WEBHOOK_URL, content=body, headers=signed(body, msg_id=msg_id))


async def test_user_created_persists_the_row(client, db_session):
    from app.services.user.repository import UserRepository

    assert post(client, "user.created", USER_DATA).status_code == 204

    user = await UserRepository.get_by_clerk_id(db_session, "user_e2e")
    assert user is not None
    assert user.email == "ada@e2e.test"
    assert user.org_id is None  # membership is a separate event


async def test_user_created_replayed_does_not_duplicate(client, db_session):
    from sqlmodel import select
    from app.models.user import User

    post(client, "user.created", USER_DATA, msg_id="msg_a")
    post(client, "user.created", USER_DATA, msg_id="msg_b")

    result = await db_session.execute(select(User).where(User.clerk_id == "user_e2e"))
    assert len(result.scalars().all()) == 1


async def test_membership_before_create_leaves_correct_state(client, db_session):
    """The reversed-delivery case. The membership handler builds the row from
    public_user_data, and the later user.created applies as an update."""
    from app.services.user.repository import UserRepository

    assert post(client, "organization_membership.created", MEMBERSHIP_DATA).status_code == 204
    assert post(client, "user.created", USER_DATA).status_code == 204

    user = await UserRepository.get_by_clerk_id(db_session, "user_e2e")
    assert user is not None
    assert user.org_id == "org_e2e"
    assert user.email_verified is True  # corrected by the later user.created


async def test_stale_update_does_not_overwrite_newer_data(client, db_session):
    from app.services.user.repository import UserRepository

    post(client, "user.created", USER_DATA)

    newer = {**USER_DATA, "first_name": "Newer", "updated_at": 1754000009000}
    stale = {**USER_DATA, "first_name": "Stale", "updated_at": 1753000000000}

    post(client, "user.updated", newer, msg_id="msg_new")
    post(client, "user.updated", stale, msg_id="msg_old")

    user = await UserRepository.get_by_clerk_id(db_session, "user_e2e")
    assert user.first_name == "Newer"


async def test_membership_deleted_clears_org(client, db_session):
    from app.services.user.repository import UserRepository

    post(client, "organization_membership.created", MEMBERSHIP_DATA)
    assert post(client, "organization_membership.deleted", MEMBERSHIP_DATA).status_code == 204

    user = await UserRepository.get_by_clerk_id(db_session, "user_e2e")
    assert user.org_id is None


async def test_user_deleted_anonymises_and_replay_is_a_noop(client, db_session):
    from app.services.user.repository import UserRepository

    post(client, "user.created", USER_DATA)

    assert post(client, "user.deleted", {"id": "user_e2e", "deleted": True}).status_code == 204
    assert await UserRepository.get_by_clerk_id(db_session, "user_e2e") is None

    # Replay — and the echo of our own DELETE /me — must not error.
    assert post(
        client, "user.deleted", {"id": "user_e2e", "deleted": True}, msg_id="msg_replay"
    ).status_code == 204


async def test_user_updated_after_deletion_does_not_resurrect(client, db_session):
    from sqlmodel import select
    from app.models.user import User

    post(client, "user.created", USER_DATA)
    post(client, "user.deleted", {"id": "user_e2e", "deleted": True})

    assert post(client, "user.updated", USER_DATA, msg_id="msg_after").status_code == 204

    result = await db_session.execute(select(User).where(User.clerk_id == "user_e2e"))
    assert result.scalars().all() == []
```

Match `db_session` to the actual fixture name in `tests/conftest.py`; use whatever the existing integration tests use.

- [ ] **Step 2: Run tests to verify they fail or pass**

Run: `APP_ENV=test uv run pytest tests/integration/api/test_webhooks.py -v`
Expected: PASS. If `test_membership_before_create_leaves_correct_state` fails on `email_verified`, the membership-created row was not updated by the later `user.created` — check that `handle_user_created` routes an existing row through `_apply_profile`.

- [ ] **Step 3: Run the whole suite with coverage**

Run: `make test-coverage`
Expected: PASS, with `app/services/clerk/webhooks/` and `app/api/dependencies/webhook.py` covered.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/api/test_webhooks.py
git commit -m "test(webhooks): end-to-end coverage against a real database

Covers the cases unit tests mock away: a replayed user.created not
duplicating a row, organization_membership.created arriving before
user.created and still converging, a stale user.updated failing to
overwrite newer data, and user.updated after user.deleted not
resurrecting the user."
```

---

### Task 9: ngrok dev service

**Files:**
- Modify: `docker-compose.dev.yml`
- Modify: `.env.example` (repo root)
- Modify: `docs/setup/clerk-webhooks.md` (drop the not-yet-implemented caveat)

- [ ] **Step 1: Add the service**

In `docker-compose.dev.yml`, after the `server` service:

```yaml
  ngrok:
    container_name: ngrok
    image: ngrok/ngrok:latest
    command: http server:8000 --url=${NGROK_DOMAIN}
    environment:
      NGROK_AUTHTOKEN: ${NGROK_AUTHTOKEN}
    depends_on:
      - server
    networks:
      - app-network
```

Deliberately absent from `docker-compose.prod.yml` — production is publicly reachable.

- [ ] **Step 2: Add the root env vars**

In the repo-root `.env.example`, beside `GRAFANA_ADMIN_PASSWORD`:

```env
# ngrok — development webhook tunnel. Static domain from the ngrok dashboard;
# it is permanent, so the Clerk endpoint URL is configured once.
NGROK_AUTHTOKEN=
NGROK_DOMAIN=
```

- [ ] **Step 3: Bring the stack up**

```bash
cd .. && make docker-run && make docker-logs-core
```
Expected: the `ngrok` container starts and logs the forwarding URL matching `NGROK_DOMAIN`.

- [ ] **Step 4: Verify against the real Clerk dashboard**

Follow `docs/setup/clerk-webhooks.md` to create the endpoint if it does not exist, then use the endpoint's **Testing** tab to send a `user.created`.

Expected: Clerk's delivery log shows **204**, and `make docker-logs-core` shows a `webhook_event_processed` line with `event_type=user.created`.

- [ ] **Step 5: Update the setup doc**

In `docs/setup/clerk-webhooks.md`, the verification section can now be followed end to end. No caveat is needed — remove nothing else.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.dev.yml .env.example docs/setup/clerk-webhooks.md
git commit -m "feat(dev): add ngrok tunnel for Clerk webhook testing

Bound to the account's static domain so the endpoint URL registered in
the Clerk dashboard survives container and host restarts and is
configured once. Dev only — production is publicly reachable."
```

---

## Verification

After Task 9, the full acceptance criteria from the spec:

```bash
cd server && make lint && make test-coverage
```

Manual checks against the running stack:

1. Edit a user's first name in the Clerk dashboard → the DB row updates without that user logging in.
2. Delete a user in the Clerk dashboard → the row is anonymised, conversations soft-deleted, and `user_erased` appears in the logs.
3. Remove a user from their organisation → `org_id` is cleared and `supplier_unlinked_on_offboarding` is logged.
4. Replay any delivery from the Clerk dashboard → 204, and no duplicate rows or errors.
5. `curl -X POST http://localhost:8000/api/v1/webhooks/clerk -d '{}'` → 401.
