# Fixes before wave 3 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the 401 race after sign-in (and handle any 401 as an auth event), make `LLMService`'s fallback per call, reject import dates analytics cannot read, and give income and expenses their own chart colours.

**Architecture:** Four independent fixes plus one approved addition. Server: the date bounds move into `transaction` and the import checks them; `LLMService` keeps its model position in locals; the server's 401 is narrowed to bad credentials. Web: `@app/auth`'s `getToken` waits for a session being activated; `@app/api-client` retries a 401 once with a fresh token, then signs out; two new colour tokens.

**Tech Stack:** FastAPI, pytest (+ pytest-asyncio, testcontainers Postgres), import-linter; Next.js 16, React 19, TanStack Query 5, Clerk (`@clerk/nextjs` 6.39), Vitest + Testing Library (jsdom), Tailwind 4 tokens.

**Spec:** `.superpowers/specs/2026-10-15-pre-wave-3-fixes-design.md`

## Global Constraints

- Paths are relative to the worktree root `/Users/tizianoiacovelli/projects/personal-finance-app/.claude/worktrees/pre-wave-3`. Stay in it; never `cd` to the main checkout.
- Server unit tests: `cd server && APP_ENV=test uv run pytest <path> -m unit -q`. Integration tests: `-m integration`, they need Docker running.
- Web tests: `cd web-app && pnpm -s vitest run <path>`; the whole suite is `make test-web` from the root.
- Import contracts: `cd server && uv run lint-imports`. R6 puts `analytics` above `transaction`; R1 sends a cross-module import through the package root only.
- Never hand-edit `server/openapi.json` or `web-app/packages/api-client/src/generated/`. After a route or schema change, `make gen-contract` and commit what it produces.
- Exact values: `SESSION_WAIT_MS = 5000`; `MIN_DATE = date(1900, 1, 1)`, `MAX_DATE = date(2100, 12, 31)`; rejection reason `date out of range “<raw>”` (curly quotes, as the existing reasons); `UserProvisioningError` is 503 / `USER_PROVISIONING_FAILED`; `ClerkAuthenticationError` is 502 / `CLERK_AUTH_ERROR`; `--chart-income` `#008300` (light and dark), `--chart-expense` `#6250d6` light / `#9085e9` dark.
- Code reads like its neighbours: same comment density, docstring style and naming. Comments say why, not what.
- Commit messages follow the repo's style: `<Area>: <what changed>` in a sentence, e.g. `Import: reject a date analytics cannot read`.
- Before every push (done by the controller, not per task): `make check`, `make test-web`, server unit and integration tests, `make check-contract`.

## Review Focus

1. **A hard reload of a dashboard page.** Clerk has not loaded (`isSignedIn` false), but its `getToken` waits for the load and returns a token. `getToken` must return it at once, never wait 5 s. Test in Task 4.
2. **Several queries waiting for the same session.** Every pending `getToken` resolves when the session arrives, not just the first. Test in Task 4.
3. **The session ended in another tab.** No token, so two 401s. The client signs out once, however many queries fail, and does not loop back to the dashboard. Tests in Tasks 4 (single-flight `signOut`) and 5 (second 401 signs out).
4. **A 401 on a POST with a body.** The retry sends the same body again. Test in Task 5.
5. **A row dated exactly `MIN_DATE` or `MAX_DATE`.** It is kept; only dates outside are rejected. Test in Task 1.

---

### Task 1: The import rejects a date analytics cannot read

**Files:**
- Create: `server/app/modules/transaction/domain/dates.py`
- Modify: `server/app/modules/transaction/__init__.py`
- Modify: `server/app/modules/analytics/schemas.py:17-19` (and the `DateRange` docstring if it names them)
- Modify: `server/app/modules/analytics/service.py:14-18`
- Modify: `server/app/modules/analytics/dependencies.py:9`
- Modify: `server/app/modules/transaction/imports/domain.py` (imports, `read_rows` docstring and loop)
- Modify: `docs/product/features/csv-import.md:60`
- Test: `server/tests/unit/modules/transaction/imports/test_domain.py` (class `TestReadRows`)

**Interfaces:**
- Produces: `from app.modules.transaction import MIN_DATE, MAX_DATE` (both `datetime.date`). Inside `transaction`: `from app.modules.transaction.domain.dates import MIN_DATE, MAX_DATE`.

- [ ] **Step 1: Write the failing test**

Add to `class TestReadRows` in `server/tests/unit/modules/transaction/imports/test_domain.py`:

```python
    def test_a_date_analytics_cannot_read_is_rejected(self):
        text = (
            "d,m,a\n"
            "1899-12-31,Early,1\n"
            "1900-01-01,First,1\n"
            "2100-12-31,Last,1\n"
            "2101-01-01,Late,1\n"
            "2205-03-01,Typo,1\n"
        )
        rows, rejected = read_rows(parse(text), {"d": "date", "m": "merchant", "a": "amount"})
        assert [(r.number, r.date) for r in rows] == [(3, dt.date(1900, 1, 1)), (4, dt.date(2100, 12, 31))]
        assert [(r.number, r.reason) for r in rejected] == [
            (2, "date out of range “1899-12-31”"),
            (5, "date out of range “2101-01-01”"),
            (6, "date out of range “2205-03-01”"),
        ]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/modules/transaction/imports/test_domain.py -m unit -q -k analytics_cannot_read`
Expected: FAIL. The out-of-range rows come back in `rows`, and `rejected` is empty.

- [ ] **Step 3: Move the bounds into `transaction`**

Create `server/app/modules/transaction/domain/dates.py`:

```python
"""The dates a transaction can carry and still be analysed."""

import datetime as dt

# The dates analytics covers. An explicit bound outside them is a 422; a row outside them
# would be left out of every analysis, so the import rejects it instead of saving it.
MIN_DATE = dt.date(1900, 1, 1)
MAX_DATE = dt.date(2100, 12, 31)
```

In `server/app/modules/transaction/__init__.py`, add the import after the `exceptions` import, and add both names to `__all__`. The list is in ASCII order, so they go between `"DuplicateTransactionError"` and `"TransactionFilters"`:

```python
from app.modules.transaction.domain.dates import MAX_DATE, MIN_DATE
```

```python
    "DuplicateTransactionError",
    "MAX_DATE",
    "MIN_DATE",
    "TransactionFilters",
```

In `server/app/modules/analytics/schemas.py`, delete the comment and the two assignments at lines 17–19:

```python
# The dates analytics covers. An explicit bound outside them is a 422; a row outside them is left out.
MIN_DATE = dt.date(1900, 1, 1)
MAX_DATE = dt.date(2100, 12, 31)
```

If `dt` is then unused in `schemas.py`, ruff will say so; remove that import only then. The `DateRange` docstring may keep naming `MIN_DATE`/`MAX_DATE`. Prose needs no import.

In `server/app/modules/analytics/dependencies.py:9`, replace:

```python
from app.modules.analytics.schemas import MAX_DATE, MIN_DATE, DateRange
```

with:

```python
from app.modules.analytics.schemas import DateRange
from app.modules.transaction import MAX_DATE, MIN_DATE
```

