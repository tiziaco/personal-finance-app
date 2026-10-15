# PR #15 Review Round Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the three holes in "a 401 means credentials only", give 503s a category, and simplify the LLM fallback and the auth seam this PR wrote.

**Architecture:** Server first (exception category and the provisioning/middleware seam, then the verifier, then the LLM loop), then the web auth seam, then docs. Each task is one commit; gates run once at the end on the whole tree, plus each task's own tests as it goes.

**Tech Stack:** FastAPI, PyJWT 2.13, tenacity, LangChain/OpenAI SDK; Next.js, React 19, Clerk 5, Vitest.

**Spec:** `.superpowers/specs/2026-10-15-pr15-review-fixes.md`

## Global Constraints

- Work in `/Users/tizianoiacovelli/projects/personal-finance-app/.claude/worktrees/pre-wave-3`, branch `fix/pre-wave-3`; never `cd` outside it; never merge PR #15.
- Server tests: `cd server && APP_ENV=test uv run pytest <path> -q` (unit tests need `-m unit` only when running a directory; a file runs as is).
- Web tests: `make test-web` from the worktree root, or `cd web-app && pnpm vitest run <path>`.
- All Python imports at the top of the file, never inside a function (`server/CLAUDE.md`).
- No route or schema changes in this round, so `make check-contract` must report no drift; if it does, stop — something moved that should not have.
- Keep every existing `error_code` string unchanged.
- Commit messages: `Area: what changed` in the branch's existing style, ending with the `Co-Authored-By` attribution line used on earlier commits.

## Review Focus

- A user signed out in another tab who signs in again in the same document: `getToken` must wait for the new session, not answer at once from a stale "signed in" (pinned in Task 4).
- `CLERK_ISSUER` empty (`""`), not just a placeholder: the JWKS URL `/.well-known/jwks.json` also fails construction and must be a 503 (pinned in Task 2).
- A token minted 30 s ahead of the server clock must still be refused: leeway is 5 s, not "any" (pinned in Task 2).
- Every model failing with mixed error types: the typed error follows the *last* failure (pinned in Task 3).
- A database error during provisioning (untyped) must still be 503, not leak as a 500 (pinned by the existing `test_a_provisioning_failure_is_503_not_401`, kept green in Task 1).

---

### Task 1: Server — the 503 category, provisioning that keeps typed statuses, `auth_error` on the request

**Files:**
- Modify: `server/app/exceptions/base.py`
- Modify: `server/app/modules/account/exceptions.py`
- Modify: `server/app/integrations/llm/exceptions.py`
- Modify: `server/app/modules/transaction/imports/exceptions.py`
- Modify: `server/app/api/middlewares/auth.py`
- Modify: `server/app/modules/account/dependencies.py`
- Test: `server/tests/unit/exceptions/test_exceptions.py`
- Test: `server/tests/unit/middleware/test_auth_middleware.py`
- Test: `server/tests/integration/modules/account/router/test_auth.py`

**Interfaces:**
- Produces: `app.exceptions.base.ServiceUnavailableError` (503, `SERVICE_UNAVAILABLE`); `request.state.auth_error: AuthUnavailableError | None`, set by `AuthMiddleware` on every request.

- [ ] **Step 1: Write the failing tests**

In `server/tests/unit/exceptions/test_exceptions.py`, extend the import block and add at the end of the file:

```python
import app.main  # noqa: F401  imports every module, so every exception class is defined
from app.exceptions.base import (
    AuthUnavailableError,
    ServiceUnavailableError,
)
from app.integrations.clerk.webhooks.exceptions import InvalidWebhookSignatureError
from app.integrations.llm.exceptions import LLMServiceError
from app.modules.account.exceptions import UserProvisioningError
from app.modules.transaction.imports.exceptions import CategorisationUnavailableError
```

(Merge `AuthUnavailableError` and `ServiceUnavailableError` into the existing `from app.exceptions.base import (...)` block rather than a second one; keep imports sorted as ruff wants.)

```python
def _subclasses(cls: type) -> set[type]:
    found: set[type] = set()
    for sub in cls.__subclasses__():
        found |= {sub} | _subclasses(sub)
    return found


def test_only_credential_failures_answer_401():
    """The web signs out on a 401 that survives a retry, so a 401 must mean the caller's credentials."""
    in_app = {c for c in _subclasses(ServiceError) if c.__module__.startswith("app.")}
    assert {c for c in in_app if c.status_code == 401} == {
        AuthenticationError,
        InvalidCredentialsError,
        InvalidWebhookSignatureError,
    }


@pytest.mark.parametrize(
    "outage",
    [AuthUnavailableError, UserProvisioningError, LLMServiceError, CategorisationUnavailableError],
)
def test_outages_are_service_unavailable(outage):
    assert issubclass(outage, ServiceUnavailableError)
    assert outage.status_code == 503


def test_service_unavailable_is_503():
    err = ServiceUnavailableError("down")
    assert (err.status_code, err.error_code) == (503, "SERVICE_UNAVAILABLE")
```

