# Chat Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A chat screen on the existing `conversation` module: list, start, rename and delete conversations, stream replies with Stop, LLM-written titles. The stream stops the model call on a client disconnect (WS7), and every LLM call goes through OpenRouter.

**Architecture:**
- **Server.** The FastAPI side gets four fixes and two additions:
  - fixes: the SSE route moves onto `sse-starlette`; the agent stream yields only the model's text; the history no longer fails on its own content; the list returns newest first
  - additions: a title endpoint, and the OpenRouter switch in the LLM registry, mem0 and evals
- **Web.** A `(dashboard)/chat` route uses assistant-ui's `ExternalStoreRuntime` and headless primitives.
  - TanStack Query (the generated hooks) stays the source of truth for conversations and history.
  - A hand-written SSE `fetch` client streams the in-flight reply.

**Tech Stack:** FastAPI, LangGraph, mem0 2.0.20, sse-starlette, pytest. Next.js 16, React 19, TanStack Query 5, orval-generated client, `@assistant-ui/react` 0.15.x, `@assistant-ui/react-markdown`, `remark-gfm`, Vitest + Testing Library.

**Spec:** `.superpowers/specs/2026-10-13-chat-screen-design.md`. Read it before any task.

## Global Constraints

These come from the brief and the spec. Every task obeys them.

- Add no file under `server/alembic/versions/`, and do not edit `server/alembic/env.py`.
- Do not touch:
  - `server/app/modules/account/`
  - `server/app/modules/conversation/handlers.py`
  - `server/app/main.py`
  - `server/app/api/v1/api.py`
  - the `[tool.importlinter]` contracts
  - anything under `server/app/api/middlewares/`
- `server/pyproject.toml`: the only change is the `sse-starlette` line in `[project].dependencies`. `version` does not change.
- The stream route keeps:
  - path `/chat/{conversation_id}/stream`
  - `operation_id="streamChatMessage"`
  - `tags=["streaming"]`
  - the event shape `{"content": str, "done": bool}`
  - no `response_class`
- Do not change the inset container in `web-app/apps/web/src/app/(dashboard)/layout.tsx`.
- Server test fixtures: do not edit an existing fixture in any `conftest.py`. New fixtures go in the test file that uses them, or beside the existing ones.
- Generated files change only through their tools:
  - `server/openapi.json` and `web-app/packages/api-client/src/generated/`: `make gen-contract`
  - `server/uv.lock`: `uv add` / `uv lock`
  - `pnpm-lock.yaml`: `pnpm add` / `pnpm install`
- Web:
  - Never render `ApiError.message`, `ApiError.body` or server-authored text.
  - Error copy comes from `@app/core/constants/messages` or the chat copy in this plan.
  - Use Base UI's `render` prop on `@app/ui` triggers, never Radix `asChild`. assistant-ui primitives accept `asChild`.
- Pin new web dependencies exactly (`--save-exact`).
- Commit messages: imperative, prefixed (`feat(chat): …`, `fix(agents): …`, `test: …`, `docs: …`).
- Commands:
  - Server tests run from `server/`: `uv run pytest <path> -v`. Integration tests need Docker running.
  - Web tests run from `web-app/`: `pnpm vitest run <path>`.
  - Before every commit that touches `server/app/`, run `make gen-contract` from the repo root. The pre-commit hook blocks on drift.
- Before writing tests, read the project skills: `server-testing` for server tests, `web-app-testing` and `web-app-patterns` for web work, `server-patterns` for server routes and services.

## Review Focus

The spec implies these, but no happy-path test covers them. Each one has a test in the task named.

1. **Switching conversation mid-stream.** Clicking another conversation, or "New chat", while a reply streams aborts that stream. The reply doesn't appear in the other conversation, and the next send works. → Task 10
2. **A stream that ends without `done`.** For example a proxy timeout or a dropped connection. It ends in the error state, not an endless "running". → Task 7
3. **Stream start rejected with an HTTP error** (429 rate limit, 404). It toasts the status copy, shows no in-flight bubbles, and puts the typed text back in the composer. → Task 10
4. **Rename to empty or whitespace.** It sends no request and restores the old name. A name over 100 characters can't be typed. → Task 11
5. **Opening `/chat/<unknown or foreign id>`.** It shows "This conversation doesn't exist" and a link to a new chat. It doesn't show an endless skeleton or an empty composer that would post into a 404. → Task 12

---

## File map

**Server**

| File | Change |
|---|---|
| `server/app/agents/messages.py` | `Message` loses the 3,000 cap and the input validator |
| `server/app/modules/conversation/schemas.py` | `ChatRequest` gains the script-tag and null-byte validator |
| `server/app/agents/base/agent.py` | `get_stream_response` yields only AI text; new `_chunk_text` |
| `server/app/modules/conversation/router/chatbot.py` | `EventSourceResponse`, disconnect logging |
| `server/app/modules/conversation/repository.py`, `service.py` | newest-first list; `generate_title` |
| `server/app/modules/conversation/router/conversation.py` | `POST …/title` route |
| `server/app/agents/chatbot/title.py` (new) | title prompt, `clean_title`, `generate_title` |
| `server/app/agents/chatbot/graph.py` | `ChatbotAgent.generate_title` delegates to `title.py` |
| `server/app/core/config.py` | OpenRouter settings (inside `LLMSettings`, `MemorySettings`, `EvaluationSettings` only) |
| `server/app/integrations/llm/service.py` | `openai/…` registry names, `base_url` |
| `server/app/agents/shared/memory/factory.py` | mem0 LLM and embedder via OpenRouter |
| `server/.env.example`, `server/scripts/build-docker.sh`, `server/scripts/docker-entrypoint.sh` | key rename |

**Web**

| File | Change |
|---|---|
| `packages/api-client/src/toast-for-error.ts` (new), `query-provider.tsx`, `use-api-fetch.ts`, `index.ts` | export `toastForError` and `resolveBaseUrl` |
| `apps/web/src/lib/chat/stream-chat.ts` (new) | SSE client |
| `apps/web/src/components/chat/*` (new) | `copy.ts`, `markdown-text.tsx`, `chat-message.tsx`, `composer.tsx`, `thread.tsx`, `chat-runtime-provider.tsx`, `conversation-list.tsx`, `conversation-row.tsx`, `chat-shell.tsx` |
| `apps/web/src/app/(dashboard)/chat/*` (new) | `layout.tsx`, `page.tsx`, `[conversationId]/page.tsx`, `loading.tsx` |
| `apps/web/src/lib/hub-nav.ts` | Chat entry |

**Docs:** `docs/product/features/chat.md`, `docs/data-model/conversation.md`, `docs/TODO.md`, `docs/architecture/web-app.md`, `docs/ROADMAP.md`, root `CLAUDE.md`, `server/CLAUDE.md`, `server/README.md`.

---

### Task 1: History cannot fail on its own content (S3)

**Files:**
- Modify: `server/app/agents/messages.py`
- Modify: `server/app/modules/conversation/schemas.py` (`ChatRequest`)
- Test: `server/tests/unit/agents/test_messages.py`, `server/tests/unit/modules/conversation/test_schemas.py`, `server/tests/integration/modules/conversation/router/test_chatbot.py`

**Interfaces:**
- Produces:
  - `Message(role, content)`: `content` is `str` with `min_length=1` and no other rule.
  - `ChatRequest.message` keeps its 1–3,000 length, and now rejects `<script…>…</script>` and `\0`. A rejection is a 422 at the route.

- [ ] **Step 1: Write the failing tests**

In `server/tests/unit/agents/test_messages.py`:
- Delete `test_script_tag_rejected`, `test_null_bytes_rejected`, `test_max_length_boundary` and `test_over_max_length_rejected`. Those rules move to `ChatRequest`.
- Add:

```python
    def test_long_assistant_reply_accepted(self):
        """History carries whole replies, and a reply has no 3,000-character cap."""
        msg = Message(role="assistant", content="a" * 10_000)
        assert len(msg.content) == 10_000

    def test_reply_quoting_a_script_tag_accepted(self):
        """A reply may quote markup in a code block; input rules apply to ChatRequest, not here."""
        msg = Message(role="assistant", content="```html\n<script>alert(1)</script>\n```")
        assert "<script>" in msg.content
```

In `server/tests/unit/modules/conversation/test_schemas.py`, add the import `from app.modules.conversation.schemas import ChatRequest` if it isn't there, plus `import pytest` and `from pydantic import ValidationError`. Then add:

```python
class TestChatRequestInputRules:
    """The rules on what a user may send live on the request, not on Message."""

    def test_script_tag_rejected(self):
        with pytest.raises(ValidationError, match="script"):
            ChatRequest(message="<script>alert('xss')</script>")

    def test_null_bytes_rejected(self):
        with pytest.raises(ValidationError, match="null bytes"):
            ChatRequest(message="hello\0world")

    def test_max_length_boundary(self):
        assert len(ChatRequest(message="a" * 3000).message) == 3000

    def test_over_max_length_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="a" * 3001)
```

In `server/tests/integration/modules/conversation/router/test_chatbot.py`, add to `TestGetChatHistory`:

```python
    async def test_long_reply_in_history_returns_200(
        self, authenticated_client_with_agent, test_conversation, mock_agent
    ):
        from app.agents.messages import Message

        mock_agent.get_chat_history.return_value = [
            Message(role="user", content="Explain budgeting"),
            Message(role="assistant", content="x" * 5000),
        ]
        response = await authenticated_client_with_agent.get(f"/api/v1/chatbot/chat/{test_conversation.id}/messages")
        assert response.status_code == 200
        assert len(response.json()["messages"][1]["content"]) == 5000
```

Add to `TestChatEndpoint`:

```python
    async def test_chat_script_tag_returns_422(self, authenticated_client_with_agent, test_conversation):
        response = await authenticated_client_with_agent.post(
            f"/api/v1/chatbot/chat/{test_conversation.id}",
            json={"message": "<script>alert(1)</script>"},
        )
        assert response.status_code == 422
```

Note: `mock_agent.get_chat_history.return_value = …` mutates the per-test `MagicMock`. It doesn't edit the fixture.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd server && uv run pytest tests/unit/agents/test_messages.py tests/unit/modules/conversation/test_schemas.py tests/integration/modules/conversation/router/test_chatbot.py -v`

Expected:
- FAIL: `test_long_assistant_reply_accepted`, `test_reply_quoting_a_script_tag_accepted`, `test_script_tag_rejected`, `test_null_bytes_rejected`
- `test_chat_script_tag_returns_422`: FAIL, or ERROR with a 500

- [ ] **Step 3: Implement**

Replace the body of `server/app/agents/messages.py` with:

```python
"""The chat message exchanged with an agent — the shape every agent's history uses."""

from typing import (
    Literal,
)

from pydantic import (
    BaseModel,
    Field,
)


class Message(BaseModel):
    """One message in an agent's history.

    Output shape only. The rules on what a user may send (length, script tags,
    null bytes) live on `ChatRequest`: applied here they also judged the
    assistant's replies, so a long answer, or one quoting `<script>` in a code
    block, turned the history route into a 500.

    Attributes:
        role: The role of the message sender (user, assistant or system).
        content: The content of the message.
    """

    model_config = {"extra": "ignore"}

    role: Literal["user", "assistant", "system"] = Field(..., description="The role of the message sender")
    content: str = Field(..., description="The content of the message", min_length=1)
```

In `server/app/modules/conversation/schemas.py`:
- Add `import re` and `field_validator` to the pydantic import.
- Give `ChatRequest` the validator:

```python
    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        """Reject script tags and null bytes in what the user sends."""
        if re.search(r"<script.*?>.*?</script>", v, re.IGNORECASE | re.DOTALL):
            raise ValueError("Content contains potentially harmful script tags")
        if "\0" in v:
            raise ValueError("Content contains null bytes")
        return v
```

- [ ] **Step 4: Run the tests to verify they pass**

Run the same command as Step 2. Expected: all PASS.

- [ ] **Step 5: Regenerate the contract and commit**

```bash
make gen-contract
git add server/app/agents/messages.py server/app/modules/conversation/schemas.py server/tests/unit/agents/test_messages.py server/tests/unit/modules/conversation/test_schemas.py server/tests/integration/modules/conversation/router/test_chatbot.py server/openapi.json web-app/packages/api-client/src/generated
git commit -m "fix(chat): input rules move to ChatRequest so history cannot 500 on a long reply"
```

---

### Task 2: Stream only the model's text (S2)

**Files:**
- Modify: `server/app/agents/base/agent.py` (`get_stream_response`, new module-level `_chunk_text`)
- Test: `server/tests/unit/agents/test_base_agent.py` (new)

**Interfaces:**
- Produces: `BaseAgent.get_stream_response(...)` yields `str` chunks of AI-message text only. It never yields `ToolMessage` content, and never yields an empty string.

- [ ] **Step 1: Write the failing test**

Create `server/tests/unit/agents/test_base_agent.py`:

```python
"""Tests for BaseAgent.get_stream_response — what reaches the client's stream."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessageChunk, ToolMessage

from app.agents.base.agent import BaseAgent, _chunk_text
from app.agents.messages import Message

pytestmark = pytest.mark.unit


class _Agent(BaseAgent):
    async def create_graph(self, checkpointer):  # pragma: no cover - not used
        raise NotImplementedError


class _FakeGraph:
    """Emits what LangGraph's stream_mode="messages" emits: (message, metadata) pairs."""

    def __init__(self, items):
        self._items = items

    async def astream(self, *args, **kwargs):
        for item in self._items:
            yield item, {}

    async def aget_state(self, config):
        return SimpleNamespace(values={})


async def _collect(items) -> list[str]:
    agent = _Agent()
    agent._graph = _FakeGraph(items)
    with (
        patch("app.agents.base.agent.get_relevant_memory", new=AsyncMock(return_value="")),
        patch("app.agents.base.agent.update_memory", new=AsyncMock()),
    ):
        return [
            chunk
            async for chunk in agent.get_stream_response(
                [Message(role="user", content="hi")], uuid.uuid4(), user_id=uuid.uuid4()
            )
        ]


@pytest.mark.asyncio
async def test_tool_results_are_not_streamed():
    """A web-search result is a ToolMessage: it must not reach the user as reply text."""
    chunks = await _collect(
        [
            AIMessageChunk(content="Let me check. "),
            ToolMessage(content="RAW SEARCH RESULTS", tool_call_id="call_1"),
            AIMessageChunk(content="It is sunny."),
        ]
    )
    assert chunks == ["Let me check. ", "It is sunny."]


@pytest.mark.asyncio
async def test_empty_and_tool_call_chunks_are_skipped():
    chunks = await _collect([AIMessageChunk(content=""), AIMessageChunk(content="Hi")])
    assert chunks == ["Hi"]


@pytest.mark.asyncio
async def test_structured_content_is_flattened_to_text():
    """GPT-5 models stream content as a list of blocks; only text blocks are the answer."""
    chunks = await _collect(
        [AIMessageChunk(content=[{"type": "reasoning", "id": "r1"}, {"type": "text", "text": "Hello"}])]
    )
    assert chunks == ["Hello"]


def test_chunk_text_handles_strings_and_blocks():
    assert _chunk_text("plain") == "plain"
    assert _chunk_text([{"type": "text", "text": "a"}, "b", {"type": "reasoning"}]) == "ab"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd server && uv run pytest tests/unit/agents/test_base_agent.py -v`