In `server/app/modules/analytics/service.py`, remove `MAX_DATE,` and `MIN_DATE,` from the `from app.modules.analytics.schemas import (...)` block. Extend the existing line 27 `from app.modules.transaction import AnalysisRow, transaction_service` to:

```python
from app.modules.transaction import MAX_DATE, MIN_DATE, AnalysisRow, transaction_service
```

Let `uv run ruff check --fix` order the names if it disagrees.

Then: `cd server && grep -rn "MIN_DATE\|MAX_DATE" app` must show the definitions only in `transaction/domain/dates.py`.

- [ ] **Step 4: Reject the row**

In `server/app/modules/transaction/imports/domain.py`, add after the stdlib imports (a first-party block):

```python
from app.modules.transaction.domain.dates import MAX_DATE, MIN_DATE
```

In `read_rows`, directly after the `if date is None:` block:

```python
        if not MIN_DATE <= date <= MAX_DATE:
            rejected.append(Rejection(row.number, f"date out of range “{_shown(raw_date)}”"))
            continue
```

In the `read_rows` docstring, change "an unreadable date" to "an unreadable date, a date outside MIN_DATE–MAX_DATE".

- [ ] **Step 5: Run the tests and the contracts**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/modules/transaction tests/unit/modules/analytics -m unit -q && uv run lint-imports && uv run ruff check app tests && uv run ruff format --check app tests`
Expected: all PASS; `lint-imports` reports every contract kept.

- [ ] **Step 6: Update the feature doc**

In `docs/product/features/csv-import.md:60`, the "Bad rows are skipped, not fatal" bullet lists the reasons. Add the new one after "an unreadable date": "a date outside 1900–2100 (analytics reads nothing outside it)". Match the bullet's sentence style.

- [ ] **Step 7: Commit**

```bash
git add server/app/modules/transaction server/app/modules/analytics server/tests/unit/modules/transaction docs/product/features/csv-import.md
git commit -m "Import: reject a date analytics cannot read; the bounds move into transaction"
```

---

### Task 2: `LLMService` keeps its fallback position per call

**Files:**
- Modify: `server/app/integrations/llm/service.py` (class `LLMService`)
- Modify: `server/app/agents/shared/structured.py:19-27` (docstring only)
- Modify: `server/tests/unit/integrations/llm/test_service.py`
- Modify: `server/tests/unit/agents/transaction_labeler/test_labeler.py:132-149` (delete one test)

**Interfaces:**
- Produces (private, used only by tests): `LLMService._default_index: int`; `LLMService._next(index: int) -> tuple[int, BaseChatModel]`; `LLMService._call_llm_with_retry(llm, messages, config=None)`; `LLMService._call_with_fallback(messages, config, start_index, start_llm)`.
- Public API unchanged: `call(messages, model_name=None, config=None, **model_kwargs)`, `get_llm()`, `current_model_name()`, `bind_tools(tools)`. `get_llm()` and `current_model_name()` now always mean the default model.

- [ ] **Step 1: Write the failing concurrency tests**

Append to `server/tests/unit/integrations/llm/test_service.py`. Add `import asyncio` to the stdlib imports and `OpenAIError` to the `from openai import (...)` line:

```python
class _FakeModel:
    """A model client that records which call reached it, yields, then answers or fails.

    It fails with a bare OpenAIError, which tenacity does not retry, so a call moves
    to the next model at once and the tests need no waits.
    """

    def __init__(self, name: str, log: list, healthy: bool):
        self.name, self.log, self.healthy = name, log, healthy
        self.hold: asyncio.Event | None = None

    async def ainvoke(self, messages, config=None):
        self.log.append((messages[0].content, self.name))
        await asyncio.sleep(0)
        if self.hold is not None:
            await self.hold.wait()
        if not self.healthy:
            raise OpenAIError(f"{self.name} is down")
        return AIMessage(content=self.name)


class TestConcurrentCalls:
    """Calls running at once on one service: `llm_service` is shared by every request."""

    @pytest.mark.asyncio
    async def test_each_call_walks_the_registry_from_the_default(self):
        names = LLMRegistry.get_all_names()
        service = LLMService()
        start = names.index(service.current_model_name())
        order = [names[(start + i) % len(names)] for i in range(len(names))]
        log: list = []
        fakes = {n: _FakeModel(n, log, healthy=n == order[-1]) for n in names}

        with patch.object(service, "_resolve", side_effect=lambda name, **kw: fakes[name]):
            answers = await asyncio.gather(
                *(service.call([HumanMessage(content=f"call {i}")]) for i in range(3)),
                return_exceptions=True,
            )

        assert [a.content if isinstance(a, AIMessage) else repr(a) for a in answers] == [order[-1]] * 3
        for i in range(3):
            assert [model for caller, model in log if caller == f"call {i}"] == order
        assert service.current_model_name() == order[0]

    @pytest.mark.asyncio
    async def test_a_pinned_call_does_not_move_a_concurrent_default_call(self):
        names = LLMRegistry.get_all_names()
        service = LLMService()
        default = service.current_model_name()
        pinned = next(n for n in names if n != default)
        log: list = []
        fakes = {n: _FakeModel(n, log, healthy=True) for n in names}
        fakes[pinned].hold = asyncio.Event()

        with patch.object(service, "_resolve", side_effect=lambda name, **kw: fakes[name]):
            pinned_call = asyncio.create_task(service.call([HumanMessage(content="pinned")], model_name=pinned))
            while not log:  # the pinned call is at its model, mid-flight
                await asyncio.sleep(0)
            default_answer = await service.call([HumanMessage(content="default")])
            fakes[pinned].hold.set()
            pinned_answer = await pinned_call

        assert default_answer.content == default
        assert pinned_answer.content == pinned
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/integrations/llm/test_service.py -m unit -q -k TestConcurrentCalls`
Expected: both FAIL. In the first, the calls skip models (some end in `LLMAPIError`) and the service is left off the default. In the second, the default call answers with the pinned model's name.

- [ ] **Step 3: Rewrite the position handling in `LLMService`**

In `server/app/integrations/llm/service.py`, class `LLMService`:

1. In `__init__`, rename `self._current_model_index` to `self._default_index`, in both the assignment and the `except` branch. Add to the docstring: "`_default_index` is set here and never moves: a call keeps its fallback position in its own locals, since `llm_service` is shared by every request."

2. Delete `_get_next_model_index` and `_switch_to_next_model`. Add in their place:

```python
    def _next(self, index: int) -> tuple[int, BaseChatModel]:
        """The model after `index` in the registry, wrapping to 0 at the end, with its client resolved."""
        next_index = (index + 1) % len(LLMRegistry.LLMS)
        return next_index, self._resolve(LLMRegistry.get_model_at_index(next_index)["name"])
```

3. `_call_llm_with_retry` takes the client. Keep the `@retry(...)` decorator as it is. Change the signature and the first lines:

```python
    async def _call_llm_with_retry(
        self, llm: BaseChatModel, messages: List[BaseMessage], config: Optional[RunnableConfig] = None
    ) -> BaseMessage:
        """Call `llm`, retrying per the decorator. Raises OpenAIError if all fail."""
        try:
            response = await llm.ainvoke(messages, config=config)