In `server/tests/unit/middleware/test_auth_middleware.py`:
- add `from app.exceptions.base import AuthUnavailableError` to the top-level imports;
- in `_make_app`'s endpoint JSON add `"auth_error": repr(getattr(request.state, "auth_error", None)),`;
- in `test_org_claims_are_ignored` change the last assertion to `assert data["state_keys"] == ["auth_error", "clerk_id", "user_id"]`;
- replace `test_an_auth_outage_flags_the_request_and_still_passes_through` with:

```python
    @pytest.mark.asyncio
    @patch("app.api.middlewares.auth.clerk_jwt_verifier")
    async def test_an_auth_outage_is_kept_on_the_request_and_still_passes_through(self, mock_verifier, app):
        outage = AuthUnavailableError("jwks down")
        mock_verifier.verify_token.side_effect = outage

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/test", headers={"Authorization": "Bearer t"})

        data = response.json()
        assert response.status_code == 200
        assert data["clerk_id"] is None
        assert data["auth_error"] == repr(outage)

    @pytest.mark.asyncio
    async def test_auth_error_defaults_to_none(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/test")

        assert response.json()["auth_error"] == "None"
```

In `server/tests/integration/modules/account/router/test_auth.py`, add to the imports:

```python
from app.integrations.clerk import ClerkAuthenticationError, ClerkRateLimitError, ClerkUserNotFoundError
from app.modules.account.exceptions import UserAlreadyExistsError
```

and add to `TestGetMe`, after `test_a_provisioning_failure_is_503_not_401`:

```python
    @pytest.mark.parametrize(
        ("error", "status", "code"),
        [
            (ClerkAuthenticationError("secret refused"), 502, "CLERK_AUTH_ERROR"),
            (ClerkRateLimitError("slow down"), 429, "CLERK_RATE_LIMIT"),
            (UserAlreadyExistsError("email taken"), 409, "USER_ALREADY_EXISTS"),
        ],
    )
    @patch("app.api.middlewares.auth.clerk_jwt_verifier")
    async def test_a_typed_provisioning_error_keeps_its_status(self, mock_verifier, client, error, status, code):
        """Only an untyped failure becomes USER_PROVISIONING_FAILED; a typed one already says what happened."""
        mock_verifier.verify_token.return_value = {"sub": "clerk_typed_error"}

        with patch("app.modules.account.dependencies.user_service.resolve_user", side_effect=error):
            response = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer t"})

        assert response.status_code == status
        assert response.json()["error"] == code

    @patch(
        "app.modules.account.dependencies.user_service.resolve_user",
        side_effect=ClerkUserNotFoundError("gone"),
    )
    @patch("app.api.middlewares.auth.clerk_jwt_verifier")
    async def test_a_user_clerk_no_longer_has_is_401(self, mock_verifier, _resolve, client):
        """A valid token for a deleted user is a credentials failure: signing out is right."""
        mock_verifier.verify_token.return_value = {"sub": "clerk_deleted"}

        response = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer t"})

        assert response.status_code == 401
```

