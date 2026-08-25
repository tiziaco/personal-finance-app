# Client Wrapper Services (External API Adapters)

External API integrations split into two files in the same provider folder:

- **`client.py`** — the raw SDK/HTTP wrapper. Owns the SDK client instance, auth, base config, retries. Knows
  nothing about domain exceptions — it only translates transport-level failures (connection errors, timeouts) into a
  thin set of its own low-level errors, or lets SDK exceptions surface as-is.
- **`service.py`** — business orchestration. Calls `client.py`, translates its errors into the domain's
  `exceptions.py` hierarchy, adds logging, and is what the rest of the app actually imports and calls.

This mirrors the `repository.py` (DB access) / `service.py` (orchestration) split in `references/services.md` —
`client.py` is a repository, just for an external system instead of the database.

## Folder placement

**Default: its own top-level `app/services/<provider>/` folder**, a sibling of the domains that call it — e.g.
`app/services/clerk/`, called from `app/services/user/`. This is the default even if only one domain calls it today:
adapter code for an external system (auth edge cases, webhooks, admin tooling) tends to accrete over time and end up
needed by more than the domain that first introduced it.

**Nested exception**: if the adapter is provably scoped to a single domain and unlikely to be reused — e.g. Stripe
used only for payment checkout — it's fine to nest it as a sub-package of that domain instead:
`app/services/payment/stripe/` (its own `client.py` + `service.py` + `exceptions.py`, same internal structure as the
top-level case). The tradeoff: if it does get reused later (a separate `subscriptions/` domain also needs to charge
cards), moving it out to top-level is a bigger refactor than importing across folders would have been from the
start. Default to top-level unless you're confident this won't happen.

Either way, the `client.py`/`service.py` split and the rules below are identical — only the folder location changes.

## `client.py` — raw SDK wrapper

**Prefer the provider's official SDK when one exists** (Stripe → `stripe-python`, Clerk → `clerk-backend-api`, etc.)
— wrap that in `client.py`. Reach for a raw `httpx.AsyncClient` only when no official SDK exists, or the SDK doesn't
support async. Official SDKs already handle auth signing, retries, pagination, and typed models — rolling your own
`httpx` wrapper around them just reimplements that worse.

Use a **stateful class with instance methods** (not static) because it holds an initialized client. Use a lazy
`@property` so the client is created on first use, not at import time.

```python
# app/services/stripe/client.py

class StripeClient:
    """Owns the Stripe SDK client. No domain exception translation here —
    that's StripeService's job."""

    def __init__(self):
        self._client: Optional[_StripeSDKClient] = None

    @property
    def client(self) -> _StripeSDKClient:
        """Lazy-initialize the Stripe client on first use."""
        if self._client is None:
            self._client = _StripeSDKClient(api_key=settings.stripe.SECRET_KEY.get_secret_value())
        return self._client

    def get_customer(self, customer_id: str) -> StripeCustomer:
        return self.client.customers.retrieve(customer_id)

    def delete_customer(self, customer_id: str) -> None:
        self.client.customers.delete(customer_id)


stripe_client = StripeClient()
```

## `service.py` — orchestration + error translation

```python
# app/services/stripe/service.py

class StripeService:
    """Anti-corruption layer over StripeClient — the only thing other domains import."""

    def get_customer(self, customer_id: str) -> StripeCustomer:
        try:
            customer = stripe_client.get_customer(customer_id)
            logger.debug("stripe_customer_fetched", customer_id=customer_id)
            return customer

        except stripe.error.InvalidRequestError as e:
            if e.http_status == 404:
                logger.warning("stripe_customer_not_found", customer_id=customer_id)
                raise StripeCustomerNotFoundError(
                    f"Customer {customer_id} not found",
                    customer_id=customer_id,
                ) from e
            raise StripeAPIError(f"Stripe request error: {e}", customer_id=customer_id) from e

        except stripe.error.AuthenticationError as e:
            logger.error("stripe_authentication_failed")
            raise StripeAuthenticationError("Stripe authentication failed") from e

        except stripe.error.RateLimitError as e:
            logger.warning("stripe_rate_limit_exceeded", customer_id=customer_id)
            raise StripeRateLimitError("Stripe rate limit exceeded", customer_id=customer_id) from e

        except Exception as e:
            logger.exception("stripe_unexpected_error", customer_id=customer_id, error=str(e))
            raise StripeAPIError(f"Unexpected Stripe error: {e}", customer_id=customer_id) from e

    def delete_customer(self, customer_id: str) -> None:
        try:
            stripe_client.delete_customer(customer_id)
            logger.info("stripe_customer_deleted", customer_id=customer_id)
        except stripe.error.InvalidRequestError as e:
            if e.http_status == 404:
                return  # Already gone — idempotent delete, not an error
            raise StripeAPIError(f"Stripe request error: {e}", customer_id=customer_id) from e
        except Exception as e:
            logger.exception("stripe_unexpected_error_on_delete", customer_id=customer_id, error=str(e))
            raise StripeAPIError(f"Unexpected Stripe error: {e}", customer_id=customer_id) from e


stripe_service = StripeService()
```

Other domains (e.g. `PaymentService.checkout()` in `references/services.md`) import and call `stripe_service`, never
`stripe_client` directly — same rule as never bypassing a repository to call `db.execute()` from a service.

## Rules

- `client.py` holds the SDK instance and raw calls only — no domain exception mapping, no business logic
- `service.py` is the only thing other domains import — it calls `client.py` and translates every SDK/HTTP error
  into the domain's `exceptions.py` hierarchy
- `@property` for lazy client init on `client.py` — never instantiate SDK clients at module load time (config may
  not be ready)
- Instance methods, not `@staticmethod`, on both classes — they hold `_client` / no-state-but-still-instance
  patterns consistently; `service.py` stays a plain instance too for symmetry with `client.py`
- Always `raise ... from e` to preserve the original traceback
- Map each HTTP status code to a specific domain exception; fall through to the service's generic base exception
- Always include a bare `except Exception` as the last clause to prevent SDK internals from leaking
- **Idempotent deletes**: 404 on delete means "already gone" — return silently, don't raise
- Keep methods synchronous if the SDK is sync; use `asyncio.to_thread()` at the call site when calling from async
  code:

```python
# In an async service or provider:
clerk_user = await asyncio.to_thread(clerk_service.get_user, clerk_id)
```