```

Delete the `llm = self.get_llm()` / `if not llm: raise RuntimeError(...)` lines. The rest of the method is unchanged.

4. Replace `call` from the line `# Resolved before anything is saved or assigned` to the end of the method:

```python
        if not model_name:
            return await self._call_with_fallback(messages, config, self._default_index, self.get_llm())

        try:
            pinned = self._resolve(model_name, **model_kwargs)
        except ValueError as e:
            logger.error("requested_model_not_found", model_name=model_name, error=str(e))
            raise

        # The pin lives in this call's locals, never on the service: `llm_service` is a
        # singleton shared by every request, and a pin set on it would retarget their calls.
        logger.info("using_requested_model", model_name=model_name, has_custom_kwargs=bool(model_kwargs))
        return await self._call_with_fallback(messages, config, LLMRegistry.get_all_names().index(model_name), pinned)
```

`_resolve` raised `ValueError` for a name outside the registry, so `.index` cannot fail here.

5. Replace `_call_with_fallback` whole:

```python
    async def _call_with_fallback(
        self,
        messages: List[BaseMessage],
        config: Optional[RunnableConfig],
        start_index: int,
        start_llm: BaseChatModel,
    ) -> BaseMessage:
        """Call the model at `start_index`, rotating through the registry on failure.

        The position is in locals. Calls run at once on one service, so a position kept
        on the service would be moved by every call's failures, and a call could use up
        its attempts without reaching a healthy model.

        Raises:
            LLMRateLimitError: If every model rate-limits
            LLMTimeoutError: If every model times out
            LLMAPIError: If every model returns an API error
            LLMFallbackExhaustedError: If the rotation ends without a response
        """
        total_models = len(LLMRegistry.LLMS)
        index, llm = start_index, start_llm
        models_tried = 0
        last_error = None

        while models_tried < total_models:
            current_model_name = LLMRegistry.LLMS[index]["name"]
            try:
                return await self._call_llm_with_retry(llm, messages, config)
            except RateLimitError as e:
                last_error = e
                models_tried += 1
                logger.error(
                    "llm_rate_limit_after_retries",
                    model=current_model_name,
                    models_tried=models_tried,
                    total_models=total_models,
                    error=str(e),
                )
                if models_tried >= total_models:
                    raise LLMRateLimitError(
                        f"Rate limit exceeded on all {total_models} models",
                        models_tried=models_tried,
                        last_model=current_model_name,
                    ) from e
            except APITimeoutError as e:
                last_error = e
                models_tried += 1
                logger.error(
                    "llm_timeout_after_retries",
                    model=current_model_name,
                    models_tried=models_tried,
                    total_models=total_models,
                    error=str(e),
                )
                if models_tried >= total_models:
                    raise LLMTimeoutError(
                        f"Timeout on all {total_models} models",
                        models_tried=models_tried,
                        last_model=current_model_name,
                    ) from e
            except OpenAIError as e:
                last_error = e
                models_tried += 1
                logger.error(
                    "llm_call_failed_after_retries",
                    model=current_model_name,
                    models_tried=models_tried,
                    total_models=total_models,
                    error=str(e),
                )
                if models_tried >= total_models:
                    logger.error(
                        "all_models_failed",
                        models_tried=models_tried,
                        starting_model=LLMRegistry.LLMS[start_index]["name"],
                    )
                    raise LLMAPIError(
                        f"LLM API error on all {total_models} models: {str(e)}",
                        models_tried=models_tried,
                        last_model=current_model_name,
                        error_type=type(e).__name__,
                    ) from e

            try:
                next_index, llm = self._next(index)
            except Exception as e:
                logger.error("model_switch_failed", error=str(e))
                break
            logger.warning(
                "switching_to_next_model",
                from_index=index,
                to_index=next_index,
                to_model=LLMRegistry.LLMS[next_index]["name"],
            )
            index = next_index

        # Only reachable when a switch failed mid-rotation; the exhaustion cases
        # above raise their own typed error.
        raise LLMFallbackExhaustedError(
            f"All {total_models} models failed after retries. Last error: {str(last_error)}",
            models_tried=models_tried,
            starting_model=LLMRegistry.LLMS[start_index]["name"],
            last_error=str(last_error) if last_error else None,
        )
```

6. `get_llm` and `current_model_name` use `_default_index`:

```python
    def get_llm(self) -> Optional[BaseChatModel]:
        """The default model's client, building it on first use."""
        if self._llm is None:
            entry = LLMRegistry.get_model_at_index(self._default_index)
            self._llm = self._resolve(entry["name"])
        return self._llm

    def current_model_name(self) -> str:
        """The default model: where every call that pins none starts.

        Ask here, not the client: `get_name()` returns the class name, and
        `model_name` is absent from a tool-bound client's own attributes.
        """
        return LLMRegistry.get_model_at_index(self._default_index)["name"]
```

7. In `_resolve`'s docstring, "Every assignment to `_llm` must go through here" stays true. "makes that correct for a *switch*" now refers to `_next`. Reword it as "Resolving from the registry rather than from a held client is what makes that correct for `_next`, which moves to another model."

8. Check: `grep -n "_current_model_index\|_switch_to_next_model\|_get_next_model_index" app` returns nothing.

- [ ] **Step 4: Move the existing tests to the new shape**

In `server/tests/unit/integrations/llm/test_service.py`:
- `_other_model`: `service._current_model_index` → `service._default_index`.
- `test_default_model_found`: `service._current_model_index` → `service._default_index`.
- Every fake passed as `side_effect` for `_call_llm_with_retry` gains the client as its first parameter. `async def mock_retry(msgs, config=None):` becomes `async def mock_retry(llm, msgs, config=None):`. The same goes for `always_rate_limit`, `always_timeout`, `always_api_error` and `boom`.
- `test_pinned_model_keeps_tools`: the fake records the client it was given:

```python
        async def capture(llm, msgs, config=None):
            seen["llm"] = llm
            return AIMessage(content="ok")
```

- `test_pinned_model_does_not_persist` and `test_pinned_model_restored_when_the_call_raises`: replace `_current_model_index` with `_default_index`. In the second test's docstring, replace the explanation of the `finally` with: "The pin is a local of the call, so an escaping error has nothing on the service to leave behind. A `RuntimeError` escapes `call()` mid-flight without going through the fallback ladder."
- Replace `class TestLLMServiceModelSwitching` whole:

```python
class TestLLMServiceNextModel:
    """Tests for `_next`, the step of the fallback rotation."""

    def test_next_wraps_to_the_first_model(self):
        index, _ = LLMService()._next(len(LLMRegistry.LLMS) - 1)
        assert index == 0

    def test_next_keeps_bound_tools(self):
        """A fallback must not drop the tools.

        The client for the next model is resolved through `_resolve`, which binds the
        service's tools. A bare registry client would leave the agent toolless after a
        fallback, and silently, since the graph routes on an empty `tool_calls` rather
        than raising.
        """
        _, llm = LLMService().bind_tools([echo])._next(0)
        assert isinstance(llm, RunnableBinding)
        assert _bound_tool_names(llm) == ["echo"]
```

- [ ] **Step 5: Drop the per-import reason**

In `server/app/agents/shared/structured.py`, the `structured_llm` docstring becomes:

```python
    """A service for one import's calls.

    Tool-less: the chatbot's `llm_service` has tools bound, and an answer here
    must never be a tool call. Builds no client until the first call, so it
    needs no API key.
    """
```

In `server/tests/unit/agents/transaction_labeler/test_labeler.py`, delete `test_each_import_rotates_its_own_model_fallback` (lines 132–149). The property it guarded, one service's fallback kept away from another's, no longer depends on sharing.

- [ ] **Step 6: Run the tests**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/integrations/llm tests/unit/agents -m unit -q && uv run ruff check app tests && uv run ruff format --check app tests`
Expected: all PASS, including both `TestConcurrentCalls` tests.

- [ ] **Step 7: Commit**

```bash
git add server/app/integrations/llm/service.py server/app/agents/shared/structured.py server/tests/unit/integrations/llm/test_service.py server/tests/unit/agents/transaction_labeler/test_labeler.py
git commit -m "LLMService: keep the fallback position in each call's locals, so concurrent calls never move each other"
```

---

### Task 3: The server's 401 means bad credentials, nothing else

**Files:**
- Modify: `server/app/modules/account/exceptions.py`
- Modify: `server/app/modules/account/dependencies.py:16,54-55`
- Modify: `server/app/integrations/clerk/exceptions.py:35-39`
- Modify: `docs/architecture/server.md` (after the error-category table, ~line 292)
- Modify: `docs/setup/clerk.md:274`
- Test: `server/tests/integration/modules/account/router/test_auth.py`
- Test: `server/tests/unit/integrations/clerk/test_client.py`

**Interfaces:**
- Produces: `app.modules.account.exceptions.UserProvisioningError(ServiceError)`, status 503, `error_code = "USER_PROVISIONING_FAILED"`. `ClerkAuthenticationError.status_code == 502`. Task 5 relies on this: a 401 now always means the request's credentials.

- [ ] **Step 1: Write the failing tests**

Add to `class TestGetMe` in `server/tests/integration/modules/account/router/test_auth.py`. It already imports `patch`:

```python
    @patch("app.modules.account.dependencies.user_service.resolve_user", side_effect=RuntimeError("db down"))
    @patch("app.api.middlewares.auth.clerk_jwt_verifier")
    async def test_a_provisioning_failure_is_503_not_401(self, mock_verifier, _resolve, client):
        """The web signs out on a persistent 401, and an outage behind valid credentials is not an ended session."""
        mock_verifier.verify_token.return_value = {"sub": "clerk_provision_fails"}

        response = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer t"})

        assert response.status_code == 503
        assert response.json()["error"] == "USER_PROVISIONING_FAILED"
```

`test_unauthenticated_returns_401`, already in the class, keeps the no-token case at 401.

Add to `server/tests/unit/integrations/clerk/test_client.py`, at module level:

```python
def test_a_rejected_server_secret_is_a_bad_gateway_not_a_401():
    """The server's own Clerk secret being refused is an upstream failure; a 401 would sign the user out."""
    assert ClerkAuthenticationError("Authentication with Clerk API failed").status_code == 502
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/integrations/clerk/test_client.py -m unit -q -k bad_gateway && APP_ENV=test uv run pytest tests/integration/modules/account/router/test_auth.py -m integration -q -k provisioning_failure`
Expected: both FAIL. The status is 401.

- [ ] **Step 3: Implement**

`server/app/modules/account/exceptions.py`:

```python
"""User service domain exceptions."""

from app.exceptions.base import ConflictError, ServiceError


class UserAlreadyExistsError(ConflictError):
    """Exception raised when attempting to create a user that already exists."""

    error_code = "USER_ALREADY_EXISTS"


class UserProvisioningError(ServiceError):
    """The request's credentials were valid, but its user could not be resolved or created.

    503, not 401: the web treats a persistent 401 as an ended session and signs out,
    and a database or Clerk outage during provisioning is not that.
    """

    status_code = 503
    error_code = "USER_PROVISIONING_FAILED"
```

`server/app/modules/account/dependencies.py`: add `from app.modules.account.exceptions import UserProvisioningError` next to the other `app.modules.account` imports, and in `get_current_user` replace:

```python
        raise AuthenticationError("Failed to provision user") from e
```

with:

```python
        raise UserProvisioningError("Failed to provision user") from e
```

`AuthenticationError` is still used by `get_clerk_id`. Keep its import.

`server/app/integrations/clerk/exceptions.py`, class `ClerkAuthenticationError`:

```python
class ClerkAuthenticationError(ClerkServiceError):
    """Raised when Clerk API authentication fails: the server's own secret was refused.

    502, not 401: the failure is upstream, and the web treats a persistent 401 as the
    user's session ending.
    """

    status_code = 502
    error_code = "CLERK_AUTH_ERROR"
```

- [ ] **Step 4: Run the tests and the contract**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/integrations/clerk tests/unit/modules/account -m unit -q && APP_ENV=test uv run pytest tests/integration/modules/account -m integration -q && uv run ruff check app tests && uv run ruff format --check app tests`
Expected: all PASS.

Run from the root: `make gen-contract && git status --short server/openapi.json web-app/packages/api-client/src/generated`
Expected: no change. No route declares a 401, 502 or 503 response. If anything did change, commit it with this task.

- [ ] **Step 5: Docs**

`docs/architecture/server.md`: below the category table (the row `| DatabaseConnectionError | 503 |`), add:

```markdown
**A 401 means the request's credentials, nothing else.** The web retries a 401 once with
a fresh token and signs out on the second ([`web-app.md`](./web-app.md) §5), so a failure
behind valid credentials must not be a 401: provisioning that fails is
`UserProvisioningError` (503), and the server's own Clerk secret being refused is
`ClerkAuthenticationError` (502).
```

Check that `web-app.md` §5 is the section holding the fetch-layer bullets (the one with "`QueryProvider` owns the error policy"). If that section has another number, use it.

`docs/setup/clerk.md:274`: the row starts `| A new user signs up and the first call answers 401 "Failed to provision user" |`. Change `401` to `503 \`USER_PROVISIONING_FAILED\``. Leave the rest of the row as it is.

- [ ] **Step 6: Commit**

```bash
git add server/app/modules/account server/app/integrations/clerk/exceptions.py server/tests/integration/modules/account/router/test_auth.py server/tests/unit/integrations/clerk/test_client.py docs/architecture/server.md docs/setup/clerk.md
git commit -m "Server: a 401 means bad credentials; provisioning failure is 503, a refused Clerk secret 502"
```

---

### Task 4: `getToken` waits for a session being activated

**Files:**
- Modify: `web-app/packages/auth/src/provider.tsx` (whole file below)
- Modify: `web-app/packages/auth/src/index.ts`
- Test: `web-app/packages/auth/src/provider.test.tsx`
- Create (test): `web-app/apps/web/src/lib/first-query-after-sign-in.test.tsx`
- Modify: `docs/architecture/web-app.md:101-106`, `docs/architecture/authentication.md` §2

**Interfaces:**
- Produces from `@app/auth`: `useAppAuth(): { user, isLoaded, isSignedIn: boolean, getToken: (options?: GetTokenOptions) => Promise<string | null>, signOut: () => Promise<void> }`; `type GetTokenOptions = { forceRefresh?: boolean }`; `SESSION_WAIT_MS = 5000`. `signOut` is single-flight: a call while one is in flight returns the same promise. Task 5 relies on `getToken({ forceRefresh: true })` and on `signOut` being single-flight.