Expected: ImportError on `_chunk_text`. Once that exists, `test_tool_results_are_not_streamed` fails with `"RAW SEARCH RESULTS"` in the output.

- [ ] **Step 3: Implement**

In `server/app/agents/base/agent.py`, import `AIMessage` from `langchain_core.messages` (alongside `BaseMessage`) and add this above the class:

```python
def _chunk_text(content: str | list) -> str:
    """The text of a streamed message's content, which GPT-5 models send as a list of blocks."""
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)
```

Replace the inner loop of `get_stream_response`:

```python
            async for token, _ in self._graph.astream(
                {"messages": dump_messages(messages), "long_term_memory": relevant_memory},
                config=config,
                stream_mode="messages",
            ):
                # stream_mode="messages" emits every message a node produces,
                # tool results included. Only the model's own text is the reply.
                if not isinstance(token, AIMessage):
                    continue
                text = _chunk_text(token.content)
                if text:
                    yield text
```

Remove the old inner `try/except` around `yield token.content`. `_chunk_text` can't raise on well-formed content, and a malformed token now surfaces instead of being swallowed. `AIMessageChunk` subclasses `AIMessage`, so both streamed chunks and a non-streamed final message pass the check.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd server && uv run pytest tests/unit/agents -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
make gen-contract
git add server/app/agents/base/agent.py server/tests/unit/agents/test_base_agent.py
git commit -m "fix(agents): stream only the model's text, not tool results"
```

---

### Task 3: WS7 — stop the stream on a client disconnect (S1)

**Files:**
- Modify: `server/pyproject.toml` (through `uv add` only), `server/uv.lock`
- Modify: `server/app/modules/conversation/router/chatbot.py`
- Test: `server/tests/integration/modules/conversation/router/test_chatbot.py`

**Interfaces:**
- Consumes: `agent.get_stream_response(...)` from Task 2.
- Produces: the wire format is unchanged. Each event is `data: {"content": "...", "done": false}\n\n`, and the last is `data: {"content": "", "done": true}\n\n`. The server may also send `: ping` comment lines.

- [ ] **Step 1: Add the dependency**

```bash
cd server && uv add sse-starlette
```

Check that `git diff pyproject.toml` shows exactly one added line in `[project].dependencies` and no `version` change.

- [ ] **Step 2: Write the failing tests**

Add to `server/tests/integration/modules/conversation/router/test_chatbot.py`, with `import asyncio` at the top:

```python
class TestStreamWireFormat:
    """The event shape is a published interface: WS7 must not move it."""

    async def test_events_are_byte_identical(self, authenticated_client_with_agent, test_conversation, mock_agent):
        async def mock_stream(*args, **kwargs):
            yield "Hi"
            yield " there"

        mock_agent.get_stream_response = mock_stream

        response = await authenticated_client_with_agent.post(
            f"/api/v1/chatbot/chat/{test_conversation.id}/stream",
            json={"message": "Hello"},
        )
        frames = [f for f in response.text.split("\n\n") if f and not f.startswith(":")]
        assert frames == [
            'data: {"content": "Hi", "done": false}',
            'data: {"content": " there", "done": false}',
            'data: {"content": "", "done": true}',
        ]

    async def test_failure_is_a_final_event_with_content(
        self, authenticated_client_with_agent, test_conversation, mock_agent
    ):
        async def failing_stream(*args, **kwargs):
            yield "partial"
            raise RuntimeError("model down")

        mock_agent.get_stream_response = failing_stream

        response = await authenticated_client_with_agent.post(
            f"/api/v1/chatbot/chat/{test_conversation.id}/stream",
            json={"message": "Hello"},
        )
        frames = [f for f in response.text.split("\n\n") if f and not f.startswith(":")]
        assert frames[-1] == 'data: {"content": "An error occurred. Please try again.", "done": true}'


class TestStreamClientDisconnect:
    """WS7: a client that leaves mid-stream stops the model call."""

    async def test_disconnect_cancels_the_agent_stream(
        self, authenticated_client_with_agent, test_conversation, mock_agent
    ):
        from app.main import app

        first_chunk_sent = asyncio.Event()
        cancelled = asyncio.Event()

        async def slow_stream(*args, **kwargs):
            try:
                yield "first"
                first_chunk_sent.set()
                await asyncio.sleep(30)  # a model still generating
                yield "never"
            except asyncio.CancelledError:
                cancelled.set()
                raise

        mock_agent.get_stream_response = slow_stream

        body = b'{"message": "Hello"}'
        request_sent = False

        async def receive():
            nonlocal request_sent
            if not request_sent:
                request_sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            await first_chunk_sent.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            pass

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": f"/api/v1/chatbot/chat/{test_conversation.id}/stream",
            "raw_path": f"/api/v1/chatbot/chat/{test_conversation.id}/stream".encode(),
            "root_path": "",
            "query_string": b"",
            "headers": [(b"host", b"test"), (b"content-type", b"application/json")],
            "client": ("127.0.0.1", 12345),
            "server": ("test", 80),
        }

        await asyncio.wait_for(app(scope, receive, send), timeout=5)
        assert cancelled.is_set()
```

`authenticated_client_with_agent` is requested for its dependency overrides (auth, DB session, agent), which live on `app`. The test drives `app` directly because httpx's ASGI transport can't send `http.disconnect` mid-response.

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd server && uv run pytest tests/integration/modules/conversation/router/test_chatbot.py -v -k "Stream"`

Expected:
- `test_disconnect_cancels_the_agent_stream`: fails. Either it times out (`TimeoutError` after 5s, because `StreamingResponse` keeps generating), or `cancelled` is unset.
- The wire-format tests: should already pass. They pin the shape before the change.

- [ ] **Step 4: Implement**

In `server/app/modules/conversation/router/chatbot.py`:
- Add `import asyncio`.
- Replace `from fastapi.responses import StreamingResponse` with `from sse_starlette import EventSourceResponse`. If the installed version only exposes `sse_starlette.sse`, import from there.
- Rewrite `event_generator` and the return:

```python
    async def event_generator():
        """Yield the response as server-sent events, one JSON payload per chunk.

        Run by EventSourceResponse, which cancels this generator when the client
        disconnects. The CancelledError travels down into the agent and the HTTP
        call to the model, which is what stops a call nobody is waiting for.
        """
        try:
            full_response = ""
            user_message = Message(role="user", content=chat_request.message)
            with llm_stream_duration_seconds.labels(model=agent.llm_service.current_model_name()).time():
                async for chunk in agent.get_stream_response([user_message], conversation.id, user_id=user.id):
                    full_response += chunk
                    response = StreamResponse(content=chunk, done=False)
                    yield {"data": json.dumps(response.model_dump())}

            final_response = StreamResponse(content="", done=True)
            yield {"data": json.dumps(final_response.model_dump())}

        except asyncio.CancelledError:
            logger.info("stream_chat_client_disconnected", conversation_id=conversation.id)
            raise

        except Exception as e:
            logger.error(
                "stream_chat_request_failed",
                conversation_id=conversation.id,
                error=str(e),
                exc_info=True,
            )
            error_response = StreamResponse(content="An error occurred. Please try again.", done=True)
            yield {"data": json.dumps(error_response.model_dump())}

    # sep="\n" keeps the frames byte-identical to the StreamingResponse this replaced.
    return EventSourceResponse(event_generator(), sep="\n")
```

Leave the decorator, path, `operation_id`, tags and the `@limiter.limit` line untouched.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd server && uv run pytest tests/integration/modules/conversation/router/test_chatbot.py -v`
Expected: all PASS.

If the disconnect test still times out, sse-starlette isn't seeing the disconnect through the middleware stack. Do not change `server/app/api/middlewares/`. Report it as BLOCKED with the observed behaviour.

- [ ] **Step 6: Prove the contract did not move, and commit**

```bash
make gen-contract && git diff --stat server/openapi.json
```

Expected: no change to `server/openapi.json`.

```bash
git add server/pyproject.toml server/uv.lock server/app/modules/conversation/router/chatbot.py server/tests/integration/modules/conversation/router/test_chatbot.py
git commit -m "fix(chat): stop the model call when the stream's client disconnects (WS7)"
```

---

### Task 4: List conversations newest first (S5)

**Files:**
- Modify: `server/app/modules/conversation/repository.py` (`list_active_for_user`), `server/app/modules/conversation/service.py` (`get_user_conversations` docstring)
- Test: `server/tests/integration/modules/conversation/test_repository.py`, plus any existing test asserting oldest-first (`grep -rn "oldest\|order" server/tests/integration/modules/conversation`)

**Interfaces:**
- Produces: `GET /api/v1/conversation/conversations` returns rows ordered by `created_at` descending.

- [ ] **Step 1: Write the failing test**

Add to `server/tests/integration/modules/conversation/test_repository.py`, using the file's existing user fixture or creating a `User` the way the file already does:

```python
async def test_list_active_for_user_is_newest_first(db_session, test_user):
    from datetime import datetime, timedelta, timezone

    from app.modules.conversation.models import Conversation
    from app.modules.conversation.repository import conversation_repository

    base = datetime(2026, 10, 1, tzinfo=timezone.utc)
    for i, name in enumerate(["first", "second", "third"]):
        conv = Conversation(user_id=test_user.id, name=name)
        conv.created_at = base + timedelta(minutes=i)
        db_session.add(conv)
    await db_session.flush()

    rows = await conversation_repository.list_active_for_user(db_session, test_user.id)
    assert [r.name for r in rows] == ["third", "second", "first"]
```

If any existing test asserts oldest-first, update it to newest-first in this step.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd server && uv run pytest tests/integration/modules/conversation -v`
Expected: the new test FAILS (`["first", "second", "third"]`).

- [ ] **Step 3: Implement**

`repository.py`:
- `.order_by(Conversation.created_at.desc())`
- Docstring: `"""A user's non-soft-deleted conversations, newest first — the order `GET /conversations` publishes."""`

`service.py`: the docstring of `get_user_conversations` becomes `"""Get a user's active conversations, newest first."""`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd server && uv run pytest tests/integration/modules/conversation -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
make gen-contract
git add server/app/modules/conversation/repository.py server/app/modules/conversation/service.py server/tests/integration/modules/conversation
git commit -m "feat(chat): list conversations newest first"
```

---

### Task 5: OpenRouter for every LLM call (S6)

**Files:**
- Modify: `server/app/core/config.py`. Edit only inside `LLMSettings`, `MemorySettings` and `EvaluationSettings`.
- Modify: `server/app/integrations/llm/service.py` (`LLMRegistry.LLMS`, `_build`)
- Modify: `server/app/agents/shared/memory/factory.py` (`_memory_llm_config`, embedder config in `create_memory`)
- Modify: `server/.env.example`. The user already changed the LLM block in the working tree; keep their lines and commit them.
- Modify: `server/scripts/build-docker.sh:66`, `server/scripts/docker-entrypoint.sh:57`
- Modify: root `CLAUDE.md` (Environment Setup), `server/CLAUDE.md:227-230`, `server/README.md:29`
- Modify: every model-name reference to the bare registry names in `server/app` and `server/evals`. Find them with `grep -rn '"gpt-' server/app server/evals`.
- Test: `server/tests/unit/integrations/llm/test_registry.py`, `test_service.py`, `test_service_import.py`, `server/tests/unit/agents/memory/test_memory_factory.py`, `server/tests/unit/config/test_settings.py`

**Interfaces:**
- Produces:
  - `settings.llm.OPENROUTER_API_KEY: SecretStr`
  - `settings.llm.LLM_BASE_URL: str` (default `"https://openrouter.ai/api/v1"`)
  - `settings.llm.DEFAULT_LLM_MODEL` default `"openai/gpt-5-mini"`
  - Registry names: `openai/gpt-5-mini`, `openai/gpt-5`, `openai/gpt-5-nano`, `openai/gpt-4o`, `openai/gpt-4o-mini`
  - `LLMRegistry.get(name)` returns a `ChatOpenAI` whose `openai_api_base == settings.llm.LLM_BASE_URL`
  - `settings.llm.OPENAI_API_KEY` no longer exists.

- [ ] **Step 1: Write the failing tests**

In `server/tests/unit/integrations/llm/test_registry.py`:
- Replace every `"gpt-5-mini"` / `"gpt-5"` with `"openai/gpt-5-mini"` / `"openai/gpt-5"`.
- Add:

```python
class TestLLMRegistryProvider:
    """Every client talks to OpenRouter."""

    def test_client_points_at_the_configured_base_url(self):
        from app.core.config import settings

        llm = LLMRegistry.get("openai/gpt-5-mini")
        assert llm.openai_api_base == settings.llm.LLM_BASE_URL

    def test_base_url_defaults_to_openrouter(self):
        from app.core.config import LLMSettings

        assert LLMSettings.model_fields["LLM_BASE_URL"].default == "https://openrouter.ai/api/v1"

    def test_every_registry_name_is_an_openrouter_model_id(self):
        assert all(name.startswith("openai/") for name in LLMRegistry.get_all_names())
```

In `server/tests/unit/integrations/llm/test_service.py`: update the model names the same way, wherever a test names one.

In `server/tests/unit/integrations/llm/test_service_import.py`: `OPENAI_API_KEY` becomes `OPENROUTER_API_KEY` in the docstring and in `env = {**os.environ, "OPENROUTER_API_KEY": ""}`.

In `server/tests/unit/agents/memory/test_memory_factory.py`:
- Update any bare `gpt-5…` model names the tests pass in. The parametrized `_memory_llm_config` tests may keep bare names, since the function strips a `provider/` prefix. Add one case with `"openai/gpt-5-nano"` to that parametrization.
- Add:

```python
@pytest.mark.asyncio
async def test_llm_and_embedder_both_go_through_openrouter(monkeypatch):
    """mem0 gets the OpenRouter key and base URL explicitly, not OPENAI_API_KEY from the environment."""
    from unittest.mock import MagicMock

    from app.agents.shared.memory import factory
    from app.core.config import settings

    monkeypatch.setattr(factory, "_memory_instance", None)
    from_config = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(factory.AsyncMemory, "from_config", from_config)

    await factory.create_memory()

    config = from_config.call_args.kwargs["config_dict"]
    key = settings.llm.OPENROUTER_API_KEY.get_secret_value()
    assert config["llm"]["config"]["api_key"] == key
    assert config["llm"]["config"]["openai_base_url"] == settings.llm.LLM_BASE_URL
    assert config["llm"]["config"]["openrouter_base_url"] == settings.llm.LLM_BASE_URL
    assert config["embedder"]["config"]["api_key"] == key
    assert config["embedder"]["config"]["openai_base_url"] == settings.llm.LLM_BASE_URL
    assert config["embedder"]["config"]["model"] == "openai/text-embedding-3-small"