Also extend `test_a_jwks_outage_is_503_not_401` with `assert response.json()["message"] == "jwks unreachable"` (the verifier's own error now reaches the response).

- [ ] **Step 2: Run the tests to see them fail**

```bash
cd server && APP_ENV=test uv run pytest tests/unit/exceptions/test_exceptions.py tests/unit/middleware/test_auth_middleware.py -q
cd server && APP_ENV=test uv run pytest tests/integration/modules/account/router/test_auth.py -q
```

Expected: ImportError on `ServiceUnavailableError`; after that, failures on `auth_error`, the 502/429/409 cases (all 503 today), the 401 case (503 today) and the message assertion.

- [ ] **Step 3: Add the category**

In `server/app/exceptions/base.py`, insert this section between `ServiceError` and the `Authentication & Authorization Errors` banner:

```python
# ============================================================================
# Availability Errors
# ============================================================================


class ServiceUnavailableError(ServiceError):
    """We, or something we depend on, cannot serve the request now; a retry later may work.

    The category for an outage behind valid credentials. Never a 401: the web treats a
    401 that survives a retry as an ended session and signs out.
    """

    status_code = 503
    error_code = "SERVICE_UNAVAILABLE"
```

and replace `AuthUnavailableError` with:

```python
class AuthUnavailableError(ServiceUnavailableError):
    """The server could not check the request's credentials: Clerk's JWKS is unreachable or misconfigured."""

    error_code = "AUTH_UNAVAILABLE"
```

In `server/app/modules/account/exceptions.py`:

```python
"""User service domain exceptions."""

from app.exceptions.base import ConflictError, ServiceUnavailableError


class UserAlreadyExistsError(ConflictError):
    """Exception raised when attempting to create a user that already exists."""

    error_code = "USER_ALREADY_EXISTS"


class UserProvisioningError(ServiceUnavailableError):
    """The request's credentials were valid, but its user could not be resolved or created."""

    error_code = "USER_PROVISIONING_FAILED"
```

In `server/app/integrations/llm/exceptions.py`, change the import to `from app.exceptions.base import ServiceUnavailableError` and the base class to:

```python
class LLMServiceError(ServiceUnavailableError):
    """Base exception for LLM service errors."""

    error_code = "LLM_ERROR"
```

In `server/app/modules/transaction/imports/exceptions.py`, import `ServiceUnavailableError` from `app.exceptions.base` alongside what is imported there, and change:

```python
class CategorisationUnavailableError(ServiceUnavailableError):
    """Every labelling call failed; nothing was saved and the upload is still held."""

    error_code = "CATEGORISATION_UNAVAILABLE"
```

(If `ServiceError` is then unused in that file, drop it from the import.)

- [ ] **Step 4: Keep the error on the request**

In `server/app/api/middlewares/auth.py`, the class docstring's key list becomes:

```python
    Stores the following in request.state on every request:
      - clerk_id   : Clerk user ID (sub claim), or None
      - user_id    : None here; set to the internal UUID after user provisioning
      - auth_error : the AuthUnavailableError when the token could not be checked,
        else None; get_clerk_id raises it, so the answer is 503, not 401
```

(and drop the separate "Note: after user provisioning…" line it replaces). The reset block:

```python
        request.state.clerk_id = None
        request.state.user_id = None
        request.state.auth_error = None
```

and the handler:

```python
            except AuthUnavailableError as e:
                # Permissive, like everything here: kept for get_clerk_id, which raises it.
                request.state.auth_error = e
                logger.error("auth_unavailable_in_middleware", error=str(e), path=request.url.path)
```

- [ ] **Step 5: Raise it, and keep typed provisioning errors**

In `server/app/modules/account/dependencies.py`, the imports become:

```python
from app.exceptions.base import AuthenticationError, ServiceError
from app.integrations.clerk import ClerkUserNotFoundError
from app.modules.account.exceptions import UserProvisioningError
```

and the two functions:

```python
def get_clerk_id(request: Request) -> str:
    """The caller's Clerk id, set on request.state by AuthMiddleware.

    None is a 401, unless the middleware could not check the token: then the
    AuthUnavailableError it kept is raised instead, a 503.
    """
    clerk_id = getattr(request.state, "clerk_id", None)
    if clerk_id:
        return clerk_id
    auth_error = getattr(request.state, "auth_error", None)
    if auth_error:
        raise auth_error
    logger.error("clerk_id_not_in_request_state")
    raise AuthenticationError("Authentication required")


async def get_current_user(
    request: Request,
    session: DbSession,
    clerk_id: str = Depends(get_clerk_id),
    _token: str = Depends(oauth2_scheme),
) -> User:
    """Get the current authenticated user with JIT provisioning.

    A typed error keeps its status (a refused Clerk secret is 502, a rate limit 429);
    only an untyped failure becomes UserProvisioningError, a 503.
    """
    try:
        user = await user_service.resolve_user(session, clerk_id)
    except ClerkUserNotFoundError as e:
        # A valid token for a user Clerk no longer has: deleted since it was issued.
        raise AuthenticationError("User no longer exists") from e
    except ServiceError:
        raise
    except Exception as e:
        logger.error("user_provisioning_failed", clerk_id=clerk_id, error=str(e))
        raise UserProvisioningError("Failed to provision user") from e
    request.state.user_id = user.id
    bind_context(user_id=user.id)
    return user
```

- [ ] **Step 6: Run the tests to see them pass, and the import contracts**

```bash
cd server && APP_ENV=test uv run pytest tests/unit/exceptions tests/unit/middleware tests/unit/integrations/clerk -q
cd server && APP_ENV=test uv run pytest tests/integration/modules/account -q
cd server && uv run lint-imports
```

Expected: all pass; `lint-imports` reports every contract kept (`account` already imports `app.integrations.clerk` in its service).

- [ ] **Step 7: Commit**

```bash
git add server/app/exceptions/base.py server/app/modules/account server/app/integrations/llm/exceptions.py \
  server/app/modules/transaction/imports/exceptions.py server/app/api/middlewares/auth.py \
  server/tests/unit/exceptions/test_exceptions.py server/tests/unit/middleware/test_auth_middleware.py \
  server/tests/integration/modules/account/router/test_auth.py
git commit -m "Server: a 503 category; provisioning keeps a typed error's status; the auth outage rides on the request"
```

---

### Task 2: Server — a JWKS client that cannot be built is an outage; 5 s of clock skew

**Files:**
- Modify: `server/app/utils/auth.py`
- Test: `server/tests/unit/utils/test_auth_rs256_verification.py`

**Interfaces:**
- Consumes: `AuthUnavailableError` (Task 1, unchanged import path `app.exceptions.base`).
- Produces: `app.utils.auth.CLOCK_SKEW_SECONDS = 5`.

- [ ] **Step 1: Write the failing tests**

In `server/tests/unit/utils/test_auth_rs256_verification.py`: add `from app.exceptions.base import AuthUnavailableError` to the top-level imports and delete the two function-local copies of that import. Then add:

```python
@pytest.mark.parametrize("issuer", ["change-me", ""])
def test_an_issuer_that_is_not_a_url_is_an_outage_not_a_bad_token(keypair, monkeypatch, issuer):
    """PyJWKClient refuses a JWKS URL without http(s) when it is built: our configuration, not the token."""
    private, _ = keypair
    monkeypatch.setattr(settings.auth, "ISSUER", issuer)

    with pytest.raises(AuthUnavailableError):
        ClerkJWTVerifier().verify_token(_sign(private))


def test_a_token_minted_a_moment_ahead_of_our_clock_verifies(keypair):
    """A server clock a few seconds behind Clerk's must not refuse a token Clerk just minted."""
    private, public = keypair
    soon = int(time.time()) + 3

    assert _verifier_serving(public).verify_token(_sign(private, iat=soon, nbf=soon)) is not None


def test_a_token_far_ahead_of_our_clock_is_still_refused(keypair):
    private, public = keypair
    later = int(time.time()) + 30

    assert _verifier_serving(public).verify_token(_sign(private, iat=later, nbf=later)) is None
```

- [ ] **Step 2: Run them to see the first two fail**

```bash
cd server && APP_ENV=test uv run pytest tests/unit/utils/test_auth_rs256_verification.py -q
```

Expected: the issuer cases return `None` instead of raising; the "a moment ahead" case returns `None`; "far ahead" already passes.

- [ ] **Step 3: Implement**

In `server/app/utils/auth.py`, after the imports:

```python
# Clerk's backend SDK allows 5 s. Without it a server clock behind Clerk's refuses a token
# Clerk has just minted (iat/nbf ahead of us), the web's forced-refresh retry mints another
# that is refused the same way, and the user is signed out.
CLOCK_SKEW_SECONDS = 5
```

In `verify_token`, before the existing `try`:

```python
        try:
            jwks_client = self.jwks_client
        except jwt.PyJWKClientError as e:
            # Raised while building the client: CLERK_ISSUER is not an http(s) URL.
            logger.error("token_jwks_client_invalid", jwks_url=settings.auth.jwks_url, error=str(e))
            raise AuthUnavailableError("The signing-key service is misconfigured") from e
```

In the existing `try`, use `jwks_client.get_signing_key_from_jwt(token)` instead of `self.jwks_client…`, and add `leeway=CLOCK_SKEW_SECONDS,` to `jwt.decode(...)` after `issuer=…`. Update the docstring's `Raises:` to `AuthUnavailableError: the token could not be checked (JWKS unreachable or misconfigured, or an unexpected failure) -- not the caller's fault.` Change the `PyJWKClientError` comment to `# The key lookup found no key for this token's kid: the token is wrong, not the service.`

- [ ] **Step 4: Run the verifier and middleware tests**

```bash
cd server && APP_ENV=test uv run pytest tests/unit/utils tests/unit/middleware -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add server/app/utils/auth.py server/tests/unit/utils/test_auth_rs256_verification.py
git commit -m "Server: an unbuildable JWKS client is 503, not a bad token; allow 5 s of clock skew"
```

---

### Task 3: Server — the LLM fallback as one loop; one structured-call service

**Files:**
- Modify: `server/app/integrations/llm/service.py`
- Modify: `server/app/integrations/llm/exceptions.py`
- Modify: `server/app/integrations/llm/__init__.py`
- Modify: `server/app/agents/shared/structured.py`
- Modify: `server/app/agents/csv_mapping/mapper.py`
- Modify: `server/app/agents/transaction_labeler/labeler.py`
- Modify: `server/app/exceptions/handlers.py` (comment only)
- Test: `server/tests/unit/integrations/llm/test_service.py`

**Interfaces:**
- Consumes: `LLMServiceError` now under `ServiceUnavailableError` (Task 1); no behavioural dependency.
- Produces: `app.agents.shared.structured.structured_llm_service: LLMService`; `ask_json(service, system, user, shape, config)` unchanged.

- [ ] **Step 1: Rewrite the rotation tests against `call`**

In `server/tests/unit/integrations/llm/test_service.py`:
- remove `LLMFallbackExhaustedError` from the imports;
- rename `test_pinned_model_restored_when_the_call_raises` to `test_an_escaping_error_leaves_the_service_unchanged`;
- delete `class TestLLMServiceNextModel` and add to `TestLLMServiceCall`:

```python
    @pytest.mark.asyncio
    async def test_fallback_wraps_to_the_first_model(self, messages):
        names = LLMRegistry.get_all_names()
        service = LLMService()
        fakes = {n: _FakeModel(n, [], healthy=n != names[-1]) for n in names}

        with patch.object(service, "_resolve", side_effect=lambda name, **kw: fakes[name]):
            answer = await service.call(messages, model_name=names[-1])

        assert answer.content == names[0]

    @pytest.mark.asyncio
    async def test_a_fallback_model_keeps_the_tools(self, messages):
        """A fallback must not drop the tools: the graph routes on `tool_calls`, so a toolless model fails silently."""
        service = LLMService().bind_tools([echo])
        seen = []

        async def fail_first(llm, msgs, config=None):
            seen.append(llm)
            if len(seen) == 1:
                raise OpenAIError("down")
            return AIMessage(content="ok")

        with patch.object(service, "_call_llm_with_retry", side_effect=fail_first):
            await service.call(messages)

        assert isinstance(seen[1], RunnableBinding)
        assert _bound_tool_names(seen[1]) == ["echo"]

    @pytest.mark.asyncio
    async def test_the_typed_error_follows_the_last_failure(self, messages):
        service = LLMService()
        calls = 0

        async def rate_limit_then_api_error(llm, msgs, config=None):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RateLimitError(message="rate limited", response=MagicMock(status_code=429, headers={}), body=None)
            raise APIError(message="server error", request=MagicMock(), body=None)

        with patch.object(service, "_call_llm_with_retry", side_effect=rate_limit_then_api_error):
            with pytest.raises(LLMAPIError):
                await service.call(messages)
```

`_FakeModel` is defined further down the file; Python resolves it at call time, so the order is fine.

- [ ] **Step 2: Run them (the new ones pass on the old loop too — they pin behaviour the rewrite must keep)**

```bash
cd server && APP_ENV=test uv run pytest tests/unit/integrations/llm/test_service.py -q
```

Expected: all pass.

- [ ] **Step 3: Replace the loop**

In `server/app/integrations/llm/service.py`:
- remove `LLMFallbackExhaustedError` from the exceptions import;
- after the imports, add:

```python
# Once every model has failed, the error raised follows the last failure; anything not
# listed is an LLMAPIError.
_EXHAUSTED_AS: tuple[tuple[type[OpenAIError], type[LLMServiceError]], ...] = (
    (RateLimitError, LLMRateLimitError),
    (APITimeoutError, LLMTimeoutError),
)
```

(import `LLMServiceError` from `app.integrations.llm.exceptions` with the others);
- delete `_next`;
- `_resolve`'s docstring first paragraph becomes `Every client the service calls is built here.` (keep the rest, replacing "for `_next`, which moves to another model" with "for a fallback, which moves to another model");
- in `call`'s docstring, `Raises:` loses the `LLMFallbackExhaustedError` line and gains `LLMServiceError: every model failed after retries (see _call_with_fallback).`;
- replace `_call_with_fallback` with:

```python
    async def _call_with_fallback(
        self,
        messages: List[BaseMessage],
        config: Optional[RunnableConfig],
        start_index: int,
        start_llm: BaseChatModel,
    ) -> BaseMessage:
        """Call the model at `start_index`, then each next one in the registry, wrapping, until one answers.

        The position is in locals. Calls run at once on one service, so a position kept
        on the service would be moved by every call's failures, and a call could use up
        its attempts without reaching a healthy model.

        Raises:
            LLMRateLimitError: every model failed, the last with a rate limit
            LLMTimeoutError: every model failed, the last with a timeout
            LLMAPIError: every model failed, the last with any other error
        """
        names = LLMRegistry.get_all_names()
        last_error: Optional[OpenAIError] = None
        for offset in range(len(names)):
            index = (start_index + offset) % len(names)
            llm = start_llm if offset == 0 else self._resolve(names[index])
            try:
                return await self._call_llm_with_retry(llm, messages, config)
            except OpenAIError as e:
                last_error = e
                logger.error(
                    "llm_model_failed_after_retries",
                    model=names[index],
                    models_tried=offset + 1,
                    total_models=len(names),
                    error_type=type(e).__name__,
                    error=str(e),
                )

        error = next((typed for raw, typed in _EXHAUSTED_AS if isinstance(last_error, raw)), LLMAPIError)
        raise error(
            f"All {len(names)} models failed; the last with {type(last_error).__name__}",
            models_tried=len(names),
            starting_model=names[start_index],
            error_type=type(last_error).__name__,
        ) from last_error
```

In `server/app/integrations/llm/exceptions.py` delete `LLMFallbackExhaustedError`; in `server/app/integrations/llm/__init__.py` remove it from the import and `__all__`.

In `server/app/exceptions/handlers.py`, the comment's "five distinct causes — rate limit, timeout, streaming, fallback exhausted, generic API error" becomes "four distinct causes — rate limit, timeout, streaming, generic API error".

- [ ] **Step 4: One structured-call service**

In `server/app/agents/shared/structured.py`, replace the `structured_llm()` function with:

```python
# Tool-less: the chatbot's `llm_service` has tools bound, and an answer here must never be
# a tool call. Builds no client until the first call, so importing it needs no API key.
structured_llm_service = LLMService()
```

In `server/app/agents/csv_mapping/mapper.py` and `server/app/agents/transaction_labeler/labeler.py`, import `structured_llm_service` instead of `structured_llm`; the mapper passes `structured_llm_service` to `ask_json`, and the labeler's `service = structured_llm()` line is deleted and `_label_batch(service, …)` becomes `_label_batch(structured_llm_service, …)`.

- [ ] **Step 5: Run the LLM and agent tests, and grep for leftovers**

```bash
cd server && APP_ENV=test uv run pytest tests/unit/integrations/llm tests/unit/agents -q
cd server && grep -rn "LLMFallbackExhausted\|_next(\|structured_llm()" app tests
```

Expected: tests pass; grep prints nothing.

- [ ] **Step 6: Commit**

```bash
git add server/app/integrations/llm server/app/agents server/app/exceptions/handlers.py server/tests/unit/integrations/llm/test_service.py
git commit -m "LLMService: the fallback is one loop; the structured calls share one service"
```

---

### Task 4: Web — the session wait as a hook; `@app/auth` exports only what is used

**Files:**
- Modify: `web-app/packages/auth/src/provider.tsx`
- Modify: `web-app/packages/auth/src/index.ts`
- Modify: `web-app/packages/api-client/src/use-api-fetch.ts` (comment only)
- Test: `web-app/packages/auth/src/provider.test.tsx`
- Test: `web-app/apps/web/src/lib/first-query-after-sign-in.test.tsx`

**Interfaces:**
- Produces: `useAppAuth()` returns `{ user, isLoaded, getToken, signOut }`; `getToken(options?: { forceRefresh?: boolean })` unchanged. `SESSION_WAIT_MS` stays exported from `./provider` (tests), not from the package.

- [ ] **Step 1: Pin the re-armed wait, drop the `isSignedIn` test**

In `web-app/packages/auth/src/provider.test.tsx`, replace `it("reports whether Clerk has a session", …)` with:

```tsx
  // Signed out from another tab, then signed in again without a document load.
  it("waits again once the session has ended", async () => {
    const { result, rerender } = renderAuthHook()
    clerk.isSignedIn = false
    rerender()
    clerk.getToken.mockResolvedValue(null)

    let token: string | null | undefined
    const pending = result.current.getToken().then((t) => (token = t))
    await flush()
    expect(token).toBeUndefined()

    clerk.isSignedIn = true
    clerk.getToken.mockResolvedValue("again")
    rerender()
    await pending
    expect(token).toBe("again")
  })

  it("exposes no session flag: getToken is the only way to the session", () => {
    expect(renderAuth().current).not.toHaveProperty("isSignedIn")
  })
```

In `web-app/apps/web/src/lib/first-query-after-sign-in.test.tsx`:
- the comment's first line becomes `// The sign-in race (docs/architecture/authentication.md §2): the first page after sign-in.`
- the hoisted mock gains `getToken: vi.fn(async (): Promise<string | null> => null),` and `useAuth` returns `getToken: clerk.getToken`; delete the `token` field and use `clerk.getToken.mockResolvedValue(...)` instead (`mockResolvedValue(null)` in `beforeEach`, after `clerk.getToken.mockClear()`);
- the opening of the test becomes:

```tsx
  const { rerender } = render(<App />)
  // The query has asked for a token and is waiting for the session.
  await vi.waitFor(() => expect(clerk.getToken).toHaveBeenCalled())
  await new Promise((resolve) => setTimeout(resolve, 0))
  expect(globalThis.fetch).not.toHaveBeenCalled()

  clerk.isSignedIn = true
  clerk.getToken.mockResolvedValue("jwt-after-sign-in")
  rerender(<App />)
```

(the rest of the test unchanged).

- [ ] **Step 2: Run them; the `isSignedIn` assertion fails**

```bash
cd web-app && pnpm vitest run packages/auth/src/provider.test.tsx apps/web/src/lib/first-query-after-sign-in.test.tsx
```

Expected: "exposes no session flag" fails; the rest pass.

- [ ] **Step 3: Extract the hook, shrink the context**

In `web-app/packages/auth/src/provider.tsx`:
- `GetTokenOptions` loses `export`;
- `AuthContextValue` loses the `isSignedIn` field and its doc comment; the default context value loses `isSignedIn: false`; the provider value becomes `{{ user, isLoaded, getToken, signOut }}`;
- replace the `sessionArrives` function with:

```tsx
/**
 * A function answering true once Clerk reports a session, or false after
 * SESSION_WAIT_MS. Straight after sign-in the session trails the navigation, and
 * the first render's requests ask for a token inside that gap. It reads the
 * session through a ref because getToken outlives the render that made it.
 */
function useSessionWait(isSignedIn: boolean): () => Promise<boolean> {
  const signedIn = useRef(isSignedIn)
  const waiters = useRef(new Set<() => void>())
  useEffect(() => {
    signedIn.current = isSignedIn
    if (!isSignedIn) return
    for (const wake of waiters.current) wake()
    waiters.current.clear()
  }, [isSignedIn])

  return useCallback(() => {
    if (signedIn.current) return Promise.resolve(true)
    return new Promise<boolean>((resolve) => {
      const wake = () => {
        clearTimeout(timer)
        resolve(true)
      }
      const timer = setTimeout(() => {
        waiters.current.delete(wake)
        resolve(false)
      }, SESSION_WAIT_MS)
      waiters.current.add(wake)
    })
  }, [])
}
```

- in `AuthProvider`, delete the `signedIn`/`waiters` refs, their effect and the comment above them; after `const { user: clerkUser } = useUser()` add `const waitForSession = useSessionWait(isSignedIn)`; and `getToken` becomes:

```tsx
  const getToken = useCallback(
    async ({ forceRefresh = false }: GetTokenOptions = {}) => {
      const ask = () =>
        clerkGetToken(forceRefresh ? { skipCache: true } : undefined)
      const token = await ask()
      if (token || forceRefresh) return token
      return (await waitForSession()) ? ask() : null
    },
    [clerkGetToken, waitForSession],
  )
```

In `web-app/packages/auth/src/index.ts`:

```ts
export { AuthProvider, useAppAuth, type AppUser } from "./provider"
```

In `web-app/packages/api-client/src/use-api-fetch.ts`, the `useApiRequest` doc comment loses the sentence "A forced token refresh does not wait for a session: the first call already did." so that its last line reads `(an outage is a 503), so an outage never signs anyone out. The ApiError still reaches the caller.` reflowed under 100 columns.

- [ ] **Step 4: Run the web tests and checks**

```bash
make test-web
make check-web
```

Expected: all tests pass (the earlier 396 minus 1 plus 2); ESLint, Prettier and `tsc` clean. If `tsc` reports a consumer of `isSignedIn`, `SESSION_WAIT_MS` or `GetTokenOptions` outside `packages/auth`, stop and report it: the review found none.

- [ ] **Step 5: Commit**

```bash
git add web-app/packages/auth web-app/packages/api-client/src/use-api-fetch.ts web-app/apps/web/src/lib/first-query-after-sign-in.test.tsx
git commit -m "Auth: the session wait is a hook; the seam exports only what is used"
```

---

### Task 5: Docs follow the code

**Files:**
- Modify: `docs/architecture/server.md` (§7, around lines 278–300)
- Modify: `docs/setup/clerk.md` (Symptom → cause table)
- Modify: `docs/architecture/authentication.md` (§2)
- Modify: `docs/architecture/web-app.md` (the `useAppAuth()` table)
- Modify: `docs/guides/api-client-codegen.md` (§6.1)
- Modify: `docs/TODO.md`
- Modify: `.claude/skills/server-patterns/references/exceptions.md`, `.claude/skills/server-patterns/references/error-handling.md`
- Modify: `server/app/modules/transaction/domain/dates.py` (comment only)

- [ ] **Step 1: `server.md` §7.** The table's last row becomes
  `| `ServiceUnavailableError` — under it `AuthUnavailableError`, `UserProvisioningError`, `LLMServiceError`, `CategorisationUnavailableError` — and `DatabaseConnectionError` | 503 |`.
  The paragraph after it becomes:

  > **A 401 means the request's credentials, nothing else.** The web retries a 401 once with
  > a fresh token and signs out on the second ([`web-app.md`](./web-app.md) §5), so a failure
  > behind valid credentials is never a 401: an outage is a `ServiceUnavailableError` (503).
  > The server unable to check a token — Clerk's signing keys unreachable, `CLERK_ISSUER`
  > not a URL, an unexpected failure — is `AuthUnavailableError` (`AUTH_UNAVAILABLE`).
  > Provisioning lets a typed error keep its status (the server's own Clerk secret refused
  > is `ClerkAuthenticationError`, 502; a Clerk rate limit 429) and wraps anything else in
  > `UserProvisioningError` (`USER_PROVISIONING_FAILED`). A valid token for a user Clerk no
  > longer has is a 401. `tests/unit/exceptions/test_exceptions.py` fails if any other
  > exception answers 401.

- [ ] **Step 2: `clerk.md` symptom table.** The `AUTH_UNAVAILABLE` row becomes:

  `| Every request fails with 503 `AUTH_UNAVAILABLE`, and you are not signed out | The server cannot check tokens. Server log `token_jwks_client_invalid`: `CLERK_ISSUER` is not an `https://` URL (§3). Server log `token_jwks_unreachable`: Clerk's JWKS endpoint cannot be reached (network, or a well-formed but wrong issuer). |`

  and add after it:

  `| You sign in and are sent straight back to `/sign-in`; the server log shows `token_verification_failed` with "The token is not yet valid" | The API host's clock is more than 5 s behind Clerk's. Resync it (Docker Desktop: restart it after the laptop has slept). |`

- [ ] **Step 3: `authentication.md` §2.** "PyJWT also checks `nbf` and `iat`;" becomes "PyJWT also checks `nbf` and `iat`, allowing 5 s of clock skew (`CLOCK_SKEW_SECONDS`, `app/utils/auth.py`);".

- [ ] **Step 4: `web-app.md`.** Delete the `isSignedIn` row of the `useAppAuth()` table.

- [ ] **Step 5: codegen guide §6.1.** Replace the guide's `useApiRequest` doc comment and function (from the `/**` above `export function useApiRequest` to its closing `}`) with the same span copied verbatim from `web-app/packages/api-client/src/use-api-fetch.ts` as it stands after Task 4. Check with `diff <(sed -n '/^\/\*\*$/,/^}$/p' …)` or by eye that the two spans match.

