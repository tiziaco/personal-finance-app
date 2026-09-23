# Conversation Repository Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move every database call in `app/modules/conversation/service.py` into a new `app/modules/conversation/repository.py`, so the conversation module follows the "services never touch the DB" rule that `account` and `supplier` already follow.

**Architecture:** A pure refactor. `ConversationRepository` owns every `session.get` / `select` / `add` / `flush` / `refresh`. `ConversationService` keeps its public methods and signatures and delegates to the repository. Callers (`router/`, `dependencies.py`, `handlers.py`) are untouched. The one deliberate removal is the unused hard-delete method, done first as its own commit.

**Tech Stack:** FastAPI, SQLModel / SQLAlchemy 2 async, pytest (`pytest.mark.integration` against the real test DB).

**Spec:** No separate spec. Scope agreed in session on 2026-09-23. The reference implementation is flyorbit's `server/app/modules/conversation/repository.py`, ported without flyorbit's erasure-policy changes.

## Global Constraints

- Run all commands from `server/`. Tests: `APP_ENV=test uv run pytest <path> -q`. Baseline before Task 1: `tests/integration/modules/conversation tests/unit/modules/conversation` → **66 passed**.
- No behaviour change visible to a route, the `UserConversation` dependency or the `USER_ERASING` handler. `ConversationService`'s public method names, parameters and return types stay as they are (except the removed `delete_conversation`).
- `app/modules/conversation/__init__.py` does not export the repository. R1: only the module itself imports `.repository`.
- The repository is a stateless class of `@staticmethod async` methods plus a module-level `conversation_repository` singleton. `session: AsyncSession` is the first parameter.
- Writes end with `flush()` (+ `refresh()` for a returned row), never `commit()`.
- Logs are structured: `logger.info("snake_case_event", key=value)`. The existing event names move with the code unchanged.
- Comments: state the constraint in one or two lines, no narrative.
- Commit messages end with: `Claude-Session: https://claude.ai/code/session_01NFDrERAUYXLeBxBUSshgVA`

## Review Focus

1. **`get_by_id` must return soft-deleted rows.** `get_user_conversation` in `dependencies.py` does its own `deleted_at` check, turning a deleted conversation into 404. A "helpful" `deleted_at` filter in the repository would keep the tests green and silently make that check dead code. Pinned in Task 2.
2. **Blanking names must reach soft-deleted rows.** This is part of erasure: the name is free text and may hold PII. The active-rows query never loads those rows. Pinned in Task 2.
3. **Blanking must update rows already loaded in the session.** The bulk `UPDATE` replaces a load-and-mutate loop. If it doesn't synchronise the identity map, an object the handler's session already holds keeps its old name, and a later flush could write it back. Pinned in Task 2 (asserted without `refresh()`).
4. **The list order is a published contract.** `GET /conversations` returns `created_at` ascending, and the web client renders it in that order. Pinned in Task 2.
5. **User scoping.** Every per-user query filters on `user_id`, so one user's conversations never leak into another's list or erasure. Pinned in Task 2.

---

### Task 1: Remove the unused hard delete

`ConversationService.delete_conversation` issues a real `DELETE`. Nothing in `app/` calls it (the delete route soft-deletes), and it contradicts the soft-delete rule. Removing it first keeps it out of the repository.

**Files:**
- Modify: `server/app/modules/conversation/service.py` (delete the `delete_conversation` method, lines 128-137)
- Modify: `server/tests/integration/modules/conversation/test_service.py` (delete `class TestDeleteConversation`)

- [ ] **Step 1: Confirm there are no callers**

Run: `grep -rn "delete_conversation\b" app tests | grep -v "soft_delete\|checkpoints\|def delete_conversation\|TestDeleteConversation\|router/conversation.py"`
Expected: only the two `ConversationService.delete_conversation(` calls inside `TestDeleteConversation`. The route function in `router/conversation.py` is also named `delete_conversation`, but it's a separate function that soft-deletes. It stays.

- [ ] **Step 2: Delete the method and its test class**

Remove from `service.py`:

```python
    @staticmethod
    async def delete_conversation(session: AsyncSession, conversation_id: str) -> bool:
        """Hard-delete a conversation. False if there is no such conversation."""
        conversation = await session.get(Conversation, conversation_id)
        if not conversation:
            return False

        await session.delete(conversation)
        logger.info("conversation_deleted", conversation_id=conversation_id)
        return True
```

Remove from `test_service.py` the whole `class TestDeleteConversation:` block (both tests).

- [ ] **Step 3: Run the conversation tests**

Run: `APP_ENV=test uv run pytest tests/integration/modules/conversation tests/unit/modules/conversation -q`
Expected: **64 passed** (66 − 2).

- [ ] **Step 4: Commit**

```bash
git add app/modules/conversation/service.py tests/integration/modules/conversation/test_service.py
git commit -m "refactor(server): drop the unused conversation hard delete

Nothing called it, and conversations are soft-deleted.

Claude-Session: https://claude.ai/code/session_01NFDrERAUYXLeBxBUSshgVA"
```

---

### Task 2: Add `ConversationRepository`

**Files:**
- Create: `server/app/modules/conversation/repository.py`
- Test: `server/tests/integration/modules/conversation/test_repository.py` (R5: one test file per slot file)

**Interfaces:**
- Produces (Task 3 relies on these exact signatures):
  - `ConversationRepository.create(session: AsyncSession, conversation_id: str, user_id: str, name: str = "") -> Conversation`
  - `ConversationRepository.get_by_id(session: AsyncSession, conversation_id: str) -> Optional[Conversation]`. Includes soft-deleted rows.
  - `ConversationRepository.list_active_for_user(session: AsyncSession, user_id: str) -> List[Conversation]`. Ordered by `created_at` ascending.
  - `ConversationRepository.update_name(session: AsyncSession, conversation: Conversation, name: str) -> Conversation`
  - `ConversationRepository.soft_delete(session: AsyncSession, conversation_id: str) -> bool`
  - `ConversationRepository.soft_delete_active_for_user(session: AsyncSession, user_id: str) -> list[str]`
  - `ConversationRepository.blank_names_for_user(session: AsyncSession, user_id: str) -> int`. Returns the row count, soft-deleted rows included.
  - module singleton `conversation_repository = ConversationRepository()`

- [ ] **Step 1: Write the failing tests**

Create `server/tests/integration/modules/conversation/test_repository.py`:

