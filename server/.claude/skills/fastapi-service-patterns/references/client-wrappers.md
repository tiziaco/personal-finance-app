# Client Wrapper Services (External API Adapters)

When wrapping a third-party SDK or HTTP client, use a **stateful class with instance methods** (not static) because it holds an initialized client. Use a lazy `@property` so the client is created on first use, not at import time.

```python
# app/services/stripe/service.py

class StripeService:
    """Anti-corruption layer over the Stripe SDK."""

    def __init__(self):
        self._client: Optional[StripeClient] = None

    @property
    def client(self) -> StripeClient:
        """Lazy-initialize the Stripe client on first use."""
        if self._client is None:
            self._client = StripeClient(api_key=settings.stripe.SECRET_KEY.get_secret_value())
        return self._client

    def get_customer(self, customer_id: str) -> StripeCustomer:
        try:
            customer = self.client.customers.retrieve(customer_id)
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
            self.client.customers.delete(customer_id)
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

## Rules

- `@property` for lazy client init — never instantiate SDK clients at module load time (config may not be ready)
- Instance methods, not `@staticmethod` — the class holds `_client` state
- Always `raise ... from e` to preserve the original traceback
- Map each HTTP status code to a specific domain exception; fall through to the service's generic base exception
- Always include a bare `except Exception` as the last clause to prevent SDK internals from leaking
- **Idempotent deletes**: 404 on delete means "already gone" — return silently, don't raise
- Keep methods synchronous if the SDK is sync; use `asyncio.to_thread()` at the call site when calling from async code:

```python
# In an async service or provider:
clerk_user = await asyncio.to_thread(clerk_service.get_user, clerk_id)
```