- [ ] **Step 1: Write the failing tests in `provider.test.tsx`**

Make the Clerk mock controllable. Replace the hoisted `clerk` object and the `vi.mock("@clerk/nextjs", ...)` block with:

```tsx
const clerk = vi.hoisted(() => ({
  user: null as Record<string, unknown> | null,
  endSession: vi.fn(),
  isSignedIn: true as boolean | undefined,
  getToken: vi.fn(),
}))

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    isLoaded: true,
    isSignedIn: clerk.isSignedIn,
    getToken: clerk.getToken,
    signOut: clerk.endSession,
  }),
  useUser: () => ({ user: clerk.user }),
}))
```

Change the import to `import { AuthProvider, SESSION_WAIT_MS, useAppAuth } from "./provider"`. Replace `renderAuth` with a version that also exposes `rerender`. The existing tests keep calling `renderAuth(...)` and reading `.current`:

```tsx
function renderAuthHook(signOutUrl?: string) {
  function Wrapper({ children }: { children: ReactNode }) {
    return <AuthProvider signOutUrl={signOutUrl}>{children}</AuthProvider>
  }
  return renderHook(() => useAppAuth(), { wrapper: Wrapper })
}

function renderAuth(signOutUrl?: string) {
  return renderAuthHook(signOutUrl).result
}

/** Let pending promise callbacks run. */
const flush = () => new Promise((resolve) => setTimeout(resolve, 0))
```

In `beforeEach`, add:

```tsx
  clerk.isSignedIn = true
  clerk.getToken.mockReset()
  clerk.getToken.mockResolvedValue("jwt")
```

Add these tests at the end of the file:

```tsx
describe("getToken", () => {
  it("returns Clerk's token without waiting", async () => {
    await expect(renderAuth().current.getToken()).resolves.toBe("jwt")
    expect(clerk.getToken).toHaveBeenCalledWith(undefined)
  })

  // A hard reload: Clerk has not loaded, so no session yet, but its getToken waits
  // for the load and returns the token. That must come back at once, not after a wait.
  it("returns a token Clerk gives before the session is reported", async () => {
    clerk.isSignedIn = undefined
    await expect(renderAuth().current.getToken()).resolves.toBe("jwt")
    expect(clerk.getToken).toHaveBeenCalledOnce()
  })

  it("asks Clerk for a fresh token on forceRefresh", async () => {
    await renderAuth().current.getToken({ forceRefresh: true })
    expect(clerk.getToken).toHaveBeenCalledWith({ skipCache: true })
  })

  // Straight after sign-in: Clerk is loaded but has not installed the session yet.
  it("waits for a session being activated, then returns its token", async () => {
    clerk.isSignedIn = false
    clerk.getToken.mockResolvedValueOnce(null)
    const { result, rerender } = renderAuthHook()

    let token: string | null | undefined
    const pending = result.current.getToken().then((t) => (token = t))
    await flush()
    expect(token).toBeUndefined()

    clerk.isSignedIn = true
    clerk.getToken.mockResolvedValue("fresh")
    rerender()
    await pending
    expect(token).toBe("fresh")
  })

  it("wakes every request waiting for the session", async () => {
    clerk.isSignedIn = false
    clerk.getToken.mockResolvedValue(null)
    const { result, rerender } = renderAuthHook()

    const pending = Promise.all([
      result.current.getToken(),
      result.current.getToken(),
    ])
    await flush()

    clerk.isSignedIn = true
    clerk.getToken.mockResolvedValue("fresh")
    rerender()
    await expect(pending).resolves.toEqual(["fresh", "fresh"])
  })

  it("answers null when no session arrives in time", async () => {
    vi.useFakeTimers()
    try {
      clerk.isSignedIn = false
      clerk.getToken.mockResolvedValue(null)
      const pending = renderAuth().current.getToken()

      await vi.advanceTimersByTimeAsync(SESSION_WAIT_MS)
      await expect(pending).resolves.toBeNull()
      expect(clerk.getToken).toHaveBeenCalledOnce()
    } finally {
      vi.useRealTimers()
    }
  })

  it("reports whether Clerk has a session", () => {
    expect(renderAuth().current.isSignedIn).toBe(true)
    clerk.isSignedIn = undefined
    expect(renderAuth().current.isSignedIn).toBe(false)
  })
})
```

Add to `describe("signOut", ...)`:

```tsx
  // Many requests refused at once each ask to sign out; the session ends once.
  it("ends the session once when called again while in flight", async () => {
    clerk.endSession.mockResolvedValue(undefined)
    const auth = renderAuth("/sign-in")

    await Promise.all([auth.current.signOut(), auth.current.signOut()])
    expect(clerk.endSession).toHaveBeenCalledOnce()
    expect(assign).toHaveBeenCalledOnce()
  })
```

- [ ] **Step 2: Write the failing wiring test in `apps/web`**

Create `web-app/apps/web/src/lib/first-query-after-sign-in.test.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { useApiFetch } from "@app/api-client"
import { QueryProvider } from "@app/api-client/query-provider"
import { AuthProvider } from "@app/auth"

// BUGS.md, "The first page load after sign-in fires its queries without a token".
// The real AuthProvider, QueryProvider and mutator; only Clerk is mocked, in the
// state it is in straight after sign-in: loaded, with no session installed yet.
const clerk = vi.hoisted(() => ({
  isSignedIn: false,
  token: null as string | null,
}))

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    isLoaded: true,
    isSignedIn: clerk.isSignedIn,
    getToken: async () => clerk.token,
    signOut: async () => {},
  }),
  useUser: () => ({ user: null }),
}))

function Me() {
  const fetcher = useApiFetch()
  const { data } = useQuery({
    queryKey: ["me"],
    queryFn: () => fetcher<{ id: string }>("/api/v1/auth/me"),
  })
  return <p>{data?.id ?? "loading"}</p>
}

function App() {
  return (
    <AuthProvider>
      <QueryProvider>
        <Me />
      </QueryProvider>
    </AuthProvider>
  )
}

beforeEach(() => {
  clerk.isSignedIn = false
  clerk.token = null
  process.env.NEXT_PUBLIC_API_URL = "http://localhost:8100"
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(JSON.stringify({ id: "u1" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
    ),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

it("holds the first query until the session is active, then sends it with the token", async () => {
  const { rerender } = render(<App />)
  await new Promise((resolve) => setTimeout(resolve, 20))
  expect(globalThis.fetch).not.toHaveBeenCalled()

  clerk.isSignedIn = true
  clerk.token = "jwt-after-sign-in"
  rerender(<App />)

  await screen.findByText("u1")
  expect(globalThis.fetch).toHaveBeenCalledOnce()
  const [, init] = vi.mocked(globalThis.fetch).mock.calls[0]
  expect(new Headers(init?.headers).get("Authorization")).toBe(
    "Bearer jwt-after-sign-in",
  )
})
```