```python
"""Integration tests for ConversationRepository — queries against the real test database."""

import uuid

import pytest

from app.modules.account.models import User
from app.modules.conversation.repository import ConversationRepository

pytestmark = pytest.mark.integration


@pytest.fixture
async def owner(db_session):
    """A user to own test conversations."""
    user = User(clerk_id="clerk_conv_repo_owner", org_id="test_org_123", email="conv_repo_owner@example.com")
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def other_user(db_session):
    """A second user, to prove per-user queries are scoped."""
    user = User(clerk_id="clerk_conv_repo_other", org_id="test_org_123", email="conv_repo_other@example.com")
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


async def _create(db_session, user_id, name=""):
    return await ConversationRepository.create(db_session, str(uuid.uuid4()), user_id, name=name)


class TestCreate:
    async def test_persists_the_row(self, db_session, owner):
        conv_id = str(uuid.uuid4())
        conv = await ConversationRepository.create(db_session, conv_id, owner.id, name="My Chat")
        assert (conv.id, conv.user_id, conv.name) == (conv_id, owner.id, "My Chat")
        assert conv.created_at is not None

    async def test_name_defaults_to_empty(self, db_session, owner):
        conv = await ConversationRepository.create(db_session, str(uuid.uuid4()), owner.id)
        assert conv.name == ""


class TestGetById:
    async def test_found(self, db_session, owner):
        conv = await _create(db_session, owner.id)
        assert (await ConversationRepository.get_by_id(db_session, conv.id)).id == conv.id

    async def test_missing_returns_none(self, db_session):
        assert await ConversationRepository.get_by_id(db_session, "nonexistent-conv-id") is None

    async def test_returns_soft_deleted_rows(self, db_session, owner):
        # get_user_conversation (dependencies.py) does its own deleted_at check.
        conv = await _create(db_session, owner.id)
        await ConversationRepository.soft_delete(db_session, conv.id)
        found = await ConversationRepository.get_by_id(db_session, conv.id)
        assert found is not None and found.deleted_at is not None


class TestListActiveForUser:
    async def test_oldest_first(self, db_session, owner):
        ids = [(await _create(db_session, owner.id, name=f"Chat {i}")).id for i in range(3)]
        result = await ConversationRepository.list_active_for_user(db_session, owner.id)
        assert [c.id for c in result] == ids

    async def test_excludes_soft_deleted(self, db_session, owner):
        kept = await _create(db_session, owner.id)
        gone = await _create(db_session, owner.id)
        await ConversationRepository.soft_delete(db_session, gone.id)
        result = await ConversationRepository.list_active_for_user(db_session, owner.id)
        assert [c.id for c in result] == [kept.id]

    async def test_scoped_to_user(self, db_session, owner, other_user):
        mine = await _create(db_session, owner.id)
        await _create(db_session, other_user.id)
        result = await ConversationRepository.list_active_for_user(db_session, owner.id)
        assert [c.id for c in result] == [mine.id]


class TestUpdateName:
    async def test_sets_the_name(self, db_session, owner):
        conv = await _create(db_session, owner.id, name="Old")
        updated = await ConversationRepository.update_name(db_session, conv, "New")
        assert updated.name == "New"
        assert (await ConversationRepository.get_by_id(db_session, conv.id)).name == "New"


class TestSoftDelete:
    async def test_stamps_deleted_at(self, db_session, owner):
        conv = await _create(db_session, owner.id)
        assert await ConversationRepository.soft_delete(db_session, conv.id) is True
        assert (await ConversationRepository.get_by_id(db_session, conv.id)).is_deleted is True

    async def test_missing_returns_false(self, db_session):
        assert await ConversationRepository.soft_delete(db_session, "nonexistent-conv-id") is False


class TestSoftDeleteActiveForUser:
    async def test_returns_only_rows_it_deleted(self, db_session, owner):
        active = await _create(db_session, owner.id)
        already = await _create(db_session, owner.id)
        await ConversationRepository.soft_delete(db_session, already.id)

        assert await ConversationRepository.soft_delete_active_for_user(db_session, owner.id) == [active.id]
        assert await ConversationRepository.list_active_for_user(db_session, owner.id) == []

    async def test_scoped_to_user(self, db_session, owner, other_user):
        theirs = await _create(db_session, other_user.id)
        await ConversationRepository.soft_delete_active_for_user(db_session, owner.id)
        assert [c.id for c in await ConversationRepository.list_active_for_user(db_session, other_user.id)] == [
            theirs.id
        ]

    async def test_nothing_active_returns_empty(self, db_session, owner):
        assert await ConversationRepository.soft_delete_active_for_user(db_session, owner.id) == []


class TestBlankNamesForUser:
    async def test_blanks_soft_deleted_rows_too(self, db_session, owner):
        kept = await _create(db_session, owner.id, name="Kept")
        gone = await _create(db_session, owner.id, name="Gone")
        await ConversationRepository.soft_delete(db_session, gone.id)

        assert await ConversationRepository.blank_names_for_user(db_session, owner.id) == 2
        # No refresh(): the objects already in the session must see the UPDATE.
        assert (kept.name, gone.name) == ("", "")

    async def test_scoped_to_user(self, db_session, owner, other_user):
        theirs = await _create(db_session, other_user.id, name="Theirs")
        await ConversationRepository.blank_names_for_user(db_session, owner.id)
        await db_session.refresh(theirs)
        assert theirs.name == "Theirs"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `APP_ENV=test uv run pytest tests/integration/modules/conversation/test_repository.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'app.modules.conversation.repository'`.

- [ ] **Step 3: Write the repository**

Create `server/app/modules/conversation/repository.py`:

```python
"""Conversation repository for database operations."""

from typing import (
    List,
    Optional,
)

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.logging import logger
from app.modules.conversation.models import Conversation