```

If the existing tests patch `from_config` differently, for example positionally, follow their pattern and read the `config_dict` the same way.

In `server/tests/unit/config/test_settings.py`, add:

```python
def test_evaluation_key_falls_back_to_the_openrouter_key(monkeypatch):
    from app.core.config import EvaluationSettings

    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.delenv("EVALUATION_API_KEY", raising=False)
    assert EvaluationSettings().API_KEY.get_secret_value() == "or-key"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd server && uv run pytest tests/unit/integrations/llm tests/unit/agents/memory tests/unit/config -v`
Expected: FAIL on the new and renamed cases.

- [ ] **Step 3: Implement config**

In `server/app/core/config.py`, `LLMSettings`:

```python
    OPENROUTER_API_KEY: SecretStr = Field(default=SecretStr(""))
    # Every LLM call (agent, titles, mem0, evals) goes through OpenRouter's
    # OpenAI-compatible API; model names are OpenRouter ids such as "openai/gpt-5-mini".
    LLM_BASE_URL: str = "https://openrouter.ai/api/v1"
    DEFAULT_LLM_MODEL: str = "openai/gpt-5-mini"
```

`OPENAI_API_KEY` is removed. Keep the other fields.

`MemorySettings`: `MODEL: str = "openai/gpt-5-nano"` and `EMBEDDER_MODEL: str = "openai/text-embedding-3-small"`.

`EvaluationSettings`:

```python
    LLM: str = "openai/gpt-5"
    BASE_URL: str = "https://openrouter.ai/api/v1"
    API_KEY: SecretStr = Field(default=SecretStr(""))
    SLEEP_TIME: int = 10

    @field_validator("API_KEY", mode="before")
    @classmethod
    def default_to_openrouter_key(cls, v):
        """Default to OPENROUTER_API_KEY if EVALUATION_API_KEY not set."""
        if not v or v == "":
            return os.getenv("OPENROUTER_API_KEY", "")
        return v
```

- [ ] **Step 4: Implement the registry**

In `server/app/integrations/llm/service.py`:
- Rename the five `LLMS` entries' `"name"` to `openai/gpt-5-mini`, `openai/gpt-5`, `openai/gpt-5-nano`, `openai/gpt-4o` and `openai/gpt-4o-mini`. Keep the params.
- `_build`:

```python
    @classmethod
    def _build(cls, model_name: str, **params) -> BaseChatModel:
        """Construct a chat model against OpenRouter. The one site that reads the credential."""
        return ChatOpenAI(
            model=model_name,
            api_key=settings.llm.OPENROUTER_API_KEY.get_secret_value(),
            base_url=settings.llm.LLM_BASE_URL,
            **params,
        )
```

Run `grep -rn '"gpt-' server/app server/evals` and prefix every remaining registry-name reference with `openai/`. Leave `tests/integration/conftest.py`'s `mock_agent` label alone: it's a fixture, and it's only a label.

- [ ] **Step 5: Implement mem0**

In `server/app/agents/shared/memory/factory.py`:

```python
def _openrouter_credentials() -> Dict[str, Any]:
    """The key and base URL every mem0 client uses.

    Passed explicitly rather than left to mem0's environment lookup. Its OpenAI
    LLM switches to OpenRouter only when OPENROUTER_API_KEY is in os.environ,
    and pydantic-settings does not put .env.<ENV> values there. Setting both
    base URLs makes either branch land on OpenRouter.
    """
    return {
        "api_key": settings.llm.OPENROUTER_API_KEY.get_secret_value(),
        "openai_base_url": settings.llm.LLM_BASE_URL,
    }
```

`_memory_llm_config` builds the config as
`config: Dict[str, Any] = {"model": settings.memory.MODEL, **_openrouter_credentials(), "openrouter_base_url": settings.llm.LLM_BASE_URL}`
and keeps the existing gpt-5 detection.

In `create_memory`, the embedder entry becomes:

```python
                "embedder": {
                    "provider": "openai",
                    "config": {"model": settings.memory.EMBEDDER_MODEL, **_openrouter_credentials()},
                },
```

- [ ] **Step 6: Env, scripts, docs**

- **`server/.env.example`** keeps the user's `OPENROUTER_API_KEY=change-me` and `DEFAULT_LLM_MODEL=openai/gpt-5-mini`.
  - Add `LLM_BASE_URL=https://openrouter.ai/api/v1` under them.
  - Change the evals comment to `# Evals (server/evals/). An empty key falls back to OPENROUTER_API_KEY.`
  - Set `EVALUATION_LLM=openai/gpt-5` and `EVALUATION_BASE_URL=https://openrouter.ai/api/v1`.
  - If memory model variables are listed, prefix them `openai/`.
- **`server/scripts/build-docker.sh:66`**: `--build-arg OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \`
- **`server/scripts/docker-entrypoint.sh:57-59`**: the comment says `OPENROUTER_API_KEY is deliberately not in the default: config.py defaults it to empty …`. The rest is unchanged.
- **Root `CLAUDE.md`, Environment Setup**: `The OpenAI key is optional` becomes `The OpenRouter key (OPENROUTER_API_KEY) is optional — every LLM call goes through OpenRouter`.
- **`server/CLAUDE.md:227-230`**: the settings example reads `settings.llm.OPENROUTER_API_KEY`.
- **`server/README.md:29`**: names `OPENROUTER_API_KEY`.

- [ ] **Step 7: Run all server unit tests**

Run: `cd server && uv run pytest tests/unit -v`
Expected: all PASS, including `test_app_imports_without_llm_credentials` and `test_module_contracts.py`.

Then check nothing still names the old key:

```bash
grep -rn "OPENAI_API_KEY" --exclude-dir=.venv --exclude-dir=node_modules --exclude-dir=.git . | grep -v "^./.superpowers"
```

Expected: no output.

- [ ] **Step 8: Commit**

```bash
make gen-contract
git add server/app/core/config.py server/app/integrations/llm/service.py server/app/agents/shared/memory/factory.py server/.env.example server/scripts/build-docker.sh server/scripts/docker-entrypoint.sh CLAUDE.md server/CLAUDE.md server/README.md server/tests/unit server/evals
git commit -m "feat(llm): route every LLM call through OpenRouter"
```

---

### Task 6: LLM-written conversation titles (S4)

**Files:**
- Create: `server/app/agents/chatbot/title.py`
- Modify: `server/app/agents/chatbot/graph.py` (`ChatbotAgent.generate_title`)
- Modify: `server/app/modules/conversation/service.py` (`generate_title`)
- Modify: `server/app/modules/conversation/router/conversation.py` (new route)
- Test: `server/tests/unit/agents/chatbot/test_title.py` (new), `server/tests/integration/modules/conversation/router/test_conversation.py`

**Interfaces:**
- Consumes:
  - `LLMRegistry.get(name)` from Task 5 (tool-free: tools are bound only by `LLMService._resolve`)
  - `process_llm_response` from `app.agents.graph`
  - `agent.get_chat_history(conversation_id) -> list[Message]`
- Produces:
  - `clean_title(raw: str) -> str`
  - `async generate_title(user_text: str, reply_text: str, model_name: str) -> str`: raises `ValueError` on an empty title, and lets model errors propagate
  - `ChatbotAgent.generate_title(user_text: str, reply_text: str) -> str`
  - `ConversationService.generate_title(session, conversation, agent) -> Conversation`
  - Route `POST /api/v1/conversation/conversation/{conversation_id}/title`, `operation_id="generateConversationTitle"`, returning `ConversationResponse`
  - After `make gen-contract`: the generated web hook `useGenerateConversationTitle` in `@app/api-client/endpoints/conversation`, with variables `{ conversationId: string }`

- [ ] **Step 1: Write the failing unit tests**

Create `server/tests/unit/agents/chatbot/test_title.py`:

```python
"""Tests for app.agents.chatbot.title — the conversation title."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.agents.chatbot.title import TITLE_MAX_LENGTH, clean_title, generate_title

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('"Monthly grocery budget"', "Monthly grocery budget"),
        ("“Rent vs. mortgage”", "Rent vs. mortgage"),
        ("Saving for a car.", "Saving for a car"),
        ("  Title: Travel fund\n", "Travel fund"),
        ("Line one\nline two", "Line one line two"),
    ],
)
def test_clean_title(raw, expected):
    assert clean_title(raw) == expected


def test_clean_title_caps_length():
    assert len(clean_title("word " * 100)) <= TITLE_MAX_LENGTH


def _fake_llm(content):
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content=content))
    return llm


@pytest.mark.asyncio
async def test_generate_title_uses_a_tool_free_client_and_cleans_the_answer():
    llm = _fake_llm('"Grocery spending in May"')
    with patch("app.agents.chatbot.title.LLMRegistry.get", return_value=llm) as get:
        title = await generate_title("How much on groceries in May?", "You spent 312 EUR.", "openai/gpt-5-mini")

    get.assert_called_once_with("openai/gpt-5-mini")
    assert title == "Grocery spending in May"
    prompt = llm.ainvoke.call_args.args[0]
    assert "How much on groceries in May?" in prompt[-1].content


@pytest.mark.asyncio
async def test_generate_title_truncates_long_inputs():
    llm = _fake_llm("Long chat")
    with patch("app.agents.chatbot.title.LLMRegistry.get", return_value=llm):
        await generate_title("u" * 5000, "r" * 5000, "openai/gpt-5-mini")
    assert len(llm.ainvoke.call_args.args[0][-1].content) < 2500


@pytest.mark.asyncio
async def test_generate_title_flattens_structured_content():
    llm = _fake_llm([{"type": "reasoning", "id": "r"}, {"type": "text", "text": "Car savings plan"}])
    with patch("app.agents.chatbot.title.LLMRegistry.get", return_value=llm):
        assert await generate_title("a", "b", "openai/gpt-5-mini") == "Car savings plan"


@pytest.mark.asyncio
async def test_empty_title_raises():
    with patch("app.agents.chatbot.title.LLMRegistry.get", return_value=_fake_llm('  ""  ')):
        with pytest.raises(ValueError):
            await generate_title("a", "b", "openai/gpt-5-mini")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd server && uv run pytest tests/unit/agents/chatbot/test_title.py -v`
Expected: ImportError (`app.agents.chatbot.title`).

- [ ] **Step 3: Implement `title.py` and the agent method**

Create `server/app/agents/chatbot/title.py`:

```python
"""A short title for a conversation, written by the model from its first exchange."""

import re

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
)

from app.agents.graph import process_llm_response
from app.integrations.llm import LLMRegistry

# The rename route's limit: a generated title must be one a user could have typed.
TITLE_MAX_LENGTH = 100
# Enough of each message to know the topic; a title needs no more.
TITLE_INPUT_LIMIT = 1000

TITLE_PROMPT = (
    "You name chat conversations. Reply with a title of at most 6 words that says what the "
    "conversation is about. Reply with the title only: no quotes, no trailing punctuation, "
    "no prefix such as 'Title:'."
)

_QUOTES = "\"'“”‘’«»`"


def clean_title(raw: str) -> str:
    """Normalise a model's title: one line, no quotes, prefix or trailing punctuation, capped."""
    title = " ".join(raw.split())
    title = re.sub(r"^title:\s*", "", title, flags=re.IGNORECASE)
    title = title.strip(_QUOTES).strip()
    title = title.rstrip(".!?:;,").strip()
    return title[:TITLE_MAX_LENGTH].rstrip()


async def generate_title(user_text: str, reply_text: str, model_name: str) -> str:
    """Ask the model for a title. Raises ValueError on an empty one; model errors propagate.

    Uses a registry client directly: `llm_service` has the chatbot's tools bound,
    and a title request must not come back as a tool call.
    """
    llm = LLMRegistry.get(model_name)
    response = await llm.ainvoke(
        [
            SystemMessage(content=TITLE_PROMPT),
            HumanMessage(
                content=f"User: {user_text[:TITLE_INPUT_LIMIT]}\n\nAssistant: {reply_text[:TITLE_INPUT_LIMIT]}"
            ),
        ]
    )
    title = clean_title(str(process_llm_response(response).content))
    if not title:
        raise ValueError("the model returned an empty title")
    return title
```

If `LLMRegistry` isn't exported from `app.integrations.llm`, add it to that package's `__init__.py` `__all__`, or import from `app.integrations.llm.service`. Either way, the patch target in the tests is `app.agents.chatbot.title.LLMRegistry.get`.

In `server/app/agents/chatbot/graph.py`, add `from app.agents.chatbot.title import generate_title` and this method on `ChatbotAgent`:

```python
    async def generate_title(self, user_text: str, reply_text: str) -> str:
        """A short title for a conversation from its first exchange, on the current model."""
        return await generate_title(user_text, reply_text, self.llm_service.current_model_name())
```

- [ ] **Step 4: Run the unit tests to verify they pass**

Run: `cd server && uv run pytest tests/unit/agents -v`
Expected: all PASS.

- [ ] **Step 5: Write the failing route tests**

Add to `server/tests/integration/modules/conversation/router/test_conversation.py`. Reuse the file's imports and add `from unittest.mock import AsyncMock` and `from app.agents.messages import Message` if missing.

```python
@pytest.fixture
async def untitled_conversation(db_session, test_user):
    from app.modules.conversation.models import Conversation

    conv = Conversation(user_id=test_user.id, name="")
    db_session.add(conv)
    await db_session.flush()
    await db_session.refresh(conv)
    return conv


class TestGenerateConversationTitle:
    """Tests for POST /api/v1/conversation/conversation/{id}/title"""

    def _url(self, conversation_id):
        return f"/api/v1/conversation/conversation/{conversation_id}/title"

    async def test_unauthenticated_returns_401(self, client, untitled_conversation):
        response = await client.post(self._url(untitled_conversation.id))
        assert response.status_code == 401

    async def test_untitled_conversation_gets_a_title(
        self, authenticated_client_with_agent, untitled_conversation, mock_agent
    ):
        mock_agent.generate_title = AsyncMock(return_value="Grocery budget")
        response = await authenticated_client_with_agent.post(self._url(untitled_conversation.id))
        assert response.status_code == 200
        assert response.json()["name"] == "Grocery budget"
        mock_agent.generate_title.assert_awaited_once_with("Hello", "Hi there!")

    async def test_named_conversation_is_unchanged(
        self, authenticated_client_with_agent, untitled_conversation, mock_agent, db_session
    ):
        untitled_conversation.name = "My name"
        await db_session.flush()
        mock_agent.generate_title = AsyncMock(return_value="Other")
        response = await authenticated_client_with_agent.post(self._url(untitled_conversation.id))
        assert response.json()["name"] == "My name"
        mock_agent.generate_title.assert_not_awaited()

    async def test_no_reply_yet_is_unchanged(self, authenticated_client_with_agent, untitled_conversation, mock_agent):
        mock_agent.get_chat_history.return_value = [Message(role="user", content="Hello")]
        mock_agent.generate_title = AsyncMock(return_value="Other")
        response = await authenticated_client_with_agent.post(self._url(untitled_conversation.id))
        assert response.status_code == 200
        assert response.json()["name"] == ""
        mock_agent.generate_title.assert_not_awaited()

    async def test_model_failure_returns_200_unchanged(
        self, authenticated_client_with_agent, untitled_conversation, mock_agent
    ):
        mock_agent.generate_title = AsyncMock(side_effect=RuntimeError("provider down"))
        response = await authenticated_client_with_agent.post(self._url(untitled_conversation.id))
        assert response.status_code == 200
        assert response.json()["name"] == ""

    async def test_other_users_conversation_returns_404(self, db_session, authenticated_client_with_agent):
        from app.modules.account.models import User
        from app.modules.conversation.models import Conversation

        other = User(clerk_id="clerk_title_other", email="title_other@example.com")
        db_session.add(other)
        await db_session.flush()
        conv = Conversation(user_id=other.id, name="")
        db_session.add(conv)
        await db_session.flush()

        response = await authenticated_client_with_agent.post(self._url(conv.id))
        assert response.status_code == 404