If `vi.mock("@clerk/nextjs")` here does not reach `packages/auth`'s import, the test sees a real Clerk error about a missing `ClerkProvider`. In that case check `ls web-app/node_modules/.pnpm | grep clerk+nextjs`: there must be exactly one version. Report it as a blocker rather than moving the test.

- [ ] **Step 3: Run them to verify they fail**

Run: `cd web-app && pnpm -s vitest run packages/auth/src/provider.test.tsx apps/web/src/lib/first-query-after-sign-in.test.tsx`
Expected: FAIL. `SESSION_WAIT_MS` is not exported. Once that import resolves, the waiting tests fail because `getToken` returns `null` at once, `isSignedIn` is undefined, `signOut` ends the session twice, and the wiring test sees one `fetch` before the session.

- [ ] **Step 4: Implement `provider.tsx`**

Replace `web-app/packages/auth/src/provider.tsx` with:

```tsx
/**
 * AuthProvider and useAppAuth hook.
 *
 * Portability seam: AuthProvider wraps Clerk's hooks to derive identity.
 * When migrating to WorkOS, only AuthProvider's internals change.
 * All components call useAppAuth() — they never call useAuth() or useUser()
 * directly — and the context exposes no vendor type.
 */
"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
} from "react"
import { useAuth, useUser } from "@clerk/nextjs"

/** How long getToken waits for a session being activated before answering null. */
export const SESSION_WAIT_MS = 5000

/** The signed-in user's profile, as the vendor reports it. */
export interface AppUser {
  /** Full name, or null when the profile has none. */
  name: string | null
  email: string | null
  imageUrl: string | null
}

export interface GetTokenOptions {
  /** Skip the cached token and fetch a new one: the server refused the last. */
  forceRefresh?: boolean
}

interface AuthContextValue {
  /** The signed-in user, or null while loading or signed out. */
  user: AppUser | null
  /** True once Clerk has finished initialising the session. */
  isLoaded: boolean
  /** True once Clerk has an active session. Straight after sign-in it trails the navigation. */
  isSignedIn: boolean
  /**
   * A fresh JWT for the current session; null only once the state has settled
   * with no session. Straight after sign-in Clerk reports no session for a moment
   * while it installs the new one, and a null then would send the request bare,
   * so a null from Clerk without a session waits for one, up to SESSION_WAIT_MS.
   * The only sanctioned way to reach a bearer token: @app/api-client's mutator
   * consumes it, which is what keeps that package off Clerk and on this seam.
   */
  getToken: (options?: GetTokenOptions) => Promise<string | null>
  /**
   * End the session, then load `signOutUrl` as a new document. A router push
   * would keep the heap — every cache and context the previous user filled —
   * alive across a trust boundary. A call while one is in flight returns the
   * same promise, so many refused requests sign out once.
   */
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  isLoaded: false,
  isSignedIn: false,
  getToken: async () => null,
  signOut: async () => {},
})

/** True when `waiters` is woken by a session, false after SESSION_WAIT_MS. */
function sessionArrives(waiters: Set<() => void>): Promise<boolean> {
  return new Promise((resolve) => {
    const wake = () => {
      clearTimeout(timer)
      resolve(true)
    }
    const timer = setTimeout(() => {
      waiters.delete(wake)
      resolve(false)
    }, SESSION_WAIT_MS)
    waiters.add(wake)
  })
}

/**
 * Wrap inside ClerkProvider in each app's root layout. `signOutUrl` is the
 * app's route, hence a prop.
 */
export function AuthProvider({
  children,
  signOutUrl = "/",
}: {
  children: React.ReactNode
  signOutUrl?: string
}) {
  const {
    isLoaded,
    isSignedIn = false,
    getToken: clerkGetToken,
    signOut: endSession,
  } = useAuth()
  const { user: clerkUser } = useUser()

  const user = useMemo<AppUser | null>(
    () =>
      clerkUser
        ? {
            name:
              [clerkUser.firstName, clerkUser.lastName]
                .filter(Boolean)
                .join(" ") || null,
            email: clerkUser.primaryEmailAddress?.emailAddress ?? null,
            imageUrl: clerkUser.imageUrl || null,
          }
        : null,
    [clerkUser],
  )

  // getToken outlives the render that made it, so it reads the session through
  // a ref, and the requests waiting for one are woken when it arrives.
  const signedIn = useRef(isSignedIn)
  const waiters = useRef(new Set<() => void>())
  useEffect(() => {
    signedIn.current = isSignedIn
    if (!isSignedIn) return
    for (const wake of waiters.current) wake()
    waiters.current.clear()
  }, [isSignedIn])

  const getToken = useCallback(
    async ({ forceRefresh = false }: GetTokenOptions = {}) => {
      const ask = () =>
        clerkGetToken(forceRefresh ? { skipCache: true } : undefined)
      const token = await ask()
      if (token) return token
      if (!signedIn.current && !(await sessionArrives(waiters.current)))
        return null
      return ask()
    },
    [clerkGetToken],
  )

  // Never cleared: the document load at the end of a sign-out replaces this page.
  const signingOut = useRef<Promise<void> | null>(null)
  const signOut = useCallback(() => {
    // Await: navigating away mid-request could leave the session alive.
    // redirectUrl because Clerk navigates too, and its default is "/".
    // finally: if the session is already gone, the destroy rejects, and
    // stranding the user on a signed-in page is the worse failure.
    signingOut.current ??= (async () => {
      try {
        await endSession({ redirectUrl: signOutUrl })
      } finally {
        window.location.assign(signOutUrl)
      }
    })()
    return signingOut.current
  }, [endSession, signOutUrl])

  return (
    <AuthContext.Provider
      value={{ user, isLoaded, isSignedIn, getToken, signOut }}
    >
      {children}
    </AuthContext.Provider>
  )
}

/**
 * Hook for the current user's identity.
 *
 * Never call useAuth() or useUser() directly in a component, and check
 * isLoaded before rendering user-dependent UI.
 */
export function useAppAuth(): AuthContextValue {
  return useContext(AuthContext)
}
```

`web-app/packages/auth/src/index.ts`:

```ts
export {
  AuthProvider,
  SESSION_WAIT_MS,
  useAppAuth,
  type AppUser,
  type GetTokenOptions,
} from "./provider"
```

- [ ] **Step 5: Run the tests and the type-check**

Run: `cd web-app && pnpm -s vitest run packages/auth apps/web/src/lib/first-query-after-sign-in.test.tsx packages/api-client && pnpm -s type-check && pnpm -s lint && pnpm -s format:check`
Expected: all PASS. `packages/api-client`'s existing tests are unaffected, since they mock `@app/auth` themselves.

- [ ] **Step 6: Docs**

`docs/architecture/web-app.md`, the `useAppAuth()` table at lines 101–106. Replace the `isLoaded`, `getToken` and `signOut` rows with:

```markdown
| `isLoaded` | Clerk has resolved |
| `isSignedIn` | Clerk has an active session; straight after sign-in it trails the navigation |
| `getToken` | the session token, fresh on every call; `{ forceRefresh }` skips Clerk's cache. Without a session it waits up to 5 s for one being activated, and answers `null` only once the state has settled |
| `signOut` | ends the session, then loads `signOutUrl` as a new document; a second call while one is in flight shares it |
```

`docs/architecture/authentication.md` §2. After the paragraph that starts `**It is short-lived.**`, add:

