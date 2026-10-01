# Services and Repositories

Services are **stateless orchestrators**: they hold no state and no direct DB access. All database work lives in the
module's **repository** — the service calls it, plus any external API client wrappers (see
`references/client-wrappers.md`), and composes the result. Both are stateless classes with `@staticmethod async`
methods, each exporting a **module-level singleton**.

The reference pair is `app/modules/conversation/repository.py` and `app/modules/conversation/service.py`. Read them
whole — together they are under 200 lines. What follows is why each line is where it is.

## The repository owns persistence

```python
# app/modules/conversation/repository.py

class ConversationRepository:
    @staticmethod
    async def get_by_id(session: AsyncSession, conversation_id: uuid.UUID) -> Optional[Conversation]:
        """Returns soft-deleted rows too — the ownership dependency does its own check."""
        return await session.get(Conversation, conversation_id)

    @staticmethod
    async def update_name(session: AsyncSession, conversation: Conversation, name: str) -> Conversation:
        conversation.name = name
        session.add(conversation)
        await session.flush()
        await session.refresh(conversation)
        logger.info("conversation_name_updated", conversation_id=conversation.id, name=name)
        return conversation

    @staticmethod
    async def soft_delete_active_for_user(session: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
        statement = select(Conversation).where(Conversation.user_id == user_id, Conversation.deleted_at.is_(None))
        conversations = (await session.execute(statement)).scalars().all()
        for conv in conversations:
            conv.soft_delete()
            session.add(conv)
        await session.flush()  # one flush for the set, not one per row
        conversation_ids = [conv.id for conv in conversations]
        logger.info("all_user_conversations_soft_deleted", user_id=user_id, count=len(conversation_ids))
        return conversation_ids


conversation_repository = ConversationRepository()
```

Three things the repository owns and the service never touches:

- **The session.** Every `get`, `select`, `execute`, `add`, `flush`, `refresh` and `delete` is here. A service that
  calls one of them has a repository method missing.
- **The flush points.** `soft_delete_active_for_user` loads the set, stamps each row, and flushes once. Had the
  service looped over a single-row `soft_delete`, it would be N round trips where there is one.
- **The log events**: `conversation_created`, `conversation_name_updated`, `all_user_conversations_soft_deleted`.
  They say what happened to rows, so they sit where the rows are written.

`conv.soft_delete()` is `SoftDeleteMixin.soft_delete()` from `app/models/base.py`. It is called from the repository,
not the service, because whoever calls it must then `add` and `flush` — and that is session work.

## The service owns the decision

```python
# app/modules/conversation/service.py

class ConversationService:
    @staticmethod
    async def update_conversation_name(session: AsyncSession, conversation_id: uuid.UUID, name: str) -> Conversation:
        conversation = await conversation_repository.get_by_id(session, conversation_id)
        if not conversation:
            raise ConversationNotFoundError(f"Conversation {conversation_id} not found", conversation_id=conversation_id)
        return await conversation_repository.update_name(session, conversation, name)

    @staticmethod
    async def blank_all_user_conversation_names(session: AsyncSession, user_id: uuid.UUID) -> int:
        """Clear the name of every conversation a user owns, deleted or not.

        Part of erasure: a name is free text and may hold PII. Returns the
        number of rows touched.
        """
        return await conversation_repository.blank_names_for_user(session, user_id)


conversation_service = ConversationService()
```

The service decides *whether*: it holds the domain exception, and the docstring that says why a method exists —
`blank_all_user_conversation_names` is one repository call, and its docstring is the point: the GDPR reason reads
without a line of SQL in the way. *In what order* several such calls run is the caller's decision — for erasure,
the event handler (**Event subscribers**).

## Orchestrating multiple collaborators

A service is not limited to one repository. Its job is to coordinate whatever the flow needs — one or more
repositories, an external API client wrapper, a cache — and stay the only place that knows how they fit together.
Route handlers and repositories never call each other directly.

`UserService.resolve_user` (`app/modules/account/service.py`) is the real example: `user_repository.get_by_clerk_id`
first, and on a miss `clerk_client.get_user` (a sync SDK call, wrapped in `asyncio.to_thread`) followed by
`user_repository.create_or_get`. None of that DB or HTTP logic lives in the service itself.

## Event subscribers

A module reacting to something a *lower* module did subscribes in its `handlers.py` slot — when that is the right
tool, how to publish and subscribe, and which dispatch mode to pick are in `references/events.md`. For the service
layer, one thing: the handler owns the order of the steps and calls through the service singleton, never the
repository (`app/modules/conversation/handlers.py`).

## Rules

- Services orchestrate; they never call `session.get()`, `select()` or `session.execute()` — that lives in the repository
- A service may depend on more than one repository and/or external client wrapper — orchestration across
  collaborators is the point of the service layer
- Repositories never call other repositories, external clients, or any service — keep them one level below
- All methods (service and repository) are `@staticmethod` and `async` — no state on either class
- Parameter order: `session` first, then the domain params
- `flush()` + `refresh()` after DB writes — never `commit()`; the `get_db_session` dependency owns the transaction.
  `DbSession` is `scope="function"`, so the commit runs after the route returns and before the response is sent.
  No carve-outs
- A background task never receives the request's session: by the time a `BackgroundTasks` callable runs, that
  session is committed and closed. Pass it plain values; a task that needs the database opens its own from
  `request.app.state.session_factory`. The same holds for a `StreamingResponse` body
- Soft delete is `SoftDeleteMixin.soft_delete()`, called from the repository, which then adds and flushes. Never a
  `DELETE`, and never on personal data — that is anonymised (GDPR section of `server/CLAUDE.md`)
- Listing queries filter `deleted_at.is_(None)`. A by-id lookup feeding an ownership dependency returns the row as is
  and the dependency decides — see `references/database.md`
- A route never receives `None`: the service raises the domain exception, or the module's ownership dependency does.
  Repositories return `Optional`
- PATCH updates that take a body use `model_dump(exclude_unset=True)` — only write fields the caller actually sent
- Log events that say what happened to rows (`x_created`, `x_soft_deleted`) live in the repository; a service logs
  a decision it made. Structured key=value pairs, never f-strings
- Events: subscribe in `handlers.py`, pick inline or deferred on purpose — see `references/events.md`
