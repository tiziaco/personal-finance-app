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

## Retries and Fallback for Model Calls

Model calls do not hand-roll a retry. Transient failures retry inside the client: `chat_model` in
`app/integrations/llm/models.py` sets `max_retries`, and the SDK backs off exponentially. Past that:

- **Fallback to another model:** `with_fallbacks` for the one-call agents, title and summary (it catches
  `OpenAIError` only); inside the chat agent, `ModelFallbackMiddleware` (it catches any exception).
- **A typed error:** a provider error becomes an `LLMServiceError` subclass through `translate_error`.
- **An invalid answer:** `ask()` in `app/agents/core/structured.py` re-asks once.

For a retry on a non-LLM call, `tenacity` is not a direct dependency any more: adding one is a decision, not a
default. A bounded loop that logs each attempt with the structlog `logger` is enough for most cases.

## Database Error Handling

See `references/database.md` for the full DB error handling and race condition patterns.