```

Run: `cd server && uv run pytest tests/integration/modules/conversation/router/test_conversation.py -v -k Title`
Expected: FAIL with 404/405, since the route doesn't exist yet.

- [ ] **Step 6: Implement the service and route**

In `server/app/modules/conversation/service.py`:
- Import `from app.core.logging import logger`.
- Import `from app.agents.chatbot.graph import ChatbotAgent` under `TYPE_CHECKING` only, to keep the import graph unchanged.
- Add:

```python
    @staticmethod
    async def generate_title(session: AsyncSession, conversation: Conversation, agent: "ChatbotAgent") -> Conversation:
        """Name an untitled conversation from its first exchange.

        A no-op for a named conversation or one with no reply yet. A model
        failure is logged and the conversation returned unchanged: a title is
        cosmetic, and the client asks again after the next completed reply.
        """
        if conversation.name:
            return conversation

        history = await agent.get_chat_history(conversation.id)
        user_text = next((m.content for m in history if m.role == "user"), None)
        reply_text = next((m.content for m in history if m.role == "assistant"), None)
        if not user_text or not reply_text:
            return conversation

        try:
            title = await agent.generate_title(user_text, reply_text)
        except Exception as e:
            logger.warning("conversation_title_generation_failed", conversation_id=conversation.id, error=str(e))
            return conversation

        return await conversation_repository.update_name(session, conversation, title)
```

In `server/app/modules/conversation/router/conversation.py`, import `ChatbotAgentDep` alongside `UserConversation` and add:

```python
@router.post(
    "/conversation/{conversation_id}/title",
    operation_id="generateConversationTitle",
    response_model=ConversationResponse,
    summary="Generate a conversation title",
    description=(
        "Name an untitled conversation from its first exchange. A conversation that already "
        "has a name, or has no reply yet, is returned unchanged."
    ),
)
@limiter.limit(settings.rate_limits.endpoints.CHAT[0])
async def generate_conversation_title(
    request: Request,
    conversation: UserConversation,
    db_session: DbSession,
    agent: ChatbotAgentDep,
):
    """Generate and save a title for an untitled conversation."""
    conversation = await conversation_service.generate_title(db_session, conversation, agent)

    return ConversationResponse(
        conversation_id=conversation.id,
        name=conversation.name,
        created_at=conversation.created_at,
    )
```

- [ ] **Step 7: Run all server tests**

Run: `cd server && uv run pytest tests -v`
Expected: all PASS, including `test_openapi_contract`, `test_module_contracts` and `test_owned_tables`.

- [ ] **Step 8: Regenerate the contract and commit**

```bash
make gen-contract
grep -n "useGenerateConversationTitle" web-app/packages/api-client/src/generated/endpoints/conversation/conversation.ts | head -2
git add server/app/agents/chatbot server/app/modules/conversation server/tests server/openapi.json web-app/packages/api-client/src/generated server/app/integrations/llm/__init__.py
git commit -m "feat(chat): LLM-written titles for untitled conversations"
```

---

### Task 7: The SSE client and the api-client exports (W3)

**Files:**
- Create: `web-app/packages/api-client/src/toast-for-error.ts`
- Modify: `web-app/packages/api-client/src/query-provider.tsx` (import `toastForError` instead of defining it), `src/use-api-fetch.ts` (export `resolveBaseUrl`), `src/index.ts`
- Create: `web-app/apps/web/src/lib/chat/stream-chat.ts`
- Test: `web-app/apps/web/src/lib/chat/stream-chat.test.ts`

**Interfaces:**
- Produces:
  - from `@app/api-client`: `ApiError`, `useApiFetch`, `resolveBaseUrl(): string`, `toastForError(error: unknown): void`
  - `streamChat(options: StreamChatOptions): AsyncGenerator<string>`, which yields text chunks. It throws `ApiError` on a non-2xx response, `StreamFailedError` on a failure event, a stream ending without `done`, or a malformed event, and the fetch's `AbortError` on abort.
  - `readEvents(body: ReadableStream<Uint8Array>): AsyncGenerator<StreamEvent>`
  - `class StreamFailedError extends Error`
  - `type StreamChatOptions = { conversationId: string; message: string; token: string | null; signal: AbortSignal }`

- [ ] **Step 1: Move `toastForError` and export `resolveBaseUrl`**

Create `web-app/packages/api-client/src/toast-for-error.ts` by moving the `toastForError` function out of `query-provider.tsx` verbatim. Keep its SECURITY comment, its imports (`toast` from `sonner`, `ApiError` from `./errors`, `messages` from `@app/core/constants/messages`), and add `export`.

In `query-provider.tsx`, delete the function and add `import { toastForError } from "./toast-for-error"`.

In `use-api-fetch.ts`, change `function resolveBaseUrl()` to `export function resolveBaseUrl()`.

`index.ts` becomes:

```ts
/**
 * The package's public runtime surface is deliberately tiny. Everything else is
 * reached through the subpath exports, so importing one tag does not pull in
 * the whole client.
 *
 * `resolveBaseUrl` and `toastForError` are here for the one hand-written call
 * site: the chat stream, which orval does not generate (streaming routes are
 * excluded) but which must resolve the API and report errors the same way.
 */
export { ApiError } from "./errors"
export { useApiFetch, resolveBaseUrl } from "./use-api-fetch"
export { toastForError } from "./toast-for-error"
```

Run: `cd web-app && pnpm vitest run packages/api-client`
Expected: PASS. This is a pure move.

- [ ] **Step 2: Write the failing tests**

Create `web-app/apps/web/src/lib/chat/stream-chat.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest"
import { ApiError } from "@app/api-client"

import { readEvents, streamChat, StreamFailedError } from "./stream-chat"

function bodyOf(...chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  })
}

const frame = (content: string, done = false) =>
  `data: ${JSON.stringify({ content, done })}\n\n`

async function collect<T>(gen: AsyncGenerator<T>): Promise<T[]> {
  const out: T[] = []
  for await (const item of gen) out.push(item)
  return out
}

function mockFetch(response: Response) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(response)
}

function run(signal = new AbortController().signal) {
  return collect(
    streamChat({ conversationId: "c1", message: "hi", token: "tok", signal }),
  )
}

afterEach(() => vi.restoreAllMocks())

describe("readEvents", () => {
  it("joins a frame split across chunks", async () => {
    const whole = frame("Hello")
    const events = await collect(
      readEvents(bodyOf(whole.slice(0, 7), whole.slice(7))),
    )
    expect(events).toEqual([{ content: "Hello", done: false }])
  })

  it("splits several frames in one chunk", async () => {
    const events = await collect(readEvents(bodyOf(frame("a") + frame("b"))))
    expect(events.map((e) => e.content)).toEqual(["a", "b"])
  })

  it("ignores comment lines such as sse-starlette's ping", async () => {
    const events = await collect(
      readEvents(bodyOf(": ping - 2026-10-13\n\n" + frame("a"))),
    )
    expect(events).toEqual([{ content: "a", done: false }])
  })
})

describe("streamChat", () => {
  it("posts the message with the bearer token and yields the chunks", async () => {
    const spy = mockFetch(
      new Response(bodyOf(frame("Hel") + frame("lo") + frame("", true))),
    )
    await expect(run()).resolves.toEqual(["Hel", "lo"])

    const [url, init] = spy.mock.calls[0]
    expect(String(url)).toMatch(/\/api\/v1\/chatbot\/chat\/c1\/stream$/)
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer tok")
    expect(init?.body).toBe(JSON.stringify({ message: "hi" }))
  })

  it("throws ApiError with the status on a non-2xx response", async () => {
    mockFetch(new Response("slow down", { status: 429 }))
    await expect(run()).rejects.toMatchObject({
      name: "ApiError",
      status: 429,
    })
    await expect(run()).rejects.toBeInstanceOf(ApiError)
  })

  it("treats a final event carrying content as a failure", async () => {
    mockFetch(
      new Response(
        bodyOf(frame("partial") + frame("An error occurred.", true)),
      ),
    )
    await expect(run()).rejects.toBeInstanceOf(StreamFailedError)
  })

  // Review Focus 2: a dropped connection must not leave the UI "running".
  it("treats a stream that ends without done as a failure", async () => {
    mockFetch(new Response(bodyOf(frame("partial"))))
    await expect(run()).rejects.toBeInstanceOf(StreamFailedError)
  })

  it("treats a malformed event as a failure", async () => {
    mockFetch(new Response(bodyOf('data: {"nope": 1}\n\n')))
    await expect(run()).rejects.toBeInstanceOf(StreamFailedError)
  })

  it("stops reading when aborted", async () => {
    const controller = new AbortController()
    vi.spyOn(globalThis, "fetch").mockImplementation(
      (_url, init) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () =>
            reject(new DOMException("aborted", "AbortError")),
          )
        }),
    )
    const pending = run(controller.signal)
    controller.abort()
    await expect(pending).rejects.toMatchObject({ name: "AbortError" })
  })
})
```

- [ ] **Step 3: Run them to verify they fail**

Run: `cd web-app && pnpm vitest run apps/web/src/lib/chat/stream-chat.test.ts`
Expected: FAIL (module not found).

- [ ] **Step 4: Implement**

Create `web-app/apps/web/src/lib/chat/stream-chat.ts`:

```ts
import { ApiError, resolveBaseUrl } from "@app/api-client"
import { z } from "zod"

/**
 * One event of POST /api/v1/chatbot/chat/{id}/stream.
 *
 * Mirrors `StreamResponse` in server/app/modules/conversation/schemas.py. It is
 * the one hand-written API payload schema in the app, and deliberately so:
 * routes tagged "streaming" are excluded from generation (orval.config.ts), and
 * the route's OpenAPI entry is held fixed (WS7), so no generated type exists.
 */
const StreamEventSchema = z.object({ content: z.string(), done: z.boolean() })
export type StreamEvent = z.infer<typeof StreamEventSchema>

/** The stream reported a failure, ended early, or sent something unreadable. */
export class StreamFailedError extends Error {
  constructor(message = "The chat stream failed") {
    super(message)
    this.name = "StreamFailedError"
  }
}

export type StreamChatOptions = {
  conversationId: string
  message: string
  token: string | null
  signal: AbortSignal
}

/**
 * Send a message and yield the reply as it is written.
 *
 * The server reports a failure as a final event with `done: true` and
 * non-empty content (the shape is fixed), so that is thrown as
 * StreamFailedError; its text is never surfaced. Aborting `signal` closes the
 * connection, and the server then stops the model call.
 */
export async function* streamChat({
  conversationId,
  message,
  token,
  signal,
}: StreamChatOptions): AsyncGenerator<string> {
  const headers = new Headers({
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  })
  if (token) headers.set("Authorization", `Bearer ${token}`)

  const response = await fetch(
    `${resolveBaseUrl()}/api/v1/chatbot/chat/${conversationId}/stream`,
    { method: "POST", headers, body: JSON.stringify({ message }), signal },
  )

  if (!response.ok) {
    throw new ApiError(
      `HTTP ${response.status}`,
      response.status,
      await response.text().catch(() => null),
      response.headers.get("x-request-id"),
    )
  }
  if (!response.body) throw new StreamFailedError("The response has no body")

  for await (const event of readEvents(response.body)) {
    if (event.done) {
      if (event.content !== "") throw new StreamFailedError()
      return
    }
    if (event.content) yield event.content
  }
  throw new StreamFailedError("The stream ended before it was done")
}

/** Parse server-sent events: frames end at a blank line; `:` lines are comments. */
export async function* readEvents(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<StreamEvent> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) return
      buffer += decoder.decode(value, { stream: true })
      let boundary = buffer.indexOf("\n\n")
      while (boundary !== -1) {
        const frame = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        const data = frame
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).replace(/^ /, ""))
          .join("\n")
        if (data) yield parseEvent(data)
        boundary = buffer.indexOf("\n\n")
      }
    }
  } finally {
    reader.cancel().catch(() => {})
  }
}

