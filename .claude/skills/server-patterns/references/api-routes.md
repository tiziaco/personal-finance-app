# API Routes

## Where a route lives

A module's routes are its `router` slot — one `router.py`, or a `router/` package with one file per tag and an
`__init__.py` that assembles them. Each route file's `APIRouter` carries its own prefix and tag; the package
assembles them bare, and `app/api/v1/api.py` mounts the module router:

```python
# app/modules/conversation/router/conversation.py
router = APIRouter(prefix="/conversation", tags=["conversation"])

# app/modules/conversation/router/__init__.py
router = APIRouter()
router.include_router(conversation_router)
router.include_router(chatbot_router)

# app/api/v1/api.py
api_router.include_router(conversation.router)
```

A module with no routes has no `router` slot and no line in `api.py` — `supplier` today. The system routes
(`app/api/system/health.py`, tag `system`) belong to no module and are mounted outside `/api/v1`.

## Dependencies

```python
from app.database.dependencies import DbSession
from app.modules.account import CurrentUser
from app.modules.conversation.dependencies import UserConversation  # from inside the module only
```

## Route structure

The real shape, from `app/modules/conversation/router/conversation.py`:

```python
router = APIRouter(prefix="/conversation", tags=["conversation"])


@router.post(
    "/conversation",
    operation_id="createConversation",
    response_model=ConversationResponse,
    summary="Create a new chat conversation",
    description="Initialize a new chat conversation for the authenticated user with a unique conversation ID.",
)
@limiter.limit(settings.rate_limits.endpoints.CHAT[0])
async def create_conversation(request: Request, db_session: DbSession, user: CurrentUser):
    conversation = await conversation_service.create_conversation(db_session, user.id)
    return ConversationResponse(
        conversation_id=conversation.id, name=conversation.name, created_at=conversation.created_at
    )


@router.patch(
    "/conversation/{conversation_id}/name",
    operation_id="renameConversation",
    response_model=ConversationResponse,
    summary="Rename a chat conversation",
    description="Update the display name of an existing chat conversation.",
)
@limiter.limit(settings.rate_limits.endpoints.CHAT[0])
async def update_conversation_name(
    request: Request,
    conversation: UserConversation,
    db_session: DbSession,
    name: str = Form(..., max_length=100),
):
    conversation = await conversation_service.update_conversation_name(
        db_session, conversation.id, name.replace("\0", "")
    )
    return ConversationResponse(
        conversation_id=conversation.id, name=conversation.name, created_at=conversation.created_at
    )
```

Rules:
- `operation_id`, `summary` and `description` on every decorator — see **The contract** below
- A route that carries a rate limit takes `@limiter.limit(settings.rate_limits.endpoints.<NAME>[0])` — a setting from
  `app/core/config.py`, never a literal — and then `request: Request` is its first parameter. There is no
  `SlowAPIMiddleware`, so an undecorated route is unlimited — today `GET /auth/me` and the webhook receiver (the
  latter deliberately, see `references/webhooks.md`)
- `db_session: DbSession` and `user: CurrentUser` come after path/body params
- Convert an ORM object with `model_validate` when the schema mirrors the model — `UserResponse.model_validate(user)`
  in `app/modules/account/router/auth.py`, with `model_config = {"from_attributes": True}` on the schema. Build the
  schema by hand when the field names differ, as `ConversationResponse` does
- Deletes: `status_code=204`, return type `-> None`, no response body

## Ownership

A path resource is resolved and authorised by the module's dependency, and the route receives the model, not the id:

```python
# app/modules/conversation/dependencies.py

async def get_user_conversation(
    user: CurrentUser,
    db_session: DbSession,
    conversation_id: uuid.UUID = Path(...),  # a malformed id is a 422 before any query
) -> Conversation:
    conversation = await conversation_service.get_conversation(db_session, conversation_id)

    if not conversation or conversation.deleted_at is not None:
        raise ConversationNotFoundError(f"Conversation {conversation_id} not found", conversation_id=conversation_id)
    if conversation.user_id != user.id:
        raise ConversationAccessDeniedError(..., conversation_id=conversation_id, user_id=user.id)

    return conversation


UserConversation = Annotated[Conversation, Depends(get_user_conversation)]
```

Not-found and access-denied are raised here, once, for every route on that resource. The route and the service never
re-check ownership. A new module with an owned resource writes the same dependency — `OrderOwner` in the `orders`
sketch of `docs/architecture/server.md` §2, which checks the caller's org rather than the user — and exports
it from its root only if another module's router needs it.

## The contract

`server/openapi.json` and the generated client under `web-app/packages/api-client/` are committed artifacts built
from the routes. `tests/unit/api/test_openapi_contract.py` enforces, on every operation:

- an explicit camelCase `operation_id` — it becomes the frontend hook name
- operation ids are unique
- a tag — from the route file's `APIRouter(tags=[...])`
- a `response_model`, or `status_code=204`
- no response schema that is an untyped object

