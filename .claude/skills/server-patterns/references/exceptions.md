# Exception Hierarchy

Exceptions follow a three-level hierarchy: base → category → domain-specific. The tree as it exists, with the file
that owns each branch:

```
ServiceError (500, INTERNAL_ERROR)                              app/exceptions/base.py
├── AuthenticationError (401)
│   ├── InvalidCredentialsError
│   └── InvalidWebhookSignatureError                            app/integrations/clerk/webhooks/exceptions.py
├── AuthorizationError (403)
│   ├── ConversationAccessDeniedError                           app/modules/conversation/exceptions.py
│   └── SupplierNotLinkedError                                  app/modules/supplier/exceptions.py
├── NotFoundError (404)
│   ├── ConversationNotFoundError                               app/modules/conversation/exceptions.py
│   └── ClerkUserNotFoundError                                  app/integrations/clerk/exceptions.py
├── ConflictError (409)
│   └── UserAlreadyExistsError                                  app/modules/account/exceptions.py
├── ValidationError (422)
├── DatabaseError (500)
│   ├── DatabaseConflictError (409)
│   └── DatabaseConnectionError (503)
├── ClerkServiceError (502)                                     app/integrations/clerk/exceptions.py
│   ├── ClerkAPIError
│   ├── ClerkAuthenticationError (401)
│   └── ClerkRateLimitError (429)
├── WebhookError (400)                                          app/integrations/clerk/webhooks/exceptions.py
│   └── WebhookPayloadTooLargeError (413)
└── LLMServiceError (503)                                       app/integrations/llm/exceptions.py
    ├── LLMRateLimitError
    ├── LLMTimeoutError
    ├── LLMStreamingError
    ├── LLMFallbackExhaustedError
    └── LLMAPIError
```

## Base class (`app/exceptions/base.py`)

```python
class ServiceError(Exception):
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, **context: Any):
        self.message = message
        self.context = context  # Merged into structured logs by the exception handler
        super().__init__(self.message)
```

## Domain exceptions (`app/modules/<name>/exceptions.py`)

The real file, `app/modules/conversation/exceptions.py`:

```python
class ConversationNotFoundError(NotFoundError):
    """Exception raised when a conversation is not found."""

    error_code = "CONVERSATION_NOT_FOUND"


class ConversationAccessDeniedError(AuthorizationError):
    """Exception raised when user attempts to access a conversation they don't own."""

    error_code = "CONVERSATION_ACCESS_DENIED"
```

Inheriting the category sets the status; the subclass sets only `error_code` and the docstring. Go direct to
`ServiceError` with an explicit `status_code` only when no category fits — a payment processor's upstream failure
would be `status_code = 502`.

## External service exceptions

Give each provider its own base class so callers can catch everything from that provider in one clause, and give
each HTTP status a subclass. A provider's not-found may instead inherit `NotFoundError` so it maps to 404 —
`ClerkUserNotFoundError` does — and then a caller that wants "any Clerk failure" catches both.

The real hierarchy is `app/integrations/clerk/exceptions.py` (above). An invented one, for a provider that does not
exist yet:

```python
# app/integrations/stripe/exceptions.py

class StripeServiceError(ServiceError):
    status_code = 502
    error_code = "STRIPE_ERROR"

class StripeCustomerNotFoundError(NotFoundError):
    error_code = "STRIPE_CUSTOMER_NOT_FOUND"

class StripeAuthenticationError(StripeServiceError):
    status_code = 401
    error_code = "STRIPE_AUTH_ERROR"

class StripeRateLimitError(StripeServiceError):
    status_code = 429
    error_code = "STRIPE_RATE_LIMIT"

class StripeAPIError(StripeServiceError):
    error_code = "STRIPE_API_ERROR"
```

Inbound webhook ingestion gets its own `exceptions.py` beside the outbound client's
(`app/integrations/clerk/webhooks/exceptions.py`) — see `references/webhooks.md`.

## Rules

- Every module and every provider gets its own `exceptions.py` file
- Always inherit from a category class (`NotFoundError`, `ConflictError`, `AuthorizationError`, …) — only go direct
  to `ServiceError` if no category fits
- `error_code` is always `SCREAMING_SNAKE_CASE`
- Pass context as kwargs to the constructor — the exception handler (`app/exceptions/handlers.py`) merges them into
  structured logs and the error response `details` field automatically:

```json
{
  "error": "CONVERSATION_NOT_FOUND",
  "message": "Conversation 42 not found",
  "correlation_id": "abc-123",
  "details": {"conversation_id": "42"}
}
```