```markdown
**Straight after sign-in, it is waited for.** Clerk navigates to the redirect before the
new session is installed, so the first render's requests find no session and Clerk's
`getToken()` answers `null`. `@app/auth`'s `getToken` waits for the session instead, up
to five seconds, and the first queries go out with a token.
```

If the hand check in Task 7 shows a different mechanism, Task 7 corrects this sentence.

- [ ] **Step 7: Commit**

```bash
git add web-app/packages/auth web-app/apps/web/src/lib/first-query-after-sign-in.test.tsx docs/architecture/web-app.md docs/architecture/authentication.md
git commit -m "Auth: getToken waits for a session being activated, so the first queries after sign-in carry a token"
```

---

### Task 5: A 401 is retried once with a fresh token, then signs out

**Files:**
- Modify: `web-app/packages/api-client/src/use-api-fetch.ts` (`useApiRequest`)
- Test: `web-app/packages/api-client/src/use-api-fetch.test.ts`
- Modify: `docs/architecture/web-app.md` (the fetch-layer bullets, after "`QueryProvider` owns the error policy")
- Modify: `docs/architecture/authentication.md` §3
- Modify: `docs/guides/api-client-codegen.md:636-650` (the quoted `useApiRequest`)

**Interfaces:**
- Consumes: `useAppAuth().getToken(options?: { forceRefresh?: boolean })` and the single-flight `useAppAuth().signOut()` from Task 4. The server's 401 now always means bad credentials (Task 3).
- Produces: `useApiRequest(): ApiRequest`. Same signature, new 401 behaviour. `useApiFetch` inherits it.

- [ ] **Step 1: Write the failing tests**

In `web-app/packages/api-client/src/use-api-fetch.test.ts`, replace the hoisted mock and `vi.mock` with:

```ts
const { getToken, signOut } = vi.hoisted(() => ({
  getToken: vi.fn(),
  signOut: vi.fn(),
}))

vi.mock("@app/auth", () => ({ useAppAuth: () => ({ getToken, signOut }) }))
```

In `beforeEach`, add:

```ts
  signOut.mockReset()
  signOut.mockResolvedValue(undefined)
```

Add at the end of the file:

```ts
describe("a 401", () => {
  it("is retried once with a fresh token", async () => {
    getToken.mockResolvedValueOnce("stale").mockResolvedValueOnce("fresh")
    vi.mocked(globalThis.fetch)
      .mockResolvedValueOnce(jsonResponse({}, { status: 401 }))
      .mockResolvedValueOnce(jsonResponse({ ok: true }))

    await expect(callApi()("/api/v1/me")).resolves.toEqual({ ok: true })

    expect(getToken).toHaveBeenLastCalledWith({ forceRefresh: true })
    expect(lastCall().headers.get("Authorization")).toBe("Bearer fresh")
    expect(signOut).not.toHaveBeenCalled()
  })

  it("replays the request's body", async () => {
    vi.mocked(globalThis.fetch)
      .mockResolvedValueOnce(jsonResponse({}, { status: 401 }))
      .mockResolvedValueOnce(jsonResponse({ ok: true }))

    await callApi()("/api/v1/transactions", {
      method: "POST",
      body: '{"merchant":"x"}',
    })

    const bodies = vi
      .mocked(globalThis.fetch)
      .mock.calls.map(([, init]) => (init as RequestInit).body)
    expect(bodies).toEqual(['{"merchant":"x"}', '{"merchant":"x"}'])
  })

  // The session is over: ended in another tab, or never coming back.
  it("signs out when the retry is refused too, and still rejects", async () => {
    vi.mocked(globalThis.fetch).mockImplementation(async () =>
      jsonResponse({}, { status: 401 }),
    )

    const error = await rejection(callApi()("/api/v1/me"))

    expect(error.status).toBe(401)
    expect(globalThis.fetch).toHaveBeenCalledTimes(2)
    expect(signOut).toHaveBeenCalledOnce()
  })

  it("rejects with the ApiError even when signing out fails", async () => {
    signOut.mockRejectedValue(new Error("session already gone"))
    vi.mocked(globalThis.fetch).mockImplementation(async () =>
      jsonResponse({}, { status: 401 }),
    )

    const error = await rejection(callApi()("/api/v1/me"))
    expect(error.status).toBe(401)
  })
})

describe("other refusals", () => {
  it.each([403, 500])("%i is neither retried nor signs out", async (status) => {
    vi.mocked(globalThis.fetch).mockImplementation(async () =>
      jsonResponse({}, { status }),
    )

    await rejection(callApi()("/api/v1/me"))

    expect(globalThis.fetch).toHaveBeenCalledOnce()
    expect(getToken).toHaveBeenCalledOnce()
    expect(signOut).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd web-app && pnpm -s vitest run packages/api-client/src/use-api-fetch.test.ts`
Expected: the `a 401` tests FAIL. No retry happens and `signOut` is never called. `other refusals` already passes.

- [ ] **Step 3: Implement**

In `web-app/packages/api-client/src/use-api-fetch.ts`, replace `useApiRequest` and its docstring with:

```ts
const isUnauthorized = (error: unknown) =>
  error instanceof ApiError && error.status === 401

/**
 * The API's transport with the current session's token, read on every call.
 * For a caller that reads the body itself: the chat stream. Everything else
 * uses a generated hook, which goes through useApiFetch.
 *
 * A 401 is an auth event, not an error to show. The request goes once more
 * with a token fetched fresh. The server ran no handler, so replaying even a
 * POST is safe. A second 401 means the session is over, and signOut() ends it
 * and loads the sign-in page. The server keeps 401 for bad credentials alone,
 * so an outage never signs anyone out. The ApiError still reaches the caller.
 */
export function useApiRequest(): ApiRequest {
  const { getToken, signOut } = useAppAuth()
  return useCallback(
    async (url, init) => {
      try {
        return await apiRequest(url, init, await getToken())
      } catch (error) {
        if (!isUnauthorized(error)) throw error
      }
      try {
        return await apiRequest(
          url,
          init,
          await getToken({ forceRefresh: true }),
        )
      } catch (error) {
        // signOut is single-flight: many requests refused at once sign out once.
        // It navigates even when ending the session fails, so its rejection is moot.
        if (isUnauthorized(error)) void signOut().catch(() => {})
        throw error
      }
    },
    [getToken, signOut],
  )
}
```

`ApiError` is already imported at the top of the file.

- [ ] **Step 4: Run the tests**

Run: `cd web-app && pnpm -s vitest run packages/api-client apps/web/src/lib/first-query-after-sign-in.test.tsx && pnpm -s type-check && pnpm -s lint && pnpm -s format:check`
Expected: all PASS.

- [ ] **Step 5: Docs**

`docs/architecture/web-app.md`: after the bullet that starts `- **\`QueryProvider\` owns the error policy.**`, add:

```markdown
- **A 401 is an auth event, not an error.** `useApiRequest`, under every hook and the
  chat stream, retries a 401 once with a token fetched fresh (Clerk's cache skipped). A
  second 401 means the session is over: `signOut()` ends it and loads `/sign-in`, so a
  stale session never bounces back from the sign-in page. It only works because the
  server keeps 401 for bad credentials ([`server.md`](./server.md), the error table).
```