After any route change run `make gen-contract`; the pre-commit hook regenerates and blocks the commit if the
artifacts moved. See **API Contract** in the root `CLAUDE.md`. A route that must not appear in the contract — the
webhook receiver — sets `include_in_schema=False`.

## Input validation

Bound every free-text input where it enters: `Form(..., max_length=100)` on the rename, `max_length=3000` on
`ChatRequest.message`. An over-long value is then a 422 and never reaches a row; a limit on the *response* model
instead turns a stored value into a 500 on every later read.

Store text as the member typed it. Escaping belongs to the renderer — JSON and React both escape on output — and at
the write layer it compounds on every edit. The one input-side change is dropping null bytes, which Postgres text
columns reject (`name.replace("\0", "")`). `sanitize_string` (`app/utils/sanitization.py`) is for identifiers, not
content; a `uuid.UUID` path parameter needs neither — FastAPI rejects a malformed id with a 422.

A validation failure raises a domain exception from the module's `exceptions.py` (the categories are in
`references/exceptions.md`) or is left to Pydantic. There is no `HTTPException` in a module.

## Pagination

Invented — no route paginates yet. Use offset/limit, plus `ordering` and `search` when the list sorts or searches.
Return an envelope with `items`, `total`, `offset`, `limit`. The web app's shared table (`@app/data-table`) is built
against exactly these names.

```python
PaymentOrdering = Literal["created_at", "-created_at", "amount", "-amount"]

class PaymentListResponse(BaseModel):
    items: List[PaymentResponse]
    total: int
    offset: int
    limit: int

@router.get("", operation_id="listPayments", response_model=PaymentListResponse, summary="List payments")
@limiter.limit(settings.rate_limits.endpoints.PAYMENTS[0])
async def list_payments(
    request: Request,
    db_session: DbSession,
    user: CurrentUser,
    filters: PaymentFilters = Depends(),
    ordering: Optional[PaymentOrdering] = Query(None),
    search: Optional[str] = Query(None, max_length=100),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),  # Always cap the max
) -> PaymentListResponse:
    payments, total = await payment_service.list(
        db_session, user.id, filters, ordering, search, offset, limit
    )
    return PaymentListResponse(
        items=[PaymentResponse.model_validate(p) for p in payments],
        total=total,
        offset=offset,
        limit=limit,
    )
```

- **`ordering`** is one field, `-` for descending — single-column sort only. It is a `Literal` allow-list per route,
  never a free string: OpenAPI then lists the sortable fields, orval generates them as a const, and an unknown field
  is a 422 instead of an `order_by` on whatever the client sent. The client's sortable column ids are these names.
- **`search`** is one free-text term the repository matches against named columns (`references/database.md`).
  Bounded like every free-text input.
- The client sends `limit` as its page size; any size up to the cap works.

Group filter query params into a `Depends()` class:

```python
class PaymentFilters(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    date_from: Optional[date] = Query(None)
    date_to: Optional[date] = Query(None)
    status: Optional[str] = Query(None)
```

## Batch operations

Invented. Named paths like `/batch` must be declared **before** `/{payment_id}` — otherwise FastAPI tries to parse
`"batch"` as an ID.

```python
class BatchDeleteRequest(BaseModel):
    ids: List[int] = Field(..., min_length=1, max_length=100)

class BatchDeleteResponse(BaseModel):
    deleted: int

# Declared before /{payment_id}
@router.delete("/batch", operation_id="batchDeletePayments", response_model=BatchDeleteResponse, summary="Delete payments")
@limiter.limit(settings.rate_limits.endpoints.PAYMENTS[0])
async def batch_delete_payments(
    request: Request,
    body: BatchDeleteRequest,
    db_session: DbSession,
    user: CurrentUser,
) -> BatchDeleteResponse:
    count = await payment_service.batch_delete(db_session, user.id, body.ids)
    return BatchDeleteResponse(deleted=count)
```

Batch operations are all-or-nothing: if any item fails, the entire batch rolls back — which the session dependency
already does for an exception.

## Response schemas

The real one, `app/modules/account/schemas.py`:

```python
class UserResponse(BaseModel):
    id: str = Field(..., description="Internal user ID (UUID)")
    clerk_id: str = Field(..., description="Clerk user ID")
    email: EmailStr = Field(..., description="User's email address")
    first_name: Optional[str] = Field(None, description="User's first name")
    last_name: Optional[str] = Field(None, description="User's last name")
    avatar_url: Optional[str] = Field(None, description="User's avatar URL")
    created_at: datetime = Field(..., description="Account creation timestamp")

    model_config = {"from_attributes": True}
```

Every field carries a `description`: it is published in `openapi.json` and in the generated client's types, so it is
part of the contract, not a comment.