- [ ] **Step 6: `TODO.md`.** After the "the chatbot names the default model after a fallback" section, add:

  ```markdown
  ## Server — every LLM call starts at the default model

  Each call walks the registry from the default model, so while the default is down every
  chat turn and labelling batch spends its retries there first (three attempts, 2 s and 4 s
  apart) before falling back. It is the cost of keeping the position per call, which
  concurrent calls need (15 Oct 2026). If it matters, keep a short-lived "last model that
  answered" hint on the service and start unpinned calls there.
  ```

- [ ] **Step 7: The `server-patterns` skill.** In `references/exceptions.md`'s tree: add `ServiceUnavailableError (503)` under `ServiceError` with `AuthUnavailableError`, `UserProvisioningError` (`app/modules/account/exceptions.py`), `CategorisationUnavailableError` (`app/modules/transaction/imports/exceptions.py`) and `LLMServiceError` with its four remaining children beneath it; delete `LLMFallbackExhaustedError`; fix `ClerkAuthenticationError (401)` to `(502)`. Match the file's existing tree drawing and path column. In `references/error-handling.md`, "before raising `LLMFallbackExhaustedError`" becomes "before raising a typed `LLMServiceError` for the last failure".

- [ ] **Step 8: `dates.py`.** The comment becomes `# The dates analytics covers. A row outside them would be left out of every analysis.` (the 422 rule is analytics', beside `get_date_range`).

- [ ] **Step 9: Commit**

```bash
git add docs .claude/skills/server-patterns server/app/modules/transaction/domain/dates.py
git commit -m "Docs: the 503 category, the issuer and clock-skew symptoms, the slimmer auth seam"
```

---

### Task 6: Gates, hand check, push

- [ ] **Step 1: All gates on the final tree**

```bash
make check
make test-web
cd server && APP_ENV=test uv run pytest tests/unit -m unit -q
cd server && APP_ENV=test uv run pytest tests/integration -m integration -q
make check-contract
```

Expected: all green; `check-contract` reports no drift.

- [ ] **Step 2: Hand check the sign-in race** (the provider changed). Start the worktree's stack (`Dev: All`, or the make targets in `/run-stack`), sign out, sign in as the seeded user, land on `/home` and `/transactions`: no 401 in the network log, and every first query carries `Authorization`. Then stop the dev servers (`make dev-kill`).

- [ ] **Step 3: Delete the spec and plan** (their lasting facts are in `docs/` after Task 5):

```bash
git rm .superpowers/specs/2026-10-15-pr15-review-fixes.md .superpowers/plans/2026-10-15-pr15-review-fixes.md
git commit -m "Spec, plan: delete; their lasting facts are in docs/"
```

- [ ] **Step 4: Push and update the PR.** `git push`. Edit PR #15's body: add this round under a "Review round" heading (one line per spec decision D1–D10), correct "two error log lines" to three, and drop the known minor about the `clerk.md` 503 row (fixed in Task 5). Tell the `orchestrator` session the round is pushed, with the gate results.