function parseEvent(data: string): StreamEvent {
  try {
    return StreamEventSchema.parse(JSON.parse(data))
  } catch {
    throw new StreamFailedError("The stream sent an unreadable event")
  }
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd web-app && pnpm vitest run apps/web/src/lib/chat packages/api-client`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
cd web-app && pnpm exec prettier --write apps/web/src/lib/chat packages/api-client/src && cd ..
git add web-app/packages/api-client/src web-app/apps/web/src/lib/chat
git commit -m "feat(chat): SSE client for the chat stream"
```

---

### Task 8: Chat message, markdown and composer components (W2)

**Files:**
- Modify: `web-app/apps/web/package.json`, `web-app/pnpm-lock.yaml` (through `pnpm add` only)
- Create: `web-app/apps/web/src/components/chat/copy.ts`, `markdown-text.tsx`, `chat-message.tsx`, `composer.tsx`, `thread.tsx`
- Create: `web-app/apps/web/src/components/chat/test-runtime.tsx` (a test helper: an `ExternalStoreRuntime` over fixed messages)
- Test: `web-app/apps/web/src/components/chat/thread.test.tsx`

**Interfaces:**
- Consumes: `sendChatMessageBodyMessageMax` from `@app/api-client/zod/chatbot` (3000).
- Produces:
  - `<Thread welcome?: ReactNode />`, rendered inside an `AssistantRuntimeProvider`
  - `CHAT_COPY` constants
  - `ChatThreadMessage`, the `ThreadMessageLike` shape Task 9 builds:
    - `{ id: string; role: "user" | "assistant"; content: string; status?: MessageStatus }`
    - `status` is `{ type: "running" }`, `{ type: "complete", reason: "stop" }`, or `{ type: "incomplete", reason: "cancelled" | "error" }`.

**Before writing code:** `@assistant-ui/react` is pre-1.0.
- After installing, check the names used below in `node_modules/@assistant-ui/react/dist/**/*.d.ts`: `ThreadPrimitive.{Root,Viewport,Messages,ScrollToBottom}`, `MessagePrimitive.{Root,Parts}`, `ComposerPrimitive.{Root,Input,Send,Cancel}`, `ActionBarPrimitive.{Root,Copy}`, `AuiIf`, `useAuiState`, `useExternalStoreRuntime`, `AssistantRuntimeProvider`, `MessageStatus`, `ThreadMessageLike`.
- Do the same for `@assistant-ui/react-markdown`: `MarkdownTextPrimitive`, `memoizeMarkdownComponents`, `useIsMarkdownCodeBlock`.
- Where a name differs, use the installed one and keep the behaviour. The registry's `thread` component for this version uses exactly these names.

- [ ] **Step 1: Install**

```bash
cd web-app && pnpm --filter @app/web add --save-exact @assistant-ui/react @assistant-ui/react-markdown remark-gfm
```

- [ ] **Step 2: Write the test helper and the failing test**

Create `web-app/apps/web/src/components/chat/test-runtime.tsx`:

```tsx
"use client"

import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  type ThreadMessageLike,
} from "@assistant-ui/react"
import type { ReactNode } from "react"

/** Test helper: render chat components over a fixed list of messages. */
export function TestRuntime({
  messages,
  isRunning = false,
  onNew = async () => {},
  onCancel,
  children,
}: {
  messages: ThreadMessageLike[]
  isRunning?: boolean
  onNew?: () => Promise<void>
  onCancel?: () => Promise<void>
  children: ReactNode
}) {
  const runtime = useExternalStoreRuntime<ThreadMessageLike>({
    messages,
    isRunning,
    convertMessage: (m) => m,
    onNew,
    onCancel,
  })
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  )
}
```

Create `web-app/apps/web/src/components/chat/thread.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeAll, describe, expect, it, vi } from "vitest"

import { CHAT_COPY } from "./copy"
import { TestRuntime } from "./test-runtime"
import { Thread } from "./thread"

beforeAll(() => {
  // jsdom has no layout: the viewport's auto-scroll calls these.
  Element.prototype.scrollTo ??= () => {}
  Element.prototype.scrollIntoView ??= () => {}
})

const user = (id: string, content: string) =>
  ({ id, role: "user", content }) as const
const assistant = (id: string, content: string, status?: object) =>
  ({ id, role: "assistant", content, status }) as never

describe("Thread", () => {
  it("shows the welcome state when there are no messages", () => {
    render(
      <TestRuntime messages={[]}>
        <Thread />
      </TestRuntime>,
    )
    expect(screen.getByText(CHAT_COPY.welcomeTitle)).toBeInTheDocument()
  })

  it("renders assistant replies as Markdown and user text as plain text", () => {
    render(
      <TestRuntime
        messages={[
          user("u1", "**not bold**"),
          assistant("a1", "Here is **bold** and a [link](https://example.com)"),
        ]}
      >
        <Thread />
      </TestRuntime>,
    )
    expect(screen.getByText("**not bold**")).toBeInTheDocument()
    expect(screen.getByText("bold").tagName).toBe("STRONG")
    const link = screen.getByRole("link", { name: "link" })
    expect(link).toHaveAttribute("target", "_blank")
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"))
  })

  it("renders raw HTML in a reply as text, not markup", () => {
    render(
      <TestRuntime messages={[assistant("a1", "<img src=x onerror=alert(1)>")]}>
        <Thread />
      </TestRuntime>,
    )
    expect(document.querySelector("img")).toBeNull()
  })

  it("marks a stopped reply and a failed reply with our own copy", () => {
    render(
      <TestRuntime
        messages={[
          user("u1", "one"),
          assistant("a1", "partial", { type: "incomplete", reason: "cancelled" }),
          user("u2", "two"),
          assistant("a2", "", { type: "incomplete", reason: "error" }),
        ]}
      >
        <Thread />
      </TestRuntime>,
    )
    expect(screen.getByText(CHAT_COPY.stopped)).toBeInTheDocument()
    expect(screen.getByText(CHAT_COPY.failed)).toBeInTheDocument()
  })

  it("offers no edit or regenerate action", () => {
    render(
      <TestRuntime messages={[user("u1", "q"), assistant("a1", "a")]}>
        <Thread />
      </TestRuntime>,
    )
    expect(screen.queryByRole("button", { name: /edit/i })).toBeNull()
    expect(screen.queryByRole("button", { name: /regenerate|reload/i })).toBeNull()
  })

  it("sends with Enter and swaps Send for Stop while running", async () => {
    const onNew = vi.fn(async () => {})
    const { rerender } = render(
      <TestRuntime messages={[]} onNew={onNew}>
        <Thread />
      </TestRuntime>,
    )
    await userEvent.type(screen.getByRole("textbox", { name: CHAT_COPY.inputLabel }), "hello{Enter}")
    expect(onNew).toHaveBeenCalledOnce()

    const onCancel = vi.fn(async () => {})
    rerender(
      <TestRuntime messages={[user("u1", "hello")]} isRunning onCancel={onCancel}>
        <Thread />
      </TestRuntime>,
    )
    await userEvent.click(screen.getByRole("button", { name: CHAT_COPY.stop }))
    expect(onCancel).toHaveBeenCalledOnce()
    expect(screen.queryByRole("button", { name: CHAT_COPY.send })).toBeNull()
  })

  it("caps the input at the server's message limit", () => {
    render(
      <TestRuntime messages={[]}>
        <Thread />
      </TestRuntime>,
    )
    expect(screen.getByRole("textbox", { name: CHAT_COPY.inputLabel })).toHaveAttribute(
      "maxLength",
      "3000",
    )
  })
})
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd web-app && pnpm vitest run apps/web/src/components/chat/thread.test.tsx`
Expected: FAIL (modules not found).

- [ ] **Step 4: Implement**

`copy.ts`:

```ts
/** User-facing copy for the chat screen. Server text is never rendered. */
export const CHAT_COPY = {
  welcomeTitle: "Ask about anything",
  welcomeBody: "Your conversations are kept in the list on the left.",
  inputLabel: "Message",
  placeholder: "Send a message…",
  send: "Send",
  stop: "Stop",
  copy: "Copy",
  scrollToBottom: "Scroll to the latest message",
  stopped: "Stopped",
  failed: "The assistant couldn't reply. Try again.",
  untitled: "New chat",
  newChat: "New chat",
  conversations: "Conversations",
  rename: "Rename",
  delete: "Delete",
  deleteTitle: "Delete this conversation?",
  deleteBody: "Its messages are deleted permanently.",
  cancel: "Cancel",
  notFoundTitle: "This conversation doesn't exist",
  notFoundAction: "Start a new chat",
  noConversations: "No conversations yet",
} as const
```

`markdown-text.tsx`:

```tsx
"use client"

import {
  MarkdownTextPrimitive,
  memoizeMarkdownComponents,
  useIsMarkdownCodeBlock,
} from "@assistant-ui/react-markdown"
import { cn } from "@app/core/lib/utils"
import { memo, type ComponentProps } from "react"
import remarkGfm from "remark-gfm"

function InlineOrBlockCode({ className, ...props }: ComponentProps<"code">) {
  const isBlock = useIsMarkdownCodeBlock()
  return (
    <code
      className={cn(
        !isBlock && "rounded bg-muted px-1 py-0.5 font-mono text-[0.9em]",
        className,
      )}
      {...props}
    />
  )
}

// Element → Tailwind classes, in place of @tailwindcss/typography.
// No rehype-raw: raw HTML in a reply renders as text, never as markup.
const components = memoizeMarkdownComponents({
  h1: ({ className, ...p }) => <h1 className={cn("mt-4 mb-2 text-lg font-semibold first:mt-0", className)} {...p} />,
  h2: ({ className, ...p }) => <h2 className={cn("mt-4 mb-2 text-base font-semibold first:mt-0", className)} {...p} />,
  h3: ({ className, ...p }) => <h3 className={cn("mt-3 mb-1 font-semibold first:mt-0", className)} {...p} />,
  p: ({ className, ...p }) => <p className={cn("my-2 leading-relaxed first:mt-0 last:mb-0", className)} {...p} />,
  ul: ({ className, ...p }) => <ul className={cn("my-2 ml-5 list-disc", className)} {...p} />,
  ol: ({ className, ...p }) => <ol className={cn("my-2 ml-5 list-decimal", className)} {...p} />,
  li: ({ className, ...p }) => <li className={cn("my-1", className)} {...p} />,
  a: ({ className, ...p }) => (
    <a className={cn("text-primary underline underline-offset-2", className)} target="_blank" rel="noopener noreferrer" {...p} />
  ),
  blockquote: ({ className, ...p }) => <blockquote className={cn("my-2 border-l-2 pl-3 text-muted-foreground", className)} {...p} />,
  hr: ({ className, ...p }) => <hr className={cn("my-4 border-border", className)} {...p} />,
  table: ({ className, ...p }) => (
    <div className="my-3 overflow-x-auto">
      <table className={cn("w-full border-collapse text-sm", className)} {...p} />
    </div>
  ),
  th: ({ className, ...p }) => <th className={cn("border px-2 py-1 text-left font-medium", className)} {...p} />,
  td: ({ className, ...p }) => <td className={cn("border px-2 py-1", className)} {...p} />,
  pre: ({ className, ...p }) => <pre className={cn("my-3 overflow-x-auto rounded-lg bg-muted p-3 text-sm", className)} {...p} />,
  code: InlineOrBlockCode,
})

function MarkdownTextImpl() {
  return (
    <MarkdownTextPrimitive
      remarkPlugins={[remarkGfm]}
      components={components}
      className="text-sm"
    />
  )
}

export const MarkdownText = memo(MarkdownTextImpl)
```

`chat-message.tsx`:

```tsx
"use client"

import {
  ActionBarPrimitive,
  MessagePrimitive,
  useAuiState,
} from "@assistant-ui/react"
import { Button } from "@app/ui/button"
import { CopyIcon } from "lucide-react"

import { CHAT_COPY } from "./copy"
import { MarkdownText } from "./markdown-text"

export function UserMessage() {
  return (
    <MessagePrimitive.Root className="flex justify-end py-2" data-role="user">
      <div className="max-w-[85%] rounded-2xl bg-muted px-4 py-2 text-sm whitespace-pre-wrap break-words">
        <MessagePrimitive.Parts />
      </div>
    </MessagePrimitive.Root>
  )
}

export function AssistantMessage() {
  const status = useAuiState((s) => s.message.status)
  const reason = status?.type === "incomplete" ? status.reason : undefined

  return (
    <MessagePrimitive.Root className="py-2" data-role="assistant">
      <div className="break-words">
        <MessagePrimitive.Parts components={{ Text: MarkdownText }} />
      </div>
      {reason === "cancelled" && (
        <p className="mt-1 text-xs text-muted-foreground">{CHAT_COPY.stopped}</p>
      )}
      {reason === "error" && (
        <p className="mt-1 text-sm text-destructive">{CHAT_COPY.failed}</p>
      )}
      <ActionBarPrimitive.Root hideWhenRunning autohide="not-last" className="mt-1 flex gap-1">
        <ActionBarPrimitive.Copy asChild>
          <Button variant="ghost" size="icon-sm" aria-label={CHAT_COPY.copy}>
            <CopyIcon />
          </Button>
        </ActionBarPrimitive.Copy>
      </ActionBarPrimitive.Root>
    </MessagePrimitive.Root>
  )
}
```

If `size="icon-sm"` isn't a variant in `packages/ui/src/primitives/button.tsx`, use the nearest icon size there.

`composer.tsx`:

```tsx
"use client"

import { AuiIf, ComposerPrimitive, useAuiState } from "@assistant-ui/react"
import { sendChatMessageBodyMessageMax } from "@app/api-client/zod/chatbot"
import { Button } from "@app/ui/button"
import { ArrowUpIcon, SquareIcon } from "lucide-react"

import { CHAT_COPY } from "./copy"

// The counter appears once a message gets close to the server's limit.
const COUNTER_FROM = sendChatMessageBodyMessageMax - 500

export function Composer() {
  const length = useAuiState((s) => s.composer.text.length)

  return (
    <ComposerPrimitive.Root className="flex w-full flex-col gap-1 rounded-2xl border bg-background p-2 focus-within:border-ring">
      <ComposerPrimitive.Input
        rows={1}
        autoFocus
        maxLength={sendChatMessageBodyMessageMax}
        placeholder={CHAT_COPY.placeholder}
        aria-label={CHAT_COPY.inputLabel}
        className="max-h-48 min-h-10 w-full resize-none bg-transparent px-2 py-1 text-sm outline-none"
      />
      <div className="flex items-center justify-end gap-2">
        {length >= COUNTER_FROM && (
          <span className="text-xs text-muted-foreground" aria-live="polite">
            {length} / {sendChatMessageBodyMessageMax}
          </span>
        )}
        <AuiIf condition={(s) => !s.thread.isRunning}>
          <ComposerPrimitive.Send asChild>
            <Button size="icon" aria-label={CHAT_COPY.send}>
              <ArrowUpIcon />
            </Button>
          </ComposerPrimitive.Send>
        </AuiIf>
        <AuiIf condition={(s) => s.thread.isRunning}>
          <ComposerPrimitive.Cancel asChild>
            <Button size="icon" variant="secondary" aria-label={CHAT_COPY.stop}>
              <SquareIcon />
            </Button>
          </ComposerPrimitive.Cancel>
        </AuiIf>
      </div>
    </ComposerPrimitive.Root>
  )
}
```

`thread.tsx`:

```tsx
"use client"

import { AuiIf, ThreadPrimitive } from "@assistant-ui/react"
import { Button } from "@app/ui/button"
import { ArrowDownIcon } from "lucide-react"
import type { ReactNode } from "react"

import { AssistantMessage, UserMessage } from "./chat-message"
import { Composer } from "./composer"
import { CHAT_COPY } from "./copy"

function Welcome() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-1 text-center">
      <h2 className="text-lg font-semibold">{CHAT_COPY.welcomeTitle}</h2>
      <p className="text-sm text-muted-foreground">{CHAT_COPY.welcomeBody}</p>
    </div>
  )
}

/** The message list and composer. Render inside an AssistantRuntimeProvider. */
export function Thread({ welcome }: { welcome?: ReactNode }) {
  return (
    <ThreadPrimitive.Root className="flex h-full min-h-0 flex-col">
      <ThreadPrimitive.Viewport className="relative flex min-h-0 flex-1 flex-col overflow-y-auto">
        <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 pt-4">
          <AuiIf condition={(s) => s.thread.isEmpty}>{welcome ?? <Welcome />}</AuiIf>
          <ThreadPrimitive.Messages components={{ UserMessage, AssistantMessage }} />
        </div>
        <div className="sticky bottom-0 mx-auto flex w-full max-w-3xl flex-col items-center gap-2 bg-background px-4 pt-2 pb-4">
          <ThreadPrimitive.ScrollToBottom asChild>
            <Button
              variant="outline"
              size="icon"
              className="rounded-full disabled:invisible"
              aria-label={CHAT_COPY.scrollToBottom}
            >
              <ArrowDownIcon />
            </Button>
          </ThreadPrimitive.ScrollToBottom>
          <Composer />
        </div>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  )
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd web-app && pnpm vitest run apps/web/src/components/chat`
Expected: all PASS.

If jsdom lacks an API the primitives call (for example `IntersectionObserver`), stub it in this test file's `beforeAll` the same way as `scrollTo`, and note it in the commit message.

- [ ] **Step 6: Lint, type-check, commit**

```bash
cd web-app && pnpm exec prettier --write apps/web/src/components/chat && pnpm --filter @app/web lint && pnpm exec tsc -p apps/web --noEmit && cd ..
git add web-app/apps/web/package.json web-app/pnpm-lock.yaml web-app/apps/web/src/components/chat
git commit -m "feat(chat): thread, message, markdown and composer on assistant-ui primitives"
```

---

### Task 9: The chat runtime — session, streaming and titles (W4)

**Files:**
- Create: `web-app/apps/web/src/components/chat/chat-runtime-provider.tsx`
- Test: `web-app/apps/web/src/components/chat/chat-runtime-provider.test.tsx`

**Interfaces:**
- Consumes:
  - `streamChat`, `StreamFailedError` (Task 7)
  - `toastForError` from `@app/api-client` (Task 7)
  - `Thread` (Task 8)
  - generated hooks:
    - from `@app/api-client/endpoints/conversation`: `useCreateConversation`, `useGenerateConversationTitle`, `getListConversationsQueryKey`
    - from `@app/api-client/endpoints/chatbot`: `useListChatMessages`, `getListChatMessagesQueryKey`
  - `ConversationResponse` and `Message` types from `@app/api-client/types`
  - `useAppAuth` from `@app/auth`
  - `useParams` and `useRouter` from `next/navigation`
- Produces:
  - `<ChatRuntimeProvider>{children}</ChatRuntimeProvider>`: provides the assistant-ui runtime for the active conversation, which comes from the `conversationId` route param.
  - `useActiveConversationId(): string | null`

- [ ] **Step 1: Write the failing tests**

Create `web-app/apps/web/src/components/chat/chat-runtime-provider.test.tsx`. It mocks `next/navigation`, `@app/auth` and `@/lib/chat/stream-chat`, and stubs `fetch` for the generated hooks, which go through `useApiFetch`.

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest"

import { getListConversationsQueryKey } from "@app/api-client/endpoints/conversation"

import { ChatRuntimeProvider } from "./chat-runtime-provider"
import { CHAT_COPY } from "./copy"
import { Thread } from "./thread"

const mocks = vi.hoisted(() => ({
  params: {} as { conversationId?: string },
  replace: vi.fn(),
  push: vi.fn(),
  stream: vi.fn(),
  toast: vi.fn(),
}))

vi.mock("next/navigation", () => ({
  useParams: () => mocks.params,
  useRouter: () => ({ replace: mocks.replace, push: mocks.push }),
}))
vi.mock("@app/auth", () => ({
  useAppAuth: () => ({ getToken: async () => "tok" }),
}))
vi.mock("@/lib/chat/stream-chat", async (importOriginal) => ({
  ...(await importOriginal<object>()),
  streamChat: (...args: unknown[]) => mocks.stream(...args),
}))
vi.mock("@app/api-client", async (importOriginal) => ({
  ...(await importOriginal<object>()),
  toastForError: (e: unknown) => mocks.toast(e),
}))

type Routes = Record<string, (init?: RequestInit) => unknown>
let routes: Routes
const calls: string[] = []

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  })
}

