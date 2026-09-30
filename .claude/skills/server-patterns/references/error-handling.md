# Error Handling

## Fail Fast on Missing Resources

A route never receives `None`. The service raises when it needs the row to do its work, and the module's ownership
dependency raises when the resource is a path parameter (`references/api-routes.md`, **Ownership**). Repositories
return `Optional` and leave the decision to the layer above.

```python
# In a service
conversation = await conversation_repository.get_by_id(session, conversation_id)
if not conversation:
    raise ConversationNotFoundError(
        f"Conversation {conversation_id} not found",
        conversation_id=conversation_id,
    )
```

## Translating External API Errors

When calling third-party services, catch their low-level errors and translate them to domain exceptions. Always
`raise ... from e` to preserve the original traceback.

```python
try:
    result = external_client.do_something(resource_id)
except ExternalNotFoundError as e:
    raise DomainNotFoundError("...", resource_id=resource_id) from e
except ExternalRateLimitError as e:
    raise DomainRateLimitError("...", resource_id=resource_id) from e
except ExternalError as e:
    raise DomainAPIError(f"Unexpected error: {e}", resource_id=resource_id) from e
```

`app/integrations/clerk/client.py` is the real one.

## Retry with Exponential Backoff

For transient failures on external calls, use `tenacity`. `LLMService._call_llm_with_retry` in
`app/integrations/llm/service.py` is the real example, and the same file rotates through every configured model
before raising `LLMFallbackExhaustedError`.

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((RateLimitError, APITimeoutError)),
    before_sleep=before_sleep_log(logger, "WARNING"),
    reraise=True,
)
async def _call_with_retry(self, ...):
    ...
```

## Database Error Handling

See `references/database.md` for the full DB error handling and race condition patterns.