class ConversationRepository:
    """Repository for conversation database operations."""

    @staticmethod
    async def create(session: AsyncSession, conversation_id: str, user_id: str, name: str = "") -> Conversation:
        """Insert a new conversation row."""
        conversation = Conversation(id=conversation_id, user_id=user_id, name=name)
        session.add(conversation)
        await session.flush()
        await session.refresh(conversation)

        logger.info("conversation_created", conversation_id=conversation_id, user_id=user_id, name=name)
        return conversation

    @staticmethod
    async def get_by_id(session: AsyncSession, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by primary key, soft-deleted rows included.

        `get_user_conversation` in `dependencies.py` does its own `deleted_at` check.
        """
        return await session.get(Conversation, conversation_id)

    @staticmethod
    async def list_active_for_user(session: AsyncSession, user_id: str) -> List[Conversation]:
        """A user's non-soft-deleted conversations, oldest first — the order `GET /conversations` publishes."""
        statement = (
            select(Conversation)
            .where(Conversation.user_id == user_id, Conversation.deleted_at.is_(None))
            .order_by(Conversation.created_at)
        )
        result = await session.execute(statement)
        return list(result.scalars().all())

    @staticmethod
    async def update_name(session: AsyncSession, conversation: Conversation, name: str) -> Conversation:
        """Set a loaded conversation's name and flush it."""
        conversation.name = name
        session.add(conversation)
        await session.flush()
        await session.refresh(conversation)

        logger.info("conversation_name_updated", conversation_id=conversation.id, name=name)
        return conversation

    @staticmethod
    async def soft_delete(session: AsyncSession, conversation_id: str) -> bool:
        """Stamp deleted_at on one conversation. False if there is no such row."""
        conversation = await session.get(Conversation, conversation_id)
        if not conversation:
            return False

        conversation.soft_delete()
        session.add(conversation)
        await session.flush()

        logger.info("conversation_soft_deleted", conversation_id=conversation_id)
        return True

    @staticmethod
    async def soft_delete_active_for_user(session: AsyncSession, user_id: str) -> list[str]:
        """Soft-delete a user's active conversations and return their IDs. One flush for the set."""
        statement = select(Conversation).where(
            Conversation.user_id == user_id,
            Conversation.deleted_at.is_(None),
        )
        result = await session.execute(statement)
        conversations = result.scalars().all()

        for conv in conversations:
            conv.soft_delete()
            session.add(conv)

        await session.flush()

        conversation_ids = [conv.id for conv in conversations]
        logger.info("all_user_conversations_soft_deleted", user_id=user_id, count=len(conversation_ids))
        return conversation_ids

    @staticmethod
    async def blank_names_for_user(session: AsyncSession, user_id: str) -> int:
        """Clear the name on every conversation a user owns, soft-deleted included; return the row count.

        One UPDATE: the soft-deleted rows are ones no active-rows select loads.
        """
        result = await session.execute(update(Conversation).where(Conversation.user_id == user_id).values(name=""))
        logger.info("all_user_conversation_names_blanked", user_id=user_id, count=result.rowcount)
        return result.rowcount


conversation_repository = ConversationRepository()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `APP_ENV=test uv run pytest tests/integration/modules/conversation/test_repository.py -q`
Expected: **16 passed**.

If `test_blanks_soft_deleted_rows_too` fails on the in-session assertion, the ORM `UPDATE` didn't synchronise the identity map. Pass `.execution_options(synchronize_session="fetch")` on the statement. Don't add a `refresh()` to the test.

- [ ] **Step 5: Lint and check boundaries**

Run: `make -C .. check-server`
Expected: ruff and import-linter both pass. The R1 contracts already forbid `app.modules.conversation.*` from other modules, so no `pyproject.toml` change is needed.

- [ ] **Step 6: Commit**

```bash
git add app/modules/conversation/repository.py tests/integration/modules/conversation/test_repository.py
git commit -m "feat(server): add ConversationRepository

Holds every conversation query. Not wired into the service yet.

Claude-Session: https://claude.ai/code/session_01NFDrERAUYXLeBxBUSshgVA"
```

---

### Task 3: Delegate `ConversationService` to the repository

**Files:**
- Modify: `server/app/modules/conversation/service.py` (full rewrite, shown below)
- Test: `server/tests/integration/modules/conversation/test_service.py` (unchanged — the behaviour guard)
- Test: `server/tests/unit/modules/conversation/test_handlers.py` (unchanged — it patches service methods by name, which still exist)

**Interfaces:**
- Consumes: every `conversation_repository.*` method listed in Task 2.
- Produces: unchanged `ConversationService` surface — `create_conversation`, `get_conversation`, `get_user_conversations`, `update_conversation_name`, `soft_delete_conversation`, `soft_delete_all_user_conversations`, `blank_all_user_conversation_names`, plus the `conversation_service` singleton.

- [ ] **Step 1: Rewrite the service**

Replace `server/app/modules/conversation/service.py` with:

```python
"""Conversation management service."""

from typing import (
    List,
    Optional,
)

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.conversation.exceptions import ConversationNotFoundError
from app.modules.conversation.models import Conversation
from app.modules.conversation.repository import conversation_repository


class ConversationService:
    """Service for chat conversation management operations."""

    @staticmethod
    async def create_conversation(
        session: AsyncSession, conversation_id: str, user_id: str, name: str = ""
    ) -> Conversation:
        """Create a new chat conversation."""
        return await conversation_repository.create(session, conversation_id, user_id, name)

    @staticmethod
    async def get_conversation(session: AsyncSession, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID, soft-deleted included."""
        return await conversation_repository.get_by_id(session, conversation_id)

    @staticmethod
    async def get_user_conversations(session: AsyncSession, user_id: str) -> List[Conversation]:
        """Get a user's active conversations, oldest first."""
        return await conversation_repository.list_active_for_user(session, user_id)

    @staticmethod
    async def update_conversation_name(session: AsyncSession, conversation_id: str, name: str) -> Conversation:
        """Update a conversation's name.

        Raises ConversationNotFoundError if there is no such conversation.
        """
        conversation = await conversation_repository.get_by_id(session, conversation_id)
        if not conversation:
            raise ConversationNotFoundError(
                f"Conversation {conversation_id} not found", conversation_id=conversation_id
            )

        return await conversation_repository.update_name(session, conversation, name)

    @staticmethod
    async def soft_delete_conversation(session: AsyncSession, conversation_id: str) -> bool:
        """Soft-delete a conversation. False if there is no such conversation."""
        return await conversation_repository.soft_delete(session, conversation_id)

    @staticmethod
    async def soft_delete_all_user_conversations(session: AsyncSession, user_id: str) -> list[str]:
        """Soft-delete every active conversation for a user.

        Returns their IDs so the caller can clear each one's LangGraph
        checkpoint data.
        """
        return await conversation_repository.soft_delete_active_for_user(session, user_id)

    @staticmethod
    async def blank_all_user_conversation_names(session: AsyncSession, user_id: str) -> int:
        """Clear the name of every conversation a user owns, deleted or not.

        Part of erasure: a name is free text and may hold PII. Returns the
        number of rows touched.
        """
        return await conversation_repository.blank_names_for_user(session, user_id)


conversation_service = ConversationService()
```

- [ ] **Step 2: Verify the service no longer touches the session directly**

Run: `grep -nE "select\(|update\(|session\.(get|execute|add|flush|refresh|delete)" app/modules/conversation/service.py`
Expected: no output.

- [ ] **Step 3: Run the whole conversation suite**

Run: `APP_ENV=test uv run pytest tests/integration/modules/conversation tests/unit/modules/conversation -q`
Expected: **80 passed** (64 from Task 1 + 16 repository tests). No change to `test_service.py`, the router tests, the dependency tests or `test_handlers.py`.

- [ ] **Step 4: Run the full suite and the checks**

Run: `APP_ENV=test uv run pytest tests -q` then `make -C .. check-server`
Expected: all pass. The erasure tests under `tests/integration/modules/account/` exercise the handler → service → repository path end to end.

- [ ] **Step 5: Confirm the API contract did not move**

Run: `make -C .. check-contract`
Expected: pass with no diff. No route changed.

- [ ] **Step 6: Commit**

```bash
git add app/modules/conversation/service.py
git commit -m "refactor(server): route conversation service queries through the repository

The service no longer touches the session; behaviour is unchanged.

Claude-Session: https://claude.ai/code/session_01NFDrERAUYXLeBxBUSshgVA"
```