beforeAll(() => {
  Element.prototype.scrollTo ??= () => {}
  Element.prototype.scrollIntoView ??= () => {}
})

beforeEach(() => {
  vi.clearAllMocks()
  calls.length = 0
  mocks.params = {}
  routes = {
    "GET /api/v1/conversation/conversations": () => [],
    "POST /api/v1/conversation/conversation": () => ({
      conversation_id: "c1",
      name: "",
      created_at: "2026-10-13T10:00:00Z",
    }),
    "GET /api/v1/chatbot/chat/c1/messages": () => ({ messages: [] }),
    "POST /api/v1/conversation/conversation/c1/title": () => ({
      conversation_id: "c1",
      name: "Groceries",
      created_at: "2026-10-13T10:00:00Z",
    }),
  }
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const path = new URL(String(input)).pathname
    const key = `${init?.method ?? "GET"} ${path}`
    calls.push(key)
    const handler = routes[key]
    if (!handler) return json({ detail: "not found" }, 404)
    return json(handler(init))
  })
})

function renderChat() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const utils = render(
    <QueryClientProvider client={client}>
      <ChatRuntimeProvider>
        <Thread />
      </ChatRuntimeProvider>
    </QueryClientProvider>,
  )
  return { client, ...utils }
}

async function send(text: string) {
  await userEvent.type(
    screen.getByRole("textbox", { name: CHAT_COPY.inputLabel }),
    `${text}{Enter}`,
  )
}

async function* chunks(...parts: string[]) {
  for (const part of parts) yield part
}

describe("ChatRuntimeProvider", () => {
  it("creates a conversation on the first send, replaces the URL and streams the reply", async () => {
    mocks.stream.mockImplementation(() => chunks("Hel", "lo"))
    renderChat()
    await send("hi")

    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/chat/c1"))
    expect(mocks.stream).toHaveBeenCalledWith(
      expect.objectContaining({ conversationId: "c1", message: "hi", token: "tok" }),
    )
    expect(calls).toContain("POST /api/v1/conversation/conversation")
  })

  it("swaps the in-flight exchange for the saved history, then asks for a title", async () => {
    mocks.params = { conversationId: "c1" }
    routes["GET /api/v1/conversation/conversations"] = () => [
      { conversation_id: "c1", name: "", created_at: "2026-10-13T10:00:00Z" },
    ]
    // The server has saved the exchange once the stream has finished, not before.
    let saved = false
    mocks.stream.mockImplementation(async function* () {
      yield "Hello"
      saved = true
    })
    routes["GET /api/v1/chatbot/chat/c1/messages"] = () => ({
      messages: saved
        ? [
            { role: "user", content: "hi" },
            { role: "assistant", content: "Hello" },
          ]
        : [],
    })
    renderChat()
    await send("hi")

    await waitFor(() =>
      expect(calls).toContain("POST /api/v1/conversation/conversation/c1/title"),
    )
    expect(screen.getAllByText("hi")).toHaveLength(1)
    expect(screen.getAllByText("Hello")).toHaveLength(1)
  })

  it("does not ask for a title when the conversation already has a name", async () => {
    mocks.params = { conversationId: "c1" }
    mocks.stream.mockImplementation(() => chunks("Hello"))
    routes["GET /api/v1/conversation/conversations"] = () => [
      { conversation_id: "c1", name: "Named", created_at: "2026-10-13T10:00:00Z" },
    ]
    const { client } = renderChat()
    // The title check reads the list cache; the list is loaded by the
    // conversation column in the app, so load it here the same way.
    await client.fetchQuery({
      queryKey: getListConversationsQueryKey(),
      queryFn: async () =>
        (await fetch("http://localhost:8100/api/v1/conversation/conversations")).json(),
    })
    await send("hi")
    await waitFor(() => expect(mocks.stream).toHaveBeenCalled())
    await new Promise((r) => setTimeout(r, 50))
    expect(calls).not.toContain("POST /api/v1/conversation/conversation/c1/title")
  })

  it("Stop aborts the stream and marks the partial reply as stopped", async () => {
    mocks.params = { conversationId: "c1" }
    let signal: AbortSignal | undefined
    mocks.stream.mockImplementation(async function* (opts: { signal: AbortSignal }) {
      signal = opts.signal
      yield "partial"
      await new Promise((_, reject) =>
        opts.signal.addEventListener("abort", () =>
          reject(new DOMException("aborted", "AbortError")),
        ),
      )
    })
    renderChat()
    await send("hi")
    await screen.findByText("partial")
    await userEvent.click(screen.getByRole("button", { name: CHAT_COPY.stop }))

    expect(signal?.aborted).toBe(true)
    expect(await screen.findByText(CHAT_COPY.stopped)).toBeInTheDocument()
  })

  it("a failure event shows our copy, not the server's", async () => {
    mocks.params = { conversationId: "c1" }
    const { StreamFailedError } = await import("@/lib/chat/stream-chat")
    mocks.stream.mockImplementation(async function* () {
      yield "par"
      throw new StreamFailedError()
    })
    renderChat()
    await send("hi")
    expect(await screen.findByText(CHAT_COPY.failed)).toBeInTheDocument()
  })
})
```

The `fetch` URL's host is irrelevant: the stub routes by path, and `vitest.setup.ts` sets `NEXT_PUBLIC_API_URL` to `http://localhost:8100` when it's unset.

- [ ] **Step 2: Run them to verify they fail**

Run: `cd web-app && pnpm vitest run apps/web/src/components/chat/chat-runtime-provider.test.tsx`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement**

Create `web-app/apps/web/src/components/chat/chat-runtime-provider.tsx`:

```tsx
"use client"

import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from "@assistant-ui/react"
import { ApiError, toastForError } from "@app/api-client"
import {
  getListChatMessagesQueryKey,
  useListChatMessages,
} from "@app/api-client/endpoints/chatbot"
import {
  getListConversationsQueryKey,
  useCreateConversation,
  useGenerateConversationTitle,
} from "@app/api-client/endpoints/conversation"
import type {
  ConversationHistory,
  ConversationResponse,
  Message,
} from "@app/api-client/types"
import { useAppAuth } from "@app/auth"
import { useQueryClient } from "@tanstack/react-query"
import { useParams, useRouter } from "next/navigation"
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"

import { streamChat } from "@/lib/chat/stream-chat"

/**
 * The exchange being streamed, kept beside the saved history until the server
 * has it. `baseCount` is how many history messages preceded it: the history
 * query can refetch mid-stream (it gains the user's message as soon as the
 * graph starts), and slicing at baseCount is what keeps that message from
 * showing twice.
 */
type Exchange = {
  conversationId: string
  baseCount: number
  userText: string
  replyText: string
  status: "running" | "stopped" | "error"
}

const EMPTY: Message[] = []

export function useActiveConversationId(): string | null {
  const params = useParams<{ conversationId?: string }>()
  return params.conversationId ?? null
}

export function ChatRuntimeProvider({ children }: { children: ReactNode }) {
  const activeId = useActiveConversationId()
  const router = useRouter()
  const queryClient = useQueryClient()
  const { getToken } = useAppAuth()
  const createConversation = useCreateConversation()
  const generateTitle = useGenerateConversationTitle()
  const history = useListChatMessages(activeId ?? "", {
    query: { enabled: activeId !== null },
  })

  const [exchange, setExchange] = useState<Exchange | null>(null)
  const controllerRef = useRef<AbortController | null>(null)
  const inflightIdRef = useRef<string | null>(null)
  const restoreTextRef = useRef<(text: string) => void>(() => {})

  // Leaving a conversation abandons its stream, and with WS7 the server stops
  // the model call. The first send on /chat moves the URL to the new
  // conversation's id: that move is not leaving, hence inflightIdRef.
  useEffect(() => {
    if (inflightIdRef.current !== null && inflightIdRef.current !== activeId) {
      controllerRef.current?.abort()
      controllerRef.current = null
      inflightIdRef.current = null
    }
    setExchange((e) => (e && e.conversationId !== activeId ? null : e))
  }, [activeId])

  useEffect(() => () => controllerRef.current?.abort(), [])

  const requestTitle = useCallback(
    (conversationId: string) => {
      const listKey = getListConversationsQueryKey()
      const rows = queryClient.getQueryData<ConversationResponse[]>(listKey)
      const row = rows?.find((r) => r.conversation_id === conversationId)
      if (row && row.name !== "") return
      generateTitle.mutate(
        { conversationId },
        {
          onSuccess: (updated) =>
            queryClient.setQueryData<ConversationResponse[]>(listKey, (current) =>
              current?.map((r) =>
                r.conversation_id === updated.conversation_id ? updated : r,
              ),
            ),
        },
      )
    },
    [generateTitle, queryClient],
  )

  const onNew = useCallback(
    async (message: AppendMessage) => {
      const part = message.content[0]
      if (part?.type !== "text") return
      const text = part.text

      let conversationId = activeId
      if (conversationId === null) {
        let created: ConversationResponse
        try {
          created = await createConversation.mutateAsync()
        } catch {
          // The mutation cache has already toasted.
          restoreTextRef.current(text)
          return
        }
        conversationId = created.conversation_id
        queryClient.setQueryData<ConversationResponse[]>(
          getListConversationsQueryKey(),
          (rows) => [created, ...(rows ?? [])],
        )
        // A new conversation's history is known to be empty. Seeding it means
        // /chat/[id] renders the thread at once instead of a loading skeleton
        // that would hide the reply as it starts streaming.
        queryClient.setQueryData<ConversationHistory>(
          getListChatMessagesQueryKey(conversationId),
          { messages: [] },
        )
        inflightIdRef.current = conversationId
        router.replace(`/chat/${conversationId}`)
      }

      // After a stop or failure the saved history may have moved on (it holds
      // the stopped turn's user message), so count from fresh data.
      const historyKey = getListChatMessagesQueryKey(conversationId)
      if (activeId !== null) await queryClient.refetchQueries({ queryKey: historyKey })
      const saved =
        queryClient.getQueryData<ConversationHistory>(historyKey)?.messages ?? EMPTY

      const controller = new AbortController()
      controllerRef.current = controller
      inflightIdRef.current = conversationId
      setExchange({
        conversationId,
        baseCount: saved.length,
        userText: text,
        replyText: "",
        status: "running",
      })

      try {
        const token = await getToken()
        for await (const chunk of streamChat({
          conversationId,
          message: text,
          token,
          signal: controller.signal,
        })) {
          setExchange((e) =>
            e && e.conversationId === conversationId
              ? { ...e, replyText: e.replyText + chunk }
              : e,
          )
        }
        await queryClient.refetchQueries({ queryKey: historyKey })
        setExchange((e) => (e?.conversationId === conversationId ? null : e))
        requestTitle(conversationId)
      } catch (error) {
        if (controller.signal.aborted) {
          setExchange((e) =>
            e?.conversationId === conversationId ? { ...e, status: "stopped" } : e,
          )
        } else if (error instanceof ApiError) {
          // Refused before anything streamed: nothing to show but the toast,
          // and the user's text goes back in the composer.
          toastForError(error)
          setExchange((e) => (e?.conversationId === conversationId ? null : e))
          restoreTextRef.current(text)
        } else {
          setExchange((e) =>
            e?.conversationId === conversationId ? { ...e, status: "error" } : e,
          )
        }
      } finally {
        if (controllerRef.current === controller) controllerRef.current = null
        if (inflightIdRef.current === conversationId) inflightIdRef.current = null
      }
    },
    [activeId, createConversation, getToken, queryClient, requestTitle, router],
  )

  const onCancel = useCallback(async () => {
    controllerRef.current?.abort()
  }, [])

  const savedMessages = history.data?.messages ?? EMPTY
  const messages = useMemo<ThreadMessageLike[]>(() => {
    const visible =
      exchange && (exchange.conversationId === activeId || activeId === null)
        ? exchange
        : null
    const base = visible ? savedMessages.slice(0, visible.baseCount) : savedMessages
    const converted: ThreadMessageLike[] = base.map((m, i) => ({
      id: `${activeId}-${i}`,
      role: m.role === "user" ? "user" : "assistant",
      content: m.content,
    }))
    if (!visible) return converted
    return [
      ...converted,
      { id: "inflight-user", role: "user", content: visible.userText },
      {
        id: "inflight-assistant",
        role: "assistant",
        content: visible.replyText,
        status:
          visible.status === "running"
            ? { type: "running" }
            : { type: "incomplete", reason: visible.status === "stopped" ? "cancelled" : "error" },
      },
    ]
  }, [activeId, exchange, savedMessages])

  const runtime = useExternalStoreRuntime<ThreadMessageLike>({
    messages,
    isRunning: exchange?.status === "running",
    convertMessage: (m) => m,
    onNew,
    onCancel,
  })

  // Set in an effect, not during render: React 19's lint rules forbid writing refs while rendering.
  useEffect(() => {
    restoreTextRef.current = (text: string) => runtime.thread.composer.setText(text)
  }, [runtime])

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  )
}
```