`docs/architecture/authentication.md` §3. After the paragraph starting `` `AuthMiddleware` verifies and never blocks. ``, add:

```markdown
**A 401 ends the session on the web.** The web retries it once with a fresh token, then
signs out. So the server answers 401 only when the request's credentials fail; an outage
behind valid ones is a 5xx ([`server.md`](./server.md)).
```

`docs/guides/api-client-codegen.md:636-650` quotes the old `useApiRequest`. Replace the quoted function with the new one from Step 3, and the `isUnauthorized` helper. Keep the surrounding prose. If the prose says the transport "sends whatever `getToken` returns", add one sentence: "A 401 is retried once with a fresh token, then signs out (see `web-app.md`)."

- [ ] **Step 6: Commit**

```bash
git add web-app/packages/api-client/src/use-api-fetch.ts web-app/packages/api-client/src/use-api-fetch.test.ts docs/architecture/web-app.md docs/architecture/authentication.md docs/guides/api-client-codegen.md
git commit -m "API client: retry a 401 once with a fresh token, then sign out"
```

---

### Task 6: Income and expenses get their own colours

**Files:**
- Modify: `web-app/packages/ui/src/styles/globals.css` (`@theme inline`, `:root`, `.dark`)
- Modify: `web-app/apps/web/src/components/dashboard/trend-chart.tsx:15-18`

**Interfaces:**
- Produces: CSS tokens `--chart-income`, `--chart-expense`, and Tailwind colours `chart-income`, `chart-expense`. 5b's analytics charts use these for every income or expense mark.

No unit test: the change is a token value. The validator run below and the screenshot in Task 7 are the checks.

- [ ] **Step 1: Re-run the validator on the app's card surfaces**

Run:
```bash
V=/private/tmp/claude-501/bundled-skills/2.1.300/5347fe2a4a170d3fc06b849345394522/dataviz/scripts/validate_palette.js
node $V "#008300,#6250d6" --mode light --surface "#ffffff"
node $V "#008300,#9085e9" --mode dark --surface "#161b1d"
```
Expected: `ALL CHECKS PASS` for both. If the path is gone, run `ls /private/tmp/claude-501/bundled-skills/*/*/dataviz/scripts/validate_palette.js` to find it. If it's missing entirely, skip this step and say so in the task report: the spec records the results from 15 Oct 2026.

- [ ] **Step 2: Add the tokens**

In `web-app/packages/ui/src/styles/globals.css`:

`@theme inline`, directly above `--color-chart-6: var(--chart-6);`:

```css
  --color-chart-income: var(--chart-income);
  --color-chart-expense: var(--chart-expense);
```

`:root`, directly after `--chart-6: #898781;`:

```css
  /* Income and expenses, wherever they appear: a pair no category slot uses (dataviz-validated). */
  --chart-income: #008300;
  --chart-expense: #6250d6;
```

`.dark`, directly after `--chart-6: #898781;`:

```css
  --chart-income: #008300;
  --chart-expense: #9085e9;
```

- [ ] **Step 3: Use them in the trend chart**

`web-app/apps/web/src/components/dashboard/trend-chart.tsx`:

```tsx
const config: ChartConfig = {
  income: { label: "Income", color: "var(--chart-income)" },
  expenses: { label: "Expenses", color: "var(--chart-expense)" },
}
```

The lines read `var(--color-income)` and `var(--color-expenses)`, which `ChartContainer` derives from this config. The legend reads `item.color`. Nothing else changes.

Check that nothing else on the dashboard draws income or expenses. `grep -rn "chart-1\|chart-2" web-app/apps/web/src` must show only `category-slices.ts` and its test (the donut, which is right).

- [ ] **Step 4: Run the checks**

Run: `cd web-app && pnpm -s vitest run apps/web/src/components/dashboard && pnpm -s type-check && pnpm -s lint && pnpm -s format:check`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web-app/packages/ui/src/styles/globals.css web-app/apps/web/src/components/dashboard/trend-chart.tsx
git commit -m "Dashboard: income and expenses get their own validated colours"
```

---

### Task 7: Hand checks, docs cleanup, gates (the controller runs this)

Not dispatched to a subagent: it needs the running stack, a real sign-in and the user.

**Files:**
- Modify: `docs/BUGS.md` (delete the entry "The first page load after sign-in fires its queries without a token")
- Modify: `docs/TODO.md` (delete the `LLMService` bullet and the date-range bullet under "Server — CSV import follow-ups", and the section "Web — dedicated income and expense colours"; add the two out-of-scope findings)
- Modify: `docs/architecture/authentication.md` (only if the repro shows a different mechanism)

- [ ] **Step 1: Start this worktree's stack.** Follow the `worktrees` and `run-stack` skills: the worktree's own port slot and database, migrations applied.

- [ ] **Step 2: Repro the sign-in race by hand.** Sign out, sign in, land on `/transactions`. Then repeat, landing on `/home`. Expected: data on the first render, no "Something went wrong", and no `no_auth_header_present` in the server log for those requests. In the browser, record whether `isLoaded` was false or `isSignedIn` was false during the wait. If it wasn't "Clerk navigates before the session is installed", correct the sentence added to `authentication.md` §2. The user may need to type their password; ask them in this tab.

- [ ] **Step 3: Check the 401 path by hand.** Signed in on `/home`, end the session from another tab (sign out there). Trigger a query in the first tab (navigate to `/transactions`). Expected: it lands on `/sign-in` within a few seconds and doesn't loop back.

- [ ] **Step 4: Check the colours.** Screenshot `/home` in light and dark mode. The trend chart's lines and legend are green and violet, and the donut beside it keeps its own slots.

- [ ] **Step 5: Check the import.** Upload a CSV with a row dated `2205-03-01`. The review lists it as `date out of range “2205-03-01”`.

- [ ] **Step 6: Docs cleanup.** Delete the `BUGS.md` entry and the three `TODO.md` entries listed above. If a TODO section ends up empty, delete its heading too. Add to `TODO.md`, in the sections that fit:
  - Server: "A transaction added by hand is not held to `MIN_DATE`/`MAX_DATE` (`transaction/domain/dates.py`), so a typo year drops out of every chart without a word, as the import's did."
  - Server: "After an LLM fallback, the chatbot's inference-time metric label and its stored model name are the default model's (`current_model_name()`), not the one that answered. The answering model is in the response's `response_metadata`."

  Commit: `Docs: close the sign-in 401 bug and three TODOs; record two findings`.

- [ ] **Step 7: Gates.** From the root: `make check`, `make test-web`, `cd server && APP_ENV=test uv run pytest tests/unit -m unit -q && APP_ENV=test uv run pytest tests/integration -m integration -q`, `make check-contract`. All must pass before the push.

- [ ] **Step 8: At the PR** (`superpowers:finishing-a-development-branch`, PR into `template-base`): set the roadmap row to `complete — [PR #N](url) into template-base; reaches main at Cutover`; delete this plan and the spec; comment the PR link on https://github.com/tiziaco/fullstack-b2b-nextjs-fastapi-template/issues/12, with what the hand repro showed about the mechanism; report to `orchestrator` with the URL and gate results.