Notes for the implementer:
- If the installed `MessageStatus` names the incomplete reasons differently, map `stopped` and `error` onto the installed names. Task 8's `AssistantMessage` reads `status.reason`, so keep the two in agreement.
- If `runtime.thread.composer.setText` isn't the installed path, find the composer's `setText` on the runtime's thread.
- The system role isn't in `Message` history from the server (it filters to user and assistant), so mapping everything non-user to assistant is safe.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd web-app && pnpm vitest run apps/web/src/components/chat`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
cd web-app && pnpm exec prettier --write apps/web/src/components/chat && pnpm exec tsc -p apps/web --noEmit && cd ..
git add web-app/apps/web/src/components/chat
git commit -m "feat(chat): runtime over the generated hooks — stream, stop, history swap, titles"
```

---

### Task 10: Review Focus tests for the runtime — switching mid-stream, HTTP errors

**Files:**
- Test: `web-app/apps/web/src/components/chat/chat-runtime-provider.test.tsx`
- Modify, only if a test fails: `web-app/apps/web/src/components/chat/chat-runtime-provider.tsx`

**Interfaces:**
- Consumes: Task 9's `ChatRuntimeProvider` and the test harness in its test file.

- [ ] **Step 1: Write the tests**

Append to `chat-runtime-provider.test.tsx`:

```tsx
describe("ChatRuntimeProvider — leaving and refusals", () => {
  // Review Focus 1
  it("switching conversation mid-stream aborts it and does not carry the reply over", async () => {
    mocks.params = { conversationId: "c1" }
    routes["GET /api/v1/chatbot/chat/c2/messages"] = () => ({
      messages: [{ role: "user", content: "older question" }],
    })
    let signal: AbortSignal | undefined
    mocks.stream.mockImplementation(async function* (opts: { signal: AbortSignal }) {
      signal = opts.signal
      yield "streaming in c1"
      await new Promise((_, reject) =>
        opts.signal.addEventListener("abort", () =>
          reject(new DOMException("aborted", "AbortError")),
        ),
      )
    })
    const { rerender, client } = renderChat()
    await send("hi")
    await screen.findByText("streaming in c1")

    mocks.params = { conversationId: "c2" }
    rerender(
      <QueryClientProvider client={client}>
        <ChatRuntimeProvider>
          <Thread />
        </ChatRuntimeProvider>
      </QueryClientProvider>,
    )

    await waitFor(() => expect(signal?.aborted).toBe(true))
    expect(await screen.findByText("older question")).toBeInTheDocument()
    expect(screen.queryByText("streaming in c1")).toBeNull()
    expect(screen.queryByText(CHAT_COPY.stopped)).toBeNull()
  })

  // Review Focus 3
  it("a refused stream start toasts, shows no bubbles and gives the text back", async () => {
    mocks.params = { conversationId: "c1" }
    const { ApiError } = await import("@app/api-client")
    mocks.stream.mockImplementation(async function* () {
      throw new ApiError("HTTP 429", 429, null, null)
    })
    renderChat()
    await send("too fast")

    await waitFor(() => expect(mocks.toast).toHaveBeenCalledOnce())
    expect(mocks.toast.mock.calls[0][0]).toMatchObject({ status: 429 })
    expect(document.querySelector('[data-role="user"]')).toBeNull()
    await waitFor(() =>
      expect(screen.getByRole("textbox", { name: CHAT_COPY.inputLabel })).toHaveValue("too fast"),
    )
  })
})
```

- [ ] **Step 2: Run them**

Run: `cd web-app && pnpm vitest run apps/web/src/components/chat/chat-runtime-provider.test.tsx`
Expected: PASS. If one fails, fix `chat-runtime-provider.tsx` (not the test) until it passes, and say what changed in the commit message.

- [ ] **Step 3: Commit**

```bash
git add web-app/apps/web/src/components/chat
git commit -m "test(chat): leaving mid-stream aborts; a refused send restores the text"
```

---

### Task 11: The conversation list (W2)

**Files:**
- Create: `web-app/apps/web/src/components/chat/conversation-row.tsx`, `conversation-list.tsx`
- Test: `web-app/apps/web/src/components/chat/conversation-list.test.tsx`

**Interfaces:**
- Consumes:
  - from `@app/api-client/endpoints/conversation`: `useListConversations`, `useRenameConversation`, `useDeleteConversation`, `getListConversationsQueryKey`
  - `renameConversationBodyNameMax` from `@app/api-client/zod/conversation` (100)
  - `@app/ui`: `button`, `input`, `dropdown-menu`, `dialog`, `skeleton`
  - `CHAT_COPY`
- Produces: `<ConversationList activeId: string | null; onNavigate?: () => void />`. `onNavigate` lets the mobile sheet close after a pick.

Before writing, read `packages/ui/src/primitives/dropdown-menu.tsx` and `dialog.tsx` for their export names, and the `web-app-patterns` skill's `references/components.md`. Triggers use `render={<Button … />}`.

Check the generated variables shapes in `packages/api-client/src/generated/endpoints/conversation/conversation.ts`:
- `RenameConversationMutationVariables`, expected to be `{ conversationId: string; data: BodyRenameConversation }`
- `DeleteConversationMutationVariables`, which is `{ conversationId: string }`

- [ ] **Step 1: Write the failing tests**

Create `conversation-list.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ConversationList } from "./conversation-list"
import { CHAT_COPY } from "./copy"

const mocks = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
  usePathname: () => "/chat",
}))
vi.mock("@app/auth", () => ({ useAppAuth: () => ({ getToken: async () => "tok" }) }))

const rows = [
  { conversation_id: "c2", name: "", created_at: "2026-10-13T11:00:00Z" },
  { conversation_id: "c1", name: "Groceries", created_at: "2026-10-13T10:00:00Z" },
]
const calls: { method: string; path: string; body?: string }[] = []

beforeEach(() => {
  vi.clearAllMocks()
  calls.length = 0
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const path = new URL(String(input)).pathname
    const method = init?.method ?? "GET"
    calls.push({ method, path, body: init?.body ? String(init.body) : undefined })
    if (method === "GET") {
      return new Response(JSON.stringify(rows), { headers: { "content-type": "application/json" } })
    }
    if (method === "PATCH") {
      const name = new URLSearchParams(String(init?.body)).get("name")
      return new Response(
        JSON.stringify({ ...rows[1], name }),
        { headers: { "content-type": "application/json" } },
      )
    }
    return new Response(null, { status: 204 })
  })
})

function renderList(activeId: string | null = null) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <ConversationList activeId={activeId} />
    </QueryClientProvider>,
  )
}

async function openMenu(rowName: string) {
  const row = (await screen.findByText(rowName)).closest("[data-slot=conversation-row]") as HTMLElement
  await userEvent.click(within(row).getByRole("button", { name: /options/i }))
}

describe("ConversationList", () => {
  it("lists conversations in server order and labels an untitled one", async () => {
    renderList()
    const links = await screen.findAllByRole("link")
    expect(links.map((l) => l.textContent?.trim())).toEqual([CHAT_COPY.newChat, CHAT_COPY.untitled, "Groceries"])
  })

  it("marks the active conversation", async () => {
    renderList("c1")
    expect(await screen.findByRole("link", { name: "Groceries" })).toHaveAttribute("aria-current", "page")
  })

  it("renames with Enter", async () => {
    renderList()
    await openMenu("Groceries")
    await userEvent.click(await screen.findByRole("menuitem", { name: CHAT_COPY.rename }))
    const input = screen.getByRole("textbox", { name: CHAT_COPY.rename })
    await userEvent.clear(input)
    await userEvent.type(input, "Food{Enter}")

    await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true))
    expect(await screen.findByRole("link", { name: "Food" })).toBeInTheDocument()
  })

  // Review Focus 4
  it("an empty or whitespace name sends nothing and keeps the old name", async () => {
    renderList()
    await openMenu("Groceries")
    await userEvent.click(await screen.findByRole("menuitem", { name: CHAT_COPY.rename }))
    const input = screen.getByRole("textbox", { name: CHAT_COPY.rename })
    expect(input).toHaveAttribute("maxLength", "100")
    await userEvent.clear(input)
    await userEvent.type(input, "   {Enter}")

    expect(calls.some((c) => c.method === "PATCH")).toBe(false)
    expect(await screen.findByRole("link", { name: "Groceries" })).toBeInTheDocument()
  })

  it("Escape cancels a rename", async () => {
    renderList()
    await openMenu("Groceries")
    await userEvent.click(await screen.findByRole("menuitem", { name: CHAT_COPY.rename }))
    await userEvent.type(screen.getByRole("textbox", { name: CHAT_COPY.rename }), "xyz{Escape}")
    expect(await screen.findByRole("link", { name: "Groceries" })).toBeInTheDocument()
    expect(calls.some((c) => c.method === "PATCH")).toBe(false)
  })

  it("deletes after confirmation, and leaves the conversation if it was open", async () => {
    renderList("c1")
    await openMenu("Groceries")
    await userEvent.click(await screen.findByRole("menuitem", { name: CHAT_COPY.delete }))
    const dialog = await screen.findByRole("dialog")
    expect(within(dialog).getByText(CHAT_COPY.deleteTitle)).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole("button", { name: CHAT_COPY.delete }))

    await waitFor(() =>
      expect(calls).toContainEqual(
        expect.objectContaining({ method: "DELETE", path: "/api/v1/conversation/conversation/c1" }),
      ),
    )
    await waitFor(() => expect(mocks.push).toHaveBeenCalledWith("/chat"))
    await waitFor(() => expect(screen.queryByRole("link", { name: "Groceries" })).toBeNull())
  })
})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd web-app && pnpm vitest run apps/web/src/components/chat/conversation-list.test.tsx`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement**

`conversation-row.tsx`:

```tsx
"use client"

import type { ConversationResponse } from "@app/api-client/types"
import { renameConversationBodyNameMax } from "@app/api-client/zod/conversation"
import { cn } from "@app/core/lib/utils"
import { Button } from "@app/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@app/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@app/ui/dropdown-menu"
import { Input } from "@app/ui/input"
import { MoreHorizontalIcon, PencilIcon, Trash2Icon } from "lucide-react"
import Link from "next/link"
import { useState } from "react"

import { CHAT_COPY } from "./copy"

export function ConversationRow({
  conversation,
  active,
  onRename,
  onDelete,
  onNavigate,
}: {
  conversation: ConversationResponse
  active: boolean
  onRename: (name: string) => void
  onDelete: () => void
  onNavigate?: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const label = conversation.name || CHAT_COPY.untitled

  function commit(value: string) {
    setEditing(false)
    const name = value.trim()
    if (name !== "" && name !== conversation.name) onRename(name)
  }

  return (
    <div
      data-slot="conversation-row"
      className={cn(
        "group flex items-center gap-1 rounded-lg pr-1 hover:bg-muted",
        active && "bg-muted",
      )}
    >
      {editing ? (
        <Input
          autoFocus
          aria-label={CHAT_COPY.rename}
          defaultValue={conversation.name}
          maxLength={renameConversationBodyNameMax}
          className="h-8 flex-1"
          onKeyDown={(e) => {
            if (e.key === "Enter") commit(e.currentTarget.value)
            if (e.key === "Escape") setEditing(false)
          }}
          onBlur={(e) => commit(e.currentTarget.value)}
        />
      ) : (
        <Link
          href={`/chat/${conversation.conversation_id}`}
          aria-current={active ? "page" : undefined}
          onClick={onNavigate}
          className="flex-1 truncate px-3 py-2 text-sm"
        >
          {label}
        </Link>
      )}

      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={`Options for ${label}`}
              className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100 data-[popup-open]:opacity-100"
            />
          }
        >
          <MoreHorizontalIcon />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => setEditing(true)}>
            <PencilIcon /> {CHAT_COPY.rename}
          </DropdownMenuItem>
          <DropdownMenuItem variant="destructive" onClick={() => setConfirming(true)}>
            <Trash2Icon /> {CHAT_COPY.delete}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={confirming} onOpenChange={setConfirming}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{CHAT_COPY.deleteTitle}</DialogTitle>
            <DialogDescription>{CHAT_COPY.deleteBody}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose render={<Button variant="outline" />}>{CHAT_COPY.cancel}</DialogClose>
            <Button
              variant="destructive"
              onClick={() => {
                setConfirming(false)
                onDelete()
              }}
            >
              {CHAT_COPY.delete}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
```

Adjust the primitive export names and props, such as `DropdownMenuItem variant` and `DialogClose render`, to what `packages/ui/src/primitives/*.tsx` actually exports. Keep the roles and labels the tests use.

`conversation-list.tsx`:

```tsx
"use client"

import {
  getListConversationsQueryKey,
  useDeleteConversation,
  useListConversations,
  useRenameConversation,
} from "@app/api-client/endpoints/conversation"
import type { ConversationResponse } from "@app/api-client/types"
import { Skeleton } from "@app/ui/skeleton"
import { useQueryClient } from "@tanstack/react-query"
import { SquarePenIcon } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"

import { ConversationRow } from "./conversation-row"
import { CHAT_COPY } from "./copy"

export function ConversationList({
  activeId,
  onNavigate,
}: {
  activeId: string | null
  onNavigate?: () => void
}) {
  const router = useRouter()
  const queryClient = useQueryClient()
  const listKey = getListConversationsQueryKey()
  const { data, isPending } = useListConversations()
  const rename = useRenameConversation()
  const remove = useDeleteConversation()

  const replaceRow = (updated: ConversationResponse) =>
    queryClient.setQueryData<ConversationResponse[]>(listKey, (rows) =>
      rows?.map((r) => (r.conversation_id === updated.conversation_id ? updated : r)),
    )

  return (
    <nav aria-label={CHAT_COPY.conversations} className="flex min-h-0 flex-col gap-1">
      <Link
        href="/chat"
        onClick={onNavigate}
        className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium hover:bg-muted"
      >
        <SquarePenIcon className="size-4" /> {CHAT_COPY.newChat}
      </Link>

      <div className="flex min-h-0 flex-col gap-0.5 overflow-y-auto">
        {isPending &&
          Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="mx-3 my-2 h-5" />)}
        {data?.length === 0 && (
          <p className="px-3 py-2 text-sm text-muted-foreground">{CHAT_COPY.noConversations}</p>
        )}
        {data?.map((conversation) => (
          <ConversationRow
            key={conversation.conversation_id}
            conversation={conversation}
            active={conversation.conversation_id === activeId}
            onNavigate={onNavigate}
            onRename={(name) =>
              rename.mutate(
                { conversationId: conversation.conversation_id, data: { name } },
                { onSuccess: replaceRow },
              )
            }
            onDelete={() =>
              remove.mutate(
                { conversationId: conversation.conversation_id },
                {
                  onSuccess: () => {
                    queryClient.setQueryData<ConversationResponse[]>(listKey, (rows) =>
                      rows?.filter((r) => r.conversation_id !== conversation.conversation_id),
                    )
                    if (conversation.conversation_id === activeId) router.push("/chat")
                  },
                },
              )
            }
          />
        ))}
      </div>
    </nav>
  )
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd web-app && pnpm vitest run apps/web/src/components/chat`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
cd web-app && pnpm exec prettier --write apps/web/src/components/chat && pnpm exec tsc -p apps/web --noEmit && cd ..
git add web-app/apps/web/src/components/chat
git commit -m "feat(chat): conversation list with rename and delete"
```

---

### Task 12: The chat route, the sidebar entry and the end-to-end check (W1)

**Files:**
- Create: `web-app/apps/web/src/components/chat/chat-shell.tsx`
- Create: `web-app/apps/web/src/app/(dashboard)/chat/layout.tsx`, `page.tsx`, `loading.tsx`, `[conversationId]/page.tsx`
- Create: `web-app/apps/web/src/components/chat/conversation-not-found.tsx`
- Modify: `web-app/apps/web/src/lib/hub-nav.ts`
- Test: `web-app/apps/web/src/components/chat/chat-shell.test.tsx`

**Interfaces:**
- Consumes:
  - `ChatRuntimeProvider` and `useActiveConversationId` (Task 9)
  - `Thread` (Task 8)
  - `ConversationList` (Task 11)
  - `useListChatMessages` (generated)
  - `useIsMobile` from `@app/ui/hooks/use-mobile`
  - `Sheet*` from `@app/ui/sheet`

Read `references/pages.md` in the `web-app-patterns` skill before starting, and `node_modules/next/dist/docs/` for layouts and `useParams` in Next 16.

- [ ] **Step 1: Write the failing test (Review Focus 5)**

Create `chat-shell.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest"

import { ChatRuntimeProvider } from "./chat-runtime-provider"
import { ConversationPage } from "./chat-shell"
import { CHAT_COPY } from "./copy"

const mocks = vi.hoisted(() => ({ params: { conversationId: "missing" } }))
vi.mock("next/navigation", () => ({
  useParams: () => mocks.params,
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/chat/missing",
}))
vi.mock("@app/auth", () => ({ useAppAuth: () => ({ getToken: async () => "tok" }) }))

beforeAll(() => {
  Element.prototype.scrollTo ??= () => {}
  Element.prototype.scrollIntoView ??= () => {}
})

beforeEach(() => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ detail: "Conversation not found" }), {
      status: 404,
      headers: { "content-type": "application/json" },
    }),
  )
})

describe("ConversationPage", () => {
  it("an unknown or foreign id shows not-found with a way out, and no composer", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <ChatRuntimeProvider>
          <ConversationPage />
        </ChatRuntimeProvider>
      </QueryClientProvider>,
    )
    expect(await screen.findByText(CHAT_COPY.notFoundTitle)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: CHAT_COPY.notFoundAction })).toHaveAttribute("href", "/chat")
    expect(screen.queryByRole("textbox", { name: CHAT_COPY.inputLabel })).toBeNull()
  })
})
```

Run: `cd web-app && pnpm vitest run apps/web/src/components/chat/chat-shell.test.tsx`
Expected: FAIL (module not found).

- [ ] **Step 2: Implement the shell and pages**

`conversation-not-found.tsx`:

```tsx
import { Button } from "@app/ui/button"
import Link from "next/link"

import { CHAT_COPY } from "./copy"

export function ConversationNotFound() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
      <p className="text-base font-medium">{CHAT_COPY.notFoundTitle}</p>
      <Button render={<Link href="/chat" />}>{CHAT_COPY.notFoundAction}</Button>
    </div>
  )
}
```

`chat-shell.tsx`:

```tsx
"use client"

import { ApiError } from "@app/api-client"
import { useListChatMessages } from "@app/api-client/endpoints/chatbot"
import { useIsMobile } from "@app/ui/hooks/use-mobile"
import { Button } from "@app/ui/button"
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@app/ui/sheet"
import { Skeleton } from "@app/ui/skeleton"
import { PanelLeftIcon } from "lucide-react"
import { useState, type ReactNode } from "react"

import { ChatRuntimeProvider, useActiveConversationId } from "./chat-runtime-provider"
import { ConversationList } from "./conversation-list"
import { ConversationNotFound } from "./conversation-not-found"
import { CHAT_COPY } from "./copy"
import { Thread } from "./thread"

/**
 * The chat route's two panes. Sized to the viewport inside the dashboard's
 * shared scroller (whose py-4 is the 2rem), so the thread scrolls in its own
 * viewport with the composer pinned beneath it. Nothing outside /chat changes.
 */
export function ChatShell({ children }: { children: ReactNode }) {
  const activeId = useActiveConversationId()
  const isMobile = useIsMobile()
  const [open, setOpen] = useState(false)

  return (
    <ChatRuntimeProvider>
      <div className="flex h-[calc(100svh-2rem)] min-h-0 gap-4">
        {isMobile ? null : (
          <aside className="flex w-64 shrink-0 flex-col border-r pr-2">
            <ConversationList activeId={activeId} />
          </aside>
        )}
        <section className="flex min-h-0 min-w-0 flex-1 flex-col">
          {isMobile && (
            <Sheet open={open} onOpenChange={setOpen}>
              <SheetTrigger
                render={<Button variant="ghost" size="icon" aria-label={CHAT_COPY.conversations} />}
              >
                <PanelLeftIcon />
              </SheetTrigger>
              <SheetContent side="left" className="p-2">
                <SheetTitle className="sr-only">{CHAT_COPY.conversations}</SheetTitle>
                <ConversationList activeId={activeId} onNavigate={() => setOpen(false)} />
              </SheetContent>
            </Sheet>
          )}
          {children}
        </section>
      </div>
    </ChatRuntimeProvider>
  )
}

/** /chat — a new conversation; nothing is created until the first send. */
export function NewChatPage() {
  return <Thread />
}

/** /chat/[conversationId] — one conversation, or not-found for an unknown or foreign id. */
export function ConversationPage() {
  const activeId = useActiveConversationId()
  const history = useListChatMessages(activeId ?? "", {
    query: { enabled: activeId !== null, meta: { silentError: true } },
  })

  if (history.error instanceof ApiError && history.error.status === 404) {
    return <ConversationNotFound />
  }
  if (history.isPending) return <ChatThreadSkeleton />
  return <Thread />
}

export function ChatThreadSkeleton() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 pt-4">
      <Skeleton className="ml-auto h-10 w-1/2 rounded-2xl" />
      <Skeleton className="h-24 w-3/4" />
      <Skeleton className="ml-auto h-10 w-1/3 rounded-2xl" />
    </div>
  )
}
```

`meta: { silentError: true }` stops `QueryProvider` toasting "Not found." on top of the not-found screen. Check that orval's query options accept `meta`; it's a TanStack option.

Pages (Server Components that render the client components):
- `app/(dashboard)/chat/layout.tsx`:

```tsx
import { ChatShell } from "@/components/chat/chat-shell"

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  return <ChatShell>{children}</ChatShell>
}
```

- `app/(dashboard)/chat/page.tsx`:

```tsx
import { NewChatPage } from "@/components/chat/chat-shell"

export default function ChatPage() {
  return <NewChatPage />
}
```

- `app/(dashboard)/chat/[conversationId]/page.tsx`:

```tsx
import { ConversationPage } from "@/components/chat/chat-shell"

export default function ConversationRoute() {
  return <ConversationPage />
}
```

- `app/(dashboard)/chat/loading.tsx`: a skeleton of both panes, using `Skeleton` from `@app/ui/skeleton`. A 16rem column of five `h-5` bars beside `ChatThreadSkeleton`. It never returns `null`.

`lib/hub-nav.ts`:

```ts
import { HomeIcon, MessageSquareIcon } from "lucide-react"
// …
export const HUB_NAV: NavItem[] = [
  { title: "Home", url: "/home", icon: HomeIcon },
  { title: "Chat", url: "/chat", icon: MessageSquareIcon },
]
```

Step 2 adds Transactions between Home and Chat; the merge takes the union.

- [ ] **Step 3: Run the whole web suite and checks**

Run from the repo root: `make check-web && make test-web`
Expected: PASS.

- [ ] **Step 4: Run the stack and check by hand**

Use the `run-stack` and `worktrees` skills. This worktree is slot 2: web 3020, API 8120, Postgres 5454. Start the stack natively with the `Dev:` tasks or their make equivalents, sign in, and go through each check:

- [ ] Chat appears in the sidebar after Home. `/chat` shows the welcome state and the conversation column.
- [ ] Sending a message creates a conversation. The URL becomes `/chat/<id>`, the reply streams in, and once it finishes, a title replaces "New chat" in the list.
- [ ] Stop mid-reply. "Stopped" shows under the partial text, and the server log has `stream_chat_client_disconnected`. Reload: the user message is there with no reply.
- [ ] Ask something that makes the assistant search the web, such as "what's the weather in Rome today". No raw search results appear in the reply.
- [ ] Rename with Enter, rename to blank (old name stays), and delete the open conversation (you land on `/chat`).
- [ ] Open `/chat/00000000-0000-0000-0000-000000000000`. You see the not-found screen.
- [ ] At phone width (≈390px), the list is behind the header button, opens as a sheet and closes on a pick.
- [ ] Home's layout is unchanged: same padding, and it scrolls as before. The page outside `/chat` has no outer scrollbar regression.

Record anything that fails as a fix in this task before committing.

- [ ] **Step 5: Commit**

```bash
cd web-app && pnpm exec prettier --write apps/web/src && cd ..
git add web-app/apps/web/src
git commit -m "feat(chat): the chat route, its sidebar entry and the mobile conversation sheet"
```

---

### Task 13: Docs, roadmap, and what the spec leaves behind

**Files:**
- Modify: `docs/product/features/chat.md`, `docs/data-model/conversation.md`, `docs/TODO.md`, `docs/architecture/web-app.md`, `docs/ROADMAP.md`
- Delete: the spec and this plan, in the PR's last commit, after the PR exists (see Step 5)

- [ ] **Step 1: `chat.md`**

- Header: `Last updated: <today>`. The Scope line says the screen shipped in step 3.
- §2 "What the user can do": rewrite for the screen.
  - Start a conversation from Chat in the sidebar.
  - The reply streams as it's written; Markdown is rendered.
  - **Stop** a reply. A stopped reply stays on screen, marked "Stopped", until the next send or until the user leaves, and isn't saved: reopening the conversation shows the question with no answer.
  - Conversations are listed newest first, under a title the assistant writes after the first reply. Rename and delete one at a time.
  - Keep the API bullets that still hold.
- §4 "Rules and edge cases":
  - Delete the "client that leaves mid-stream" bullet and the "No screen" bullet.
  - Add: a reply that fails mid-stream shows "The assistant couldn't reply. Try again." (server text is never shown); leaving a conversation mid-reply stops the model call; every LLM call goes through OpenRouter (`OPENROUTER_API_KEY`).
- §5 "Not built": remove "A chat page". Add "clear history from the screen" and "suggested prompts" (both deferred by decision on 13 Oct 2026).

- [ ] **Step 2: `data-model/conversation.md`**

- `Last updated: <today>`. The schema comment on `name` becomes `-- '' until titled; blanked on erasure`.
- Add **D3 — titles are written on request.**
  - An empty `name` means untitled.
  - After a completed reply, the client calls `POST /conversation/conversation/{id}/title`. The server asks the model for a title of at most 6 words from the first exchange, and saves it, capped at 100 characters.
  - A named conversation, or one with no reply yet, is returned unchanged. A model failure leaves it untitled, and the next completed reply retries.
  - Not generated in the stream, whose event shape is fixed.
- §3 Indexes, the `ix_conversation_created_at` row: "ordering by recency, newest first".
- §5 Deferred: delete the stale "A feature doc" bullet; `chat.md` exists.

- [ ] **Step 3: `TODO.md`, `architecture/web-app.md`, `ROADMAP.md`**

- **`TODO.md`**: delete the whole section **Server — the chat stream ignores a client disconnect**.
- **`architecture/web-app.md`**: add a short subsection where the doc covers the path to the API.
  - The chat screen uses assistant-ui's `ExternalStoreRuntime`. TanStack Query (the generated hooks) holds conversations and history; the runtime only renders them plus the in-flight exchange.
  - The stream is the one hand-written `fetch` (`apps/web/src/lib/chat/stream-chat.ts`), because orval excludes `streaming` routes. It reuses `resolveBaseUrl` and `toastForError` from `@app/api-client`.
- **`ROADMAP.md`**, row 3:
  - Description: `**3 Chat screen** — the conversations UI on the existing `conversation` module; stops the stream on a client disconnect (WS7); moves the LLM provider to OpenRouter`
  - State: `complete — [PR #N](<url>) into `template-base`; reaches `main` at Cutover`. The PR number gets filled in after the PR exists, in Step 5.
  - "Where it is specified": drop "No spec yet" and the `TODO.md` reference.

- [ ] **Step 4: Commit the docs**

```bash
git add docs
git commit -m "docs: chat screen, titles and OpenRouter; WS7 closed"
```

- [ ] **Step 5: At PR time (in `finishing-a-development-branch`)**

After `gh pr create --base template-base`:
1. Put the PR URL into the ROADMAP row.
2. `git rm .superpowers/specs/2026-10-13-chat-screen-design.md .superpowers/plans/2026-10-13-chat-screen.md`
3. Commit `docs: chat screen complete; spec and plan retired` and push.

The PR description must include this line:

> **Env:** every existing `server/.env.<env>` (local, worktree and deployed) needs `OPENAI_API_KEY` renamed to `OPENROUTER_API_KEY`, and model names prefixed `openai/` (`DEFAULT_LLM_MODEL`, `EVALUATION_LLM`, any `LONG_TERM_MEMORY_*MODEL`). `LLM_BASE_URL` has a default (`https://openrouter.ai/api/v1`) and needs no entry.
