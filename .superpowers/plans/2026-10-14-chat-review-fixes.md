# Chat Screen Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the bug and config findings from the thermos review of PR #11 (`feat/chat-screen` into `template-base`). Then do the four structural refactors the user approved, without changing behaviour.

**Architecture:**
- **Server (Tasks 1–3):** the history goes through a cleaning step before every model call; model ids are checked when settings load; title generation moves behind one agent method.
- **Web (Tasks 4–7):**
  - Error silencing moves into `QueryProvider` as a typed predicate.
  - The chat stream shares the generated hooks' fetch layer.
  - The chat runtime provider becomes a thin React shell over a pure reducer (`lib/chat/exchange.ts`) and cache helpers (`lib/chat/chat-cache.ts`).

**Tech Stack:**
- Server: FastAPI, LangGraph, langchain-core 1.6, pydantic-settings, mem0, pytest (`asyncio_mode = auto`).
- Web: Next.js 16, React 19, TanStack Query v5, assistant-ui `ExternalStoreRuntime`, Vitest + Testing Library.

**Spec:** none written. This plan implements the thermos review of PR #11; the findings are summarised under **Background**.

## Global Constraints

- **Where to work:**
  - Worktree: `/Users/tizianoiacovelli/projects/personal-finance-app/.claude/worktrees/chat-screen`, branch `feat/chat-screen`. The base is `template-base`.
  - Never run `make clean` or `make rebuild` in a worktree.
- **API contract:**
  - No route signatures change. `make check-contract` must pass with no diff.
  - Never hand-edit `server/openapi.json` or `web-app/packages/api-client/src/generated/`.
- **Server conventions:**
  - `async def`, type hints on every signature, all imports at the top of the file.
  - structlog event names in `lowercase_with_underscores`, with variables as kwargs.
  - Log a failure with `logger.exception`.
- **Web conventions:**
  - kebab-case file names, Base UI (`render` prop, not `asChild`, in new code).
  - API types come only from `@app/api-client`.
  - Tests sit beside their subject as `*.test.ts(x)`.
- **How to run tests:**
  - Server, from `server/`: `APP_ENV=test uv run pytest <path> -v`. Integration tests need Docker running.
  - Web, from `web-app/`: `pnpm -s vitest run <path>`. Type-check with `pnpm -s type-check`.
- **Checks:** `make check-server` and `make check-web` from the repo root run ruff, import contracts, ESLint and Prettier.
- **Behaviour-preservation rule for Task 7:** do not edit `chat-runtime-provider.test.tsx` in Task 7. It is the safety net. Task 6 changes exactly one assertion in it.

## Review Focus

1. **Stop during a web search, then send again in the same conversation.** The reply arrives normally, with no provider 400 and no model rotation. Task 1, `test_chat_does_not_send_a_tool_call_left_without_a_result`.
2. **An env file written for the OpenAI API** (`DEFAULT_LLM_MODEL=gpt-4o-mini`). The server refuses to start, and the error names the `provider/model` form. Task 2, `TestOpenRouterModelIds`.
3. **First turn stopped before any reply, second turn completed.** The title is written from the second question and its answer. Task 3, `test_first_exchange_pairs_the_first_reply_with_the_question_it_answered`.
4. **A refused stream whose error body is JSON** (a 429 from the rate limiter). `ApiError.body` is the parsed object, the same as from a generated hook. Task 6, `useApiRequest` › `throws ApiError with the JSON error body parsed`.
5. **An unknown conversation id, a malformed one, and a 500 on the history.**
   - The unknown id shows not-found with no toast; the malformed id does the same.
   - The 500 toasts once.
   - The existing `conversation-page.test.tsx` tests already pin this. They stay unchanged through Tasks 5 and 7, and Task 5 adds `QueryProvider` tests for the predicate itself.

## Background (the review findings this plan acts on)

| # | Finding | Task |
|---|---|---|
| H1 | A Stop or leave during the `tool_call` node leaves an `AIMessage(tool_calls)` with no `ToolMessage` in the checkpoint. Every later model call gets a 400, retried and rotated through every model. | 1 |
| M1 | Nothing rejects an old, unprefixed model id. mem0 given an empty key falls back to `OPENAI_API_KEY` and sends it to openrouter.ai (verified in `mem0/llms/openai.py`). | 2 |
| L1 | `.env.example` sets `OPENROUTER_API_KEY=change-me`. It was empty before, and the key is optional. | 2 |
| L2 / Q4 | The title is built from the first user message and the first reply taken separately, so a stopped first turn mixes two turns. The agent's `generate_title` only passes through. An empty title raises `ValueError`, and a failure is logged with `warning`. | 3 |
| Q5 | `_chunk_text` re-implements `BaseMessage.text` (langchain-core 1.6.1, verified). | 3 |
| Q7 | `NewChatPage` only wraps `<Thread />`. The `welcome` prop is never passed. `chat-shell.tsx` holds three unrelated components. | 4 |
| Q2 | `ConversationPage` copies `QueryProvider`'s toast rule into an effect, because `silentError` can't depend on the error. | 5 |
| Q9 | `docs/architecture/web-app.md` says "A mutation always toasts" and that `QueryProvider` is untested; `docs/TODO.md` says the same. | 5 |
| Q3 | `stream-chat.ts` re-implements `useApiFetch`'s transport, and reads the error body as text where the hooks parse JSON. | 6 |
| Q1 / Q6 | `ChatRuntimeProvider` tracks one send in six places, `onNew` is 140 lines, and the list cache edits are copy-pasted. | 7 |

**Declined after verification, so no task:**
- `EvaluationSettings`' `os.getenv` fallback works: every launcher exports the env file (`scripts/set_env.sh`, compose `env_file`), and `test_evaluation_key_falls_back_to_the_openrouter_key` pins it.
- The stream-vs-history test for a tool-call turn already exists: `test_history_joins_a_turns_assistant_messages_as_they_were_streamed`.
- Renaming `test-runtime.tsx`: the repo has no test-helper naming convention to follow.
- An explicit "last send was stopped" field in place of the history query's `isInvalidated`: the query cache already keeps that flag per conversation across navigation. Task 7 only names it (`historyNeedsRefetch`).

**Correction to the review:** Q1 said the provider's "is this exchange on screen" rule is written twice. On reading, the two are different rules, on purpose:
- **Rendering** shows the exchange on its own conversation, and on `/chat` while a first send's URL catches up.
- **Leaving** drops it on any move to another URL, `/chat` included.

Task 7 names both and keeps both.

---

## File Map

**Server**
- `server/app/agents/graph.py`: add `drop_unanswered_tool_calls`.
- `server/app/agents/chatbot/graph.py`:
  - `_chat` cleans the history before the model call.
  - `generate_title` is replaced by `title_for`.
- `server/app/agents/chatbot/title.py`: add `first_exchange`; `generate_title` returns `str | None` and reads `.text`.
- `server/app/agents/base/agent.py`: `_chunk_text` is replaced by `token.text`.
- `server/app/agents/shared/memory/factory.py`: refuse to build mem0 with an empty key.
- `server/app/core/config.py`: add the `OpenRouterModel` validated type on four fields.
- `server/app/modules/conversation/service.py`: `generate_title` keeps only the policy; the `TYPE_CHECKING` import goes.
- `server/.env.example`: an empty `OPENROUTER_API_KEY`.
- Tests:
  - new `tests/unit/agents/test_drop_unanswered_tool_calls.py`
  - `tests/unit/agents/chatbot/test_graph.py`
  - `tests/unit/agents/chatbot/test_title.py`
  - `tests/unit/agents/test_base_agent.py`
  - `tests/unit/config/test_settings.py`
  - `tests/unit/agents/memory/test_memory_factory.py`
  - `tests/integration/modules/conversation/router/test_conversation.py`

**Web** (paths under `web-app/`)
- `packages/api-client/src/query-meta.ts` (new): the `AppMeta` type, its TanStack `Register` augmentation, and `isSilenced`.
- `packages/api-client/src/query-provider.tsx`: uses `isSilenced`.
- `packages/api-client/src/use-api-fetch.ts`:
  - adds a private `apiRequest` and an exported `useApiRequest` / `ApiRequest`;
  - `useApiFetch` is built on them;
  - `resolveBaseUrl` stops being exported.
- `packages/api-client/src/index.ts`: exports `useApiRequest` and `ApiRequest`, and no longer `resolveBaseUrl`.
- `apps/web/src/lib/chat/stream-chat.ts`: takes `request: ApiRequest` in place of `token`.
- `apps/web/src/lib/chat/exchange.ts` (new): `Send`, `Exchange`, `exchangeReducer`, `showsExchange`, `toThreadMessages`.
- `apps/web/src/lib/chat/chat-cache.ts` (new): the query-cache edits for the conversation list and chat history.
- `apps/web/src/components/chat/chat-runtime-provider.tsx`: rewritten over the two new modules.
- `apps/web/src/components/chat/conversation-page.tsx` (new, split from `chat-shell.tsx`).
- `apps/web/src/components/chat/chat-thread-skeleton.tsx` (new, split from `chat-shell.tsx`).
- `apps/web/src/components/chat/chat-shell.tsx`: `ChatShell` only.
- `apps/web/src/components/chat/thread.tsx`: the `welcome` prop is removed.
- `apps/web/src/components/chat/conversation-list.tsx`: uses `chat-cache`.
- Route files:
  - `apps/web/src/app/(dashboard)/chat/page.tsx`
  - `apps/web/src/app/(dashboard)/chat/[conversationId]/page.tsx`
  - `apps/web/src/app/(dashboard)/chat/loading.tsx`
- Tests:
  - `query-provider.test.tsx`
  - `use-api-fetch.test.ts`
  - `stream-chat.test.ts`
  - new `exchange.test.ts`
  - `chat-shell.test.tsx` moved to `conversation-page.test.tsx`
  - one line in `chat-runtime-provider.test.tsx` (Task 6)

**Docs**
- `docs/architecture/web-app.md`: §5 *API access* and *The chat screen*, and §7.
- `docs/TODO.md`: **Web — tests the suite does not have yet**.
- `docs/guides/api-client-codegen.md` §6.1: the copy of `use-api-fetch.ts`.

---

### Task 1: Clean unanswered tool calls out of the history before every model call

**Files:**
- Modify: `server/app/agents/graph.py`
- Modify: `server/app/agents/chatbot/graph.py` (imports, and `_chat` around line 85)
- Create: `server/tests/unit/agents/test_drop_unanswered_tool_calls.py`
- Modify: `server/tests/unit/agents/chatbot/test_graph.py`

**Interfaces:**
- Produces: `drop_unanswered_tool_calls(messages: list[BaseMessage]) -> list[BaseMessage]` in `app.agents.graph`.

- [ ] **Step 1: Write the failing unit tests for the helper**

Create `server/tests/unit/agents/test_drop_unanswered_tool_calls.py`:

```python
"""drop_unanswered_tool_calls: a tool call left without its result never reaches the model."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agents.graph import drop_unanswered_tool_calls

pytestmark = pytest.mark.unit


def _call(call_id: str) -> dict:
    return {"name": "web_search", "args": {"query": "rent"}, "id": call_id}


def test_an_answered_tool_call_is_kept():
    history = [
        HumanMessage(content="Rent prices?"),
        AIMessage(content="", tool_calls=[_call("call_1")]),
        ToolMessage(content="results", tool_call_id="call_1"),
        AIMessage(content="About 1200 EUR."),
    ]
    assert drop_unanswered_tool_calls(history) == history


def test_an_unanswered_tool_call_with_no_text_is_dropped():
    question, retry = HumanMessage(content="Rent prices?"), HumanMessage(content="Never mind")
    history = [question, AIMessage(content="", tool_calls=[_call("call_1")]), retry]
    assert drop_unanswered_tool_calls(history) == [question, retry]


def test_an_unanswered_tool_calls_text_is_kept_without_the_call():
    history = [
        HumanMessage(content="Rent prices?"),
        AIMessage(content="Let me check.", tool_calls=[_call("call_1")], id="m1"),
        HumanMessage(content="Never mind"),
    ]
    cleaned = drop_unanswered_tool_calls(history)
    assert [m.content for m in cleaned] == ["Rent prices?", "Let me check.", "Never mind"]
    assert cleaned[1].tool_calls == []
    assert cleaned[1].id == "m1"


def test_a_partly_answered_message_is_dropped_with_its_results():
    # The tool node answers every call of a message at once, so a partial
    # answer is not expected; if one appears, a lone ToolMessage is as
    # unacceptable to the provider as a lone call.
    history = [
        HumanMessage(content="Two searches"),
        AIMessage(content="", tool_calls=[_call("call_1"), _call("call_2")]),
        ToolMessage(content="first", tool_call_id="call_1"),
        HumanMessage(content="Next"),
    ]
    assert [m.content for m in drop_unanswered_tool_calls(history)] == ["Two searches", "Next"]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/agents/test_drop_unanswered_tool_calls.py -v`
Expected: FAIL with `ImportError: cannot import name 'drop_unanswered_tool_calls'`.

- [ ] **Step 3: Implement the helper**

In `server/app/agents/graph.py`, change the import line `from langchain_core.messages import BaseMessage` to:

```python
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    ToolMessage,
)
```

Then add this function after `process_llm_response`:

```python
def drop_unanswered_tool_calls(messages: list[BaseMessage]) -> list[BaseMessage]:
    """The history without tool calls that never got their result.

    A turn stopped while its tool ran (Stop, or leaving the conversation: the
    stream's cancellation reaches the graph) leaves the model's tool-call
    message in the checkpoint with no ToolMessage after it. Providers reject
    such a history with a 400, on that turn and on every later one. The call
    is dropped, with any result it did get, and the text the model wrote
    beside it is kept.
    """
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    dropped: set[str] = set()
    kept: list[BaseMessage] = []
    for message in messages:
        if isinstance(message, AIMessage) and any(call["id"] not in answered for call in message.tool_calls):
            dropped.update(call["id"] for call in message.tool_calls)
            if message.text:
                kept.append(AIMessage(content=str(message.text), id=message.id))
            continue
        if isinstance(message, ToolMessage) and message.tool_call_id in dropped:
            continue
        kept.append(message)
    return kept
```

- [ ] **Step 4: Run the helper tests to verify they pass**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/agents/test_drop_unanswered_tool_calls.py -v`
Expected: 4 passed.

- [ ] **Step 5: Write the failing node-level regression test**

In `server/tests/unit/agents/chatbot/test_graph.py`, add to the imports:

```python
from unittest.mock import AsyncMock, MagicMock

from langchain_core.messages import AIMessage, HumanMessage

from app.agents.chatbot.state import GraphState
from app.integrations.llm.service import LLMRegistry
```

Append:

```python
class TestChat:
    """Tests for `_chat` — what the chat node sends to the model."""

    @pytest.mark.asyncio
    async def test_chat_does_not_send_a_tool_call_left_without_a_result(self, agent):
        """Stop during a web search, then send again: the next call must not 400.

        The chat node's AIMessage is checkpointed before the tool node runs; a
        cancelled tool node leaves it there with no ToolMessage, and the next
        turn appends a HumanMessage after it.
        """
        agent.llm_service = MagicMock()
        agent.llm_service.get_llm.return_value = LLMRegistry.get(LLMRegistry.get_all_names()[0])
        agent.llm_service.current_model_name.return_value = LLMRegistry.get_all_names()[0]
        agent.llm_service.call = AsyncMock(return_value=AIMessage(content="Sure."))
        state = GraphState(
            messages=[
                HumanMessage(content="Search rent prices"),
                AIMessage(content="", tool_calls=[{"name": "web_search", "args": {"query": "rent"}, "id": "call_1"}]),
                HumanMessage(content="Never mind, thanks"),
            ]
        )

        await agent._chat(state, {"configurable": {"thread_id": "t1"}})

        sent = agent.llm_service.call.call_args.args[0]
        assert not any(m.get("tool_calls") for m in sent)
        assert [m["content"] for m in sent[1:]] == ["Search rent prices", "Never mind, thanks"]
```

- [ ] **Step 6: Run it to verify it fails**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/agents/chatbot/test_graph.py::TestChat -v`
Expected: FAIL on `assert not any(...)`. The `AIMessage` with `tool_calls` is still in `sent`.

- [ ] **Step 7: Use the helper in `_chat`**

In `server/app/agents/chatbot/graph.py`, add `drop_unanswered_tool_calls` to the `from app.agents.graph import (...)` block (alphabetical, before `dump_messages`). In `_chat`, replace:

```python
        messages = prepare_messages(state.messages, current_llm, system_prompt)
```

with:

```python
        messages = prepare_messages(drop_unanswered_tool_calls(state.messages), current_llm, system_prompt)
```

- [ ] **Step 8: Run the agent unit tests**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/agents -v`
Expected: all pass, including `TestChat` and the four helper tests.

- [ ] **Step 9: Commit**

```bash
git add server/app/agents/graph.py server/app/agents/chatbot/graph.py server/tests/unit/agents/test_drop_unanswered_tool_calls.py server/tests/unit/agents/chatbot/test_graph.py
git commit -m "fix(agents): a tool call stopped before its result no longer breaks the conversation"
```

---

### Task 2: Reject unprefixed model ids at startup; keep the OpenAI key away from OpenRouter

**Files:**
- Modify: `server/app/core/config.py` (imports at lines 8–20; fields at 107, 119–120, 221)
- Modify: `server/app/agents/shared/memory/factory.py` (`create_memory`)
- Modify: `server/.env.example:15`
- Modify: `server/tests/unit/config/test_settings.py`
- Modify: `server/tests/unit/agents/memory/test_memory_factory.py`

**Interfaces:**
- Produces: `OpenRouterModel` (an annotated `str`) in `app.core.config`. Nothing else consumes it.

- [ ] **Step 1: Write the failing settings tests**

Append to `server/tests/unit/config/test_settings.py`:

```python
class TestOpenRouterModelIds:
    """Every model id names its provider: an env file written for the OpenAI API fails at startup."""

    @pytest.mark.parametrize(
        "build",
        [
            lambda: LLMSettings(DEFAULT_LLM_MODEL="gpt-4o-mini"),
            lambda: MemorySettings(MODEL="gpt-5-nano"),
            lambda: MemorySettings(EMBEDDER_MODEL="text-embedding-3-small"),
            lambda: EvaluationSettings(LLM="gpt-5"),
        ],
        ids=["chat", "memory", "embedder", "evaluation"],
    )
    def test_an_unprefixed_model_id_fails(self, build):
        with pytest.raises(ValidationError, match="provider/model"):
            build()

    def test_a_prefixed_model_id_passes(self):
        assert LLMSettings(DEFAULT_LLM_MODEL="openai/gpt-4o-mini").DEFAULT_LLM_MODEL == "openai/gpt-4o-mini"
```

Then change the file's imports to:

```python
import pytest
from pydantic import ValidationError

from app.core.config import AuthSettings, Environment, EvaluationSettings, LLMSettings, MemorySettings, get_environment
```

Remove the now-redundant `from app.core.config import EvaluationSettings` inside `test_evaluation_key_falls_back_to_the_openrouter_key`.

- [ ] **Step 2: Run them to verify they fail**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/config/test_settings.py::TestOpenRouterModelIds -v`
Expected: 4 FAIL with `DID NOT RAISE`; 1 pass.

- [ ] **Step 3: Add the validated type and apply it**

In `server/app/core/config.py`, change `from typing import List` to `from typing import Annotated, List`, and add `AfterValidator,` to the `from pydantic import (...)` block. Above `# Database Settings`, add:

```python
def _require_provider_prefix(model: str) -> str:
    """An OpenRouter model id names its provider: "openai/gpt-5-mini", not "gpt-5-mini".

    Every LLM call goes through OpenRouter. An unprefixed id, left over from an
    env file written for the OpenAI API, fails here at startup rather than as a
    silent fallback model or a long-term memory that quietly stops working.
    """
    if "/" not in model:
        raise ValueError(f"{model!r} is not an OpenRouter model id: expected provider/model, such as 'openai/{model}'")
    return model


OpenRouterModel = Annotated[str, AfterValidator(_require_provider_prefix)]
```

Change the four fields' types (the defaults stay as they are):
- `LLMSettings.DEFAULT_LLM_MODEL: OpenRouterModel = "openai/gpt-5-mini"`
- `MemorySettings.MODEL: OpenRouterModel = "openai/gpt-5-nano"`
- `MemorySettings.EMBEDDER_MODEL: OpenRouterModel = "openai/text-embedding-3-small"`
- `EvaluationSettings.LLM: OpenRouterModel = "openai/gpt-5"`

- [ ] **Step 4: Run the settings tests**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/config -v`
Expected: all pass. `.env.test` already uses prefixed ids, so `settings = Settings()` still loads.

- [ ] **Step 5: Write the failing memory-factory test**

In `server/tests/unit/agents/memory/test_memory_factory.py`, add `from pydantic import SecretStr` to the imports and append:

```python
async def test_create_memory_refuses_an_empty_key():
    """Given an empty key, mem0's OpenAI client falls back to OPENAI_API_KEY from
    the environment and sends that secret to OpenRouter's base URL."""
    fake_cls = MagicMock()
    with (
        patch.object(factory, "AsyncMemory", fake_cls),
        patch.object(settings.llm, "OPENROUTER_API_KEY", SecretStr("")),
    ):
        with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
            await factory.create_memory()

    fake_cls.from_config.assert_not_called()
```

- [ ] **Step 6: Run it to verify it fails**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/agents/memory/test_memory_factory.py::test_create_memory_refuses_an_empty_key -v`
Expected: FAIL with `DID NOT RAISE`.

- [ ] **Step 7: Guard `create_memory`**

In `server/app/agents/shared/memory/factory.py`, inside `create_memory`, put this directly under `if _memory_instance is None:` and before the existing comment about `from_config`:

```python
        # Checked before mem0 sees the config: given an empty key, its OpenAI
        # client falls back to OPENAI_API_KEY from the environment and would
        # send that secret to OpenRouter. Callers log this and carry on with no
        # long-term memory, as they do for any other memory failure.
        if not settings.llm.OPENROUTER_API_KEY.get_secret_value():
            raise RuntimeError("OPENROUTER_API_KEY is not set: long-term memory needs it")
```

- [ ] **Step 8: Empty the example key**

In `server/.env.example`, change `OPENROUTER_API_KEY=change-me` to `OPENROUTER_API_KEY=`. The comment above it already says the key is optional, and an empty key fails at once, where `change-me` goes through every retry and model first. Leave `server/.env.test` alone: its non-empty placeholder is what lets unit tests build clients.

- [ ] **Step 9: Run the memory and config tests, then the checks**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/agents/memory tests/unit/config -v`
Expected: all pass. The existing factory tests run under `.env.test`'s non-empty key.

Run: `make check-server` (repo root)
Expected: clean.

- [ ] **Step 10: Commit**

```bash
git add server/app/core/config.py server/app/agents/shared/memory/factory.py server/.env.example server/tests/unit/config/test_settings.py server/tests/unit/agents/memory/test_memory_factory.py
git commit -m "fix(config): an unprefixed model id fails at startup; mem0 never sees an empty key"
```

---

### Task 3: The agent owns the title; `.text` replaces hand-rolled extraction

**Files:**
- Modify: `server/app/agents/chatbot/title.py`
- Modify: `server/app/agents/chatbot/graph.py` (`generate_title` method at lines 116–122; imports)
- Modify: `server/app/agents/base/agent.py` (delete `_chunk_text` at 37–47; stream loop at ~131)
- Modify: `server/app/modules/conversation/service.py` (imports at 1–18; `generate_title` at 77–100)
- Modify: `server/tests/unit/agents/chatbot/test_title.py`
- Modify: `server/tests/unit/agents/chatbot/test_graph.py`
- Modify: `server/tests/unit/agents/test_base_agent.py`
- Modify: `server/tests/integration/modules/conversation/router/test_conversation.py` (`TestGenerateConversationTitle`)

**Interfaces:**
- Produces:
  - `first_exchange(history: list[Message]) -> tuple[str, str] | None` in `app.agents.chatbot.title`.
  - `generate_title(user_text, reply_text, model_name, conversation_id, user_id) -> str | None`. It no longer raises on an empty title.
  - `ChatbotAgent.title_for(conversation_id: uuid.UUID, user_id: uuid.UUID) -> Optional[str]`, which replaces `ChatbotAgent.generate_title`.
- Consumes: nothing from Tasks 1–2.

- [ ] **Step 1: Write the failing `title.py` tests**

In `server/tests/unit/agents/chatbot/test_title.py`:
- Change the import to `from app.agents.chatbot.title import TITLE_MAX_LENGTH, clean_title, first_exchange, generate_title`.
- Add `from app.agents.messages import Message`.
- Replace `test_empty_title_raises` with:

```python
async def test_an_empty_title_is_none():
    with patch("app.agents.chatbot.title.LLMRegistry.get", return_value=_fake_llm('  ""  ')):
        assert await generate_title("a", "b", "openai/gpt-5-mini", CONVERSATION_ID, USER_ID) is None


def test_first_exchange_pairs_the_first_reply_with_the_question_it_answered():
    # A first turn stopped before any reply leaves its question unanswered:
    # the title must not pair it with the second turn's answer.
    history = [
        Message(role="user", content="stopped question"),
        Message(role="user", content="answered question"),
        Message(role="assistant", content="the answer"),
        Message(role="user", content="a follow-up"),
    ]
    assert first_exchange(history) == ("answered question", "the answer")


def test_first_exchange_is_none_before_any_reply():
    assert first_exchange([Message(role="user", content="hi")]) is None
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/agents/chatbot/test_title.py -v`
Expected: collection ERROR, `cannot import name 'first_exchange'`.

- [ ] **Step 3: Implement in `title.py`**

In `server/app/agents/chatbot/title.py`:
- Replace `from app.agents.graph import process_llm_response` with `from app.agents.messages import Message`.
- Add after `clean_title`:

```python
def first_exchange(history: list[Message]) -> tuple[str, str] | None:
    """The first reply and the user message it answered, or None before any reply.

    Paired, not taken separately: a first turn stopped before its reply leaves
    a question with no answer, and the title must not mix two turns.
    """
    for index, message in enumerate(history):
        if message.role == "assistant":
            question = next((m.content for m in reversed(history[:index]) if m.role == "user"), None)
            return (question, message.content) if question else None
    return None
```

Change `generate_title`'s return annotation to `-> str | None`. Its docstring's first line becomes `"""Ask the model for a title; None if it answers with nothing usable. Model errors propagate.`. Its last four lines become:

```python
    return clean_title(response.text) or None
```

- [ ] **Step 4: Run the title tests**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/agents/chatbot/test_title.py -v`
Expected: all pass. `test_generate_title_flattens_structured_content` still passes, because `.text` keeps only `type: "text"` blocks.

- [ ] **Step 5: Write the failing `title_for` tests**

In `server/tests/unit/agents/chatbot/test_graph.py`, add to the imports:

```python
import uuid
from unittest.mock import patch

from app.agents.messages import Message
```

Merge `patch` into the `unittest.mock` import from Task 1. Then append:

```python
class TestTitleFor:
    """Tests for `title_for` — a conversation's title from its first exchange."""

    CONVERSATION_ID = uuid.uuid4()
    USER_ID = uuid.uuid4()

    async def test_titles_the_first_exchange_on_the_current_model(self, agent):
        agent.get_chat_history = AsyncMock(
            return_value=[Message(role="user", content="Q"), Message(role="assistant", content="A")]
        )
        with patch("app.agents.chatbot.graph.generate_title", new=AsyncMock(return_value="Budget")) as generate:
            assert await agent.title_for(self.CONVERSATION_ID, self.USER_ID) == "Budget"
        generate.assert_awaited_once_with(
            "Q", "A", agent.llm_service.current_model_name(), self.CONVERSATION_ID, self.USER_ID
        )

    async def test_no_reply_yet_is_none_without_a_model_call(self, agent):
        agent.get_chat_history = AsyncMock(return_value=[Message(role="user", content="Q")])
        with patch("app.agents.chatbot.graph.generate_title", new=AsyncMock()) as generate:
            assert await agent.title_for(self.CONVERSATION_ID, self.USER_ID) is None
        generate.assert_not_awaited()

    async def test_a_model_failure_is_none(self, agent):
        agent.get_chat_history = AsyncMock(
            return_value=[Message(role="user", content="Q"), Message(role="assistant", content="A")]
        )
        with patch("app.agents.chatbot.graph.generate_title", new=AsyncMock(side_effect=RuntimeError("down"))):
            assert await agent.title_for(self.CONVERSATION_ID, self.USER_ID) is None
```

- [ ] **Step 6: Run them to verify they fail**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/agents/chatbot/test_graph.py::TestTitleFor -v`
Expected: FAIL with `AttributeError: 'ChatbotAgent' object has no attribute 'title_for'`.

- [ ] **Step 7: Replace the agent's pass-through with `title_for`**

In `server/app/agents/chatbot/graph.py`, change `from app.agents.chatbot.title import generate_title` to `from app.agents.chatbot.title import first_exchange, generate_title`. Replace the whole `async def generate_title(...)` method with:

```python
    async def title_for(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Optional[str]:
        """A title for a conversation from its first exchange, on the current model, or None.

        None before the first reply, or when the model fails or answers with
        nothing usable: a title is cosmetic, and the client asks again after the
        next completed reply.
        """
        exchange = first_exchange(await self.get_chat_history(conversation_id))
        if exchange is None:
            return None
        user_text, reply_text = exchange
        try:
            return await generate_title(
                user_text, reply_text, self.llm_service.current_model_name(), conversation_id, user_id
            )
        except Exception:
            logger.exception("conversation_title_generation_failed", conversation_id=conversation_id)
            return None
```

- [ ] **Step 8: Run the graph tests**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/agents/chatbot -v`
Expected: all pass.

- [ ] **Step 9: Update the integration tests to the new agent method**

In `server/tests/integration/modules/conversation/router/test_conversation.py`, class `TestGenerateConversationTitle`:
- In `test_untitled_conversation_gets_a_title`: `mock_agent.title_for = AsyncMock(return_value="Grocery budget")`, and assert `mock_agent.title_for.assert_awaited_once_with(untitled_conversation.id, untitled_conversation.user_id)`.
- In `test_named_conversation_is_unchanged`: `mock_agent.title_for = AsyncMock(return_value="Other")` and `mock_agent.title_for.assert_not_awaited()`.
- In `test_rename_during_the_model_call_wins`: `mock_agent.title_for = AsyncMock(side_effect=rename_then_title)`.
- Replace both `test_no_reply_yet_is_unchanged` and `test_model_failure_returns_200_unchanged` with:

```python
    async def test_no_title_leaves_the_conversation_unchanged(
        self, authenticated_client_with_agent, untitled_conversation, mock_agent
    ):
        # The agent answers None for no reply yet or a failed model call
        # (unit-tested on ChatbotAgent.title_for); the route still answers 200.
        mock_agent.title_for = AsyncMock(return_value=None)
        response = await authenticated_client_with_agent.post(self._url(untitled_conversation.id))
        assert response.status_code == 200
        assert response.json()["name"] == ""
```

- [ ] **Step 10: Reduce the service to its policy**

In `server/app/modules/conversation/service.py`:
- Remove `TYPE_CHECKING,` from the `typing` import and delete the `if TYPE_CHECKING:` block.
- Add `from app.agents.chatbot.graph import ChatbotAgent` with the other `app.` imports. `app.modules.conversation.dependencies` already imports it at runtime, and nothing in `app/agents` imports `app.modules`, so no cycle.
- Replace `generate_title` with:

```python
    @staticmethod
    async def generate_title(session: AsyncSession, conversation: Conversation, agent: ChatbotAgent) -> Conversation:
        """Name an untitled conversation from its first exchange.

        A no-op for a named conversation, and for one the agent has no title for
        (no reply yet, or the model failed).
        """
        if conversation.name:
            return conversation

        title = await agent.title_for(conversation.id, conversation.user_id)
        if title is None:
            return conversation

        # The model call takes seconds: a rename made meanwhile wins.
        return await conversation_repository.set_name_if_untitled(session, conversation, title)
```

If `logger` is now unused in `service.py`, remove its import; `ruff check` reports it as F401.

- [ ] **Step 11: Replace `_chunk_text` with `.text`**

In `server/app/agents/base/agent.py`, delete `_chunk_text` (the function and its docstring), and change `text = _chunk_text(token.content)` to `text = token.text`.

In `server/tests/unit/agents/test_base_agent.py`, change `from app.agents.base.agent import BaseAgent, _chunk_text` to `from app.agents.base.agent import BaseAgent`, and delete `test_chunk_text_handles_strings_and_blocks`.

Then add one test pinning that structured content still streams:

```python
@pytest.mark.asyncio
async def test_structured_content_streams_only_its_text():
    """GPT-5 sends content as blocks; only the text blocks are the reply."""
    chunks = await _collect(
        [AIMessageChunk(content=[{"type": "reasoning", "id": "r"}, {"type": "text", "text": "Hi"}])]
    )
    assert chunks == ["Hi"]
```

- [ ] **Step 12: Run the server suites and checks**

Run: `cd server && APP_ENV=test uv run pytest tests/unit -v -m unit`
Expected: all pass.

Run: `cd server && APP_ENV=test uv run pytest tests/integration/modules/conversation -v -m integration` (Docker must be running)
Expected: all pass.

Run: `make check-server && make check-contract` (repo root)
Expected: clean, with no contract diff (no route changed).

- [ ] **Step 13: Commit**

```bash
git add server/app/agents server/app/modules/conversation/service.py server/tests
git commit -m "refactor(chat): the agent owns the title, from the first reply and its question"
```

---

### Task 4: Split `chat-shell.tsx`; drop the unused wrapper and prop

**Files:**
- Create: `web-app/apps/web/src/components/chat/conversation-page.tsx`
- Create: `web-app/apps/web/src/components/chat/chat-thread-skeleton.tsx`
- Modify: `web-app/apps/web/src/components/chat/chat-shell.tsx`
- Modify: `web-app/apps/web/src/components/chat/thread.tsx`
- Modify: `web-app/apps/web/src/app/(dashboard)/chat/page.tsx`
- Modify: `web-app/apps/web/src/app/(dashboard)/chat/[conversationId]/page.tsx`
- Modify: `web-app/apps/web/src/app/(dashboard)/chat/loading.tsx`
- Move: `chat-shell.test.tsx` → `conversation-page.test.tsx`

**Interfaces:**
- Produces:
  - `ConversationPage` from `@/components/chat/conversation-page`.
  - `ChatThreadSkeleton` from `@/components/chat/chat-thread-skeleton`.
  - `Thread()` with no props.

This is a move with no behaviour change. The moved tests are the check.

- [ ] **Step 1: Create `chat-thread-skeleton.tsx`**

```tsx
import { Skeleton } from "@app/ui/skeleton"

/** The thread pane while a conversation's history loads. */
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

- [ ] **Step 2: Create `conversation-page.tsx`**

This is the current `ConversationPage` moved as is. Task 5 changes its error handling.

```tsx
"use client"

import { ApiError, toastForError } from "@app/api-client"
import { useEffect } from "react"

import { ChatThreadSkeleton } from "./chat-thread-skeleton"
import { useActiveConversationId, useChatHistory } from "./chat-runtime-provider"
import { ConversationNotFound } from "./conversation-not-found"
import { Thread } from "./thread"

/** /chat/[conversationId] — one conversation, or not-found for an unknown, foreign or malformed id. */
export function ConversationPage() {
  const activeId = useActiveConversationId()
  const history = useChatHistory(activeId)
  // A malformed id is answered 422 by the path's UUID validation: to the user
  // it is a conversation that doesn't exist, the same as a 404.
  const notFound =
    history.error instanceof ApiError &&
    (history.error.status === 404 || history.error.status === 422)

  // useChatHistory's silentError keeps QueryProvider from toasting, and a
  // query's meta can't depend on the status. So the toast it would have shown
  // is raised here, for every error but the not-found below.
  const hasData = history.data !== undefined
  useEffect(() => {
    // Mirrors QueryProvider's rule: a failed refetch behind shown data stays silent.
    if (history.error && !notFound && !hasData) toastForError(history.error)
  }, [history.error, notFound, hasData])

  if (notFound) return <ConversationNotFound />
  if (history.isPending) return <ChatThreadSkeleton />
  return <Thread />
}
```

- [ ] **Step 3: Cut `chat-shell.tsx` down to `ChatShell`**

Delete `NewChatPage`, `ConversationPage` and `ChatThreadSkeleton` from `chat-shell.tsx`, and replace its import block with:

```tsx
"use client"

import { Button } from "@app/ui/button"
import { Card } from "@app/ui/card"
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@app/ui/sheet"
import { MessagesSquareIcon } from "lucide-react"
import { useState, type ReactNode } from "react"

import {
  ChatRuntimeProvider,
  useActiveConversationId,
} from "./chat-runtime-provider"
import { ConversationList } from "./conversation-list"
import { CHAT_COPY } from "./copy"
```

- [ ] **Step 4: Remove the `welcome` prop from `Thread`**

In `thread.tsx`:
- delete `import type { ReactNode } from "react"`;
- change `export function Thread({ welcome }: { welcome?: ReactNode }) {` to `export function Thread() {`;
- change `{welcome ?? <Welcome />}` to `<Welcome />`.

- [ ] **Step 5: Point the route files at their components**

`app/(dashboard)/chat/page.tsx`:

```tsx
import { Thread } from "@/components/chat/thread"

/** /chat — a new conversation; nothing is created until the first send. */
export default function ChatPage() {
  return <Thread />
}
```

`app/(dashboard)/chat/[conversationId]/page.tsx`: change the import to `import { ConversationPage } from "@/components/chat/conversation-page"`.

`app/(dashboard)/chat/loading.tsx`: change the import to `import { ChatThreadSkeleton } from "@/components/chat/chat-thread-skeleton"`.

- [ ] **Step 6: Move the page's tests with it**

```bash
git mv web-app/apps/web/src/components/chat/chat-shell.test.tsx web-app/apps/web/src/components/chat/conversation-page.test.tsx
```

In the moved file, change `import { ConversationPage } from "./chat-shell"` to `import { ConversationPage } from "./conversation-page"`.

- [ ] **Step 7: Run the chat tests, type-check and lint**

Run: `cd web-app && pnpm -s vitest run apps/web/src/components/chat`
Expected: all pass, the same count as before the move.

Run: `cd web-app && pnpm -s type-check && cd .. && make check-web`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add -A web-app/apps/web/src
git commit -m "refactor(chat): one component per file; /chat renders the thread itself"
```

---

### Task 5: `silentError` takes a predicate; the copied toast rule goes

**Files:**
- Create: `web-app/packages/api-client/src/query-meta.ts`
- Modify: `web-app/packages/api-client/src/query-provider.tsx`
- Modify: `web-app/packages/api-client/src/query-provider.test.tsx`
- Modify: `web-app/apps/web/src/components/chat/chat-runtime-provider.tsx` (`useChatHistory`, lines 73–83)
- Modify: `web-app/apps/web/src/components/chat/conversation-page.tsx`
- Modify: `docs/architecture/web-app.md` (§5 lines 143–147 and 164–166; §7 lines 183–186)
- Modify: `docs/TODO.md` (the `QueryProvider` bullet, ~line 97)

**Interfaces:**
- Produces:
  - In `query-meta.ts`: `type SilentError = boolean | ((error: unknown) => boolean)`, `interface AppMeta { silentError?: SilentError }` (registered as TanStack's `queryMeta` and `mutationMeta`), and `isSilenced(meta: AppMeta | undefined, error: unknown): boolean`.
  - `isConversationNotFound(error: unknown): boolean`, exported from `chat-runtime-provider.tsx`.

- [ ] **Step 1: Write the failing `QueryProvider` query tests**

In `query-provider.test.tsx`:
- change `import { useMutation } from "@tanstack/react-query"` to `import { useMutation, useQuery } from "@tanstack/react-query"`;
- add `import type { AppMeta } from "./query-meta"`;
- change `FailingMutation`'s prop type to `{ meta?: AppMeta }`.

Append:

```tsx
function FailingQuery({ status, meta }: { status: number; meta?: AppMeta }) {
  useQuery({
    queryKey: ["failing", status],
    queryFn: async () => {
      throw new ApiError(`HTTP ${status}`, status, null, null)
    },
    meta,
    retry: false,
  })
  return null
}

describe("QueryProvider — query errors", () => {
  beforeEach(() => toastForError.mockClear())

  it("toasts a query that has never resolved", async () => {
    render(
      <QueryProvider>
        <FailingQuery status={500} />
      </QueryProvider>,
    )
    await waitFor(() => expect(toastForError).toHaveBeenCalledOnce())
  })

  // The chat page shows a 404 as its not-found screen; every other error
  // must still toast.
  it("a silentError predicate silences only the errors it matches", async () => {
    const notFound = (e: unknown) => e instanceof ApiError && e.status === 404
    render(
      <QueryProvider>
        <FailingQuery status={404} meta={{ silentError: notFound }} />
        <FailingQuery status={500} meta={{ silentError: notFound }} />
      </QueryProvider>,
    )
    await waitFor(() => expect(toastForError).toHaveBeenCalledOnce())
    await new Promise((r) => setTimeout(r, 20))
    expect(toastForError).toHaveBeenCalledOnce()
    expect(toastForError.mock.calls[0][0]).toMatchObject({ status: 500 })
  })
})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd web-app && pnpm -s vitest run packages/api-client/src/query-provider.test.tsx`
Expected: the import of `./query-meta` fails to resolve.

- [ ] **Step 3: Create `query-meta.ts`**

```ts
/**
 * What a query or mutation may carry in `meta`, typed for every hook through
 * TanStack Query's Register.
 *
 * `silentError` keeps a failure out of QueryProvider's toast: `true` for every
 * error, or a predicate for the errors the caller shows another way (the chat
 * page renders a 404 as its not-found screen).
 */
export type SilentError = boolean | ((error: unknown) => boolean)

export interface AppMeta extends Record<string, unknown> {
  silentError?: SilentError
}

declare module "@tanstack/react-query" {
  interface Register {
    queryMeta: AppMeta
    mutationMeta: AppMeta
  }
}

/** Whether `meta` keeps this error out of the toast. */
export function isSilenced(meta: AppMeta | undefined, error: unknown): boolean {
  const silent = meta?.silentError
  return typeof silent === "function" ? silent(error) : silent === true
}
```

- [ ] **Step 4: Apply it in `QueryProvider`**

In `query-provider.tsx`, add `import { isSilenced } from "./query-meta"`.

Replace the query `onError` body with:

```tsx
          onError: (error, query) => {
            // onError fires for background refetches too. A polling query that
            // fails every 30s would otherwise toast every 30s, behind data the
            // user can already see. Only a query that has never resolved
            // toasts, unless its meta silences the error.
            if (isSilenced(query.meta, error)) return
            if (query.state.data !== undefined) return
            toastForError(error)
          },
```

Replace the mutation `onError` body with:

```tsx
          onError: (error, _variables, _context, mutation) => {
            if (isSilenced(mutation.meta, error)) return
            toastForError(error)
          },
```

- [ ] **Step 5: Run the provider tests**

Run: `cd web-app && pnpm -s vitest run packages/api-client`
Expected: all pass, including the two existing mutation tests.

- [ ] **Step 6: Silence only not-found on the chat history**

In `chat-runtime-provider.tsx`, replace the `useChatHistory` doc comment and function with:

```tsx
/**
 * A malformed id is answered 422 by the path's UUID validation: to the user it
 * is a conversation that doesn't exist, the same as a 404.
 */
export function isConversationNotFound(error: unknown): boolean {
  return (
    error instanceof ApiError && (error.status === 404 || error.status === 422)
  )
}

/**
 * A conversation's saved messages. Every observer of this query goes through
 * here, because a query's meta is whichever observer set its options last.
 * Not-found is silenced: ConversationPage renders it as a screen, which a
 * toast would only repeat. Every other error toasts by QueryProvider's rule.
 */
export function useChatHistory(conversationId: string | null) {
  return useListChatMessages(conversationId ?? "", {
    query: {
      enabled: conversationId !== null,
      meta: { silentError: isConversationNotFound },
    },
  })
}
```

- [ ] **Step 7: Drop the copied rule from `ConversationPage`**

Replace `conversation-page.tsx` with:

```tsx
"use client"

import { ChatThreadSkeleton } from "./chat-thread-skeleton"
import {
  isConversationNotFound,
  useActiveConversationId,
  useChatHistory,
} from "./chat-runtime-provider"
import { ConversationNotFound } from "./conversation-not-found"
import { Thread } from "./thread"

/** /chat/[conversationId] — one conversation, or not-found for an unknown, foreign or malformed id. */
export function ConversationPage() {
  const activeId = useActiveConversationId()
  const history = useChatHistory(activeId)

  if (isConversationNotFound(history.error)) return <ConversationNotFound />
  if (history.isPending) return <ChatThreadSkeleton />
  return <Thread />
}
```

- [ ] **Step 8: Run the page tests unchanged, then type-check**

Run: `cd web-app && pnpm -s vitest run apps/web/src/components/chat`
Expected: all pass with `conversation-page.test.tsx` unedited:
- 404: not-found, no toast;
- 422: not-found, no toast;
- 500: toasts the generic copy.

Run: `cd web-app && pnpm -s type-check`
Expected: clean. This also proves the `Register` augmentation reaches the generated hooks. `useChatHistory` passes a function as `meta.silentError`, and `query.meta` reaches `isSilenced` typed as `AppMeta`.

- [ ] **Step 9: Bring the docs in line**

In `docs/architecture/web-app.md`, replace the bullet that starts with "**`QueryProvider` owns the error policy.**" (lines 143–147) with:

```markdown
- **`QueryProvider` owns the error policy.** A query toasts only if it has never
  resolved, so a failing background refetch behind visible data stays quiet. A
  mutation toasts: the user just acted. `meta.silentError` opts either out — `true`
  for every error, or a predicate for the errors the caller shows another way;
  `query-meta.ts` types it for every hook through TanStack's `Register`. The toast
  maps `status` to copy in `@app/core`'s `constants/messages.ts`; server text never
  reaches the UI. A 4xx is not retried.
```

Replace the chat-screen bullet that starts with "**Errors.** Both observers of the history query" (lines 164–166) with:

```markdown
- **Errors.** The history query's `meta.silentError` is `isConversationNotFound`: the
  conversation page renders a 404 (or the 422 of a malformed id) as "This conversation
  doesn't exist", and every other error toasts by `QueryProvider`'s rule.
```

In §7, replace:

```markdown
yet: nothing drives a browser. `QueryProvider`'s error policy is untested too — the
mutator and the status-recovery hook are covered, the provider is not
([`../TODO.md`](../TODO.md), **Web — tests the suite does not have yet**). `make test-web`
```

with:

```markdown
yet: nothing drives a browser. `QueryProvider`'s retry rule is untested too
([`../TODO.md`](../TODO.md), **Web — tests the suite does not have yet**). `make test-web`
```

In `docs/TODO.md`, replace the bullet that starts with "**`QueryProvider`'s error policy.**" with:

```markdown
- **`QueryProvider`'s retry rule.** That a 4xx is not retried and a 5xx is retried once.
  Which errors toast is covered (`query-provider.test.tsx`); the retry predicate is not.
```

- [ ] **Step 10: Commit**

```bash
git add web-app/packages/api-client/src web-app/apps/web/src/components/chat docs/architecture/web-app.md docs/TODO.md
git commit -m "refactor(web): silentError takes a predicate; the chat page stops copying the toast rule"
```

---

### Task 6: One fetch transport for the generated hooks and the chat stream

**Files:**
- Modify: `web-app/packages/api-client/src/use-api-fetch.ts`
- Modify: `web-app/packages/api-client/src/index.ts`
- Modify: `web-app/packages/api-client/src/use-api-fetch.test.ts`
- Modify: `web-app/apps/web/src/lib/chat/stream-chat.ts`
- Modify: `web-app/apps/web/src/lib/chat/stream-chat.test.ts`
- Modify: `web-app/apps/web/src/components/chat/chat-runtime-provider.tsx` (auth import, `getToken`, the `streamChat` call, `onNew`'s deps)
- Modify: `web-app/apps/web/src/components/chat/chat-runtime-provider.test.tsx` (one assertion, lines 172–178)
- Modify: `docs/architecture/web-app.md` (lines 159–161), `docs/guides/api-client-codegen.md` §6.1

**Interfaces:**
- Produces, from `@app/api-client`:
  - `type ApiRequest = (url: string, init?: RequestInit) => Promise<Response>`
  - `useApiRequest(): ApiRequest`
  - `resolveBaseUrl` is no longer exported.
- Produces: `streamChat({ conversationId, message, request, signal })`, where `request: ApiRequest` replaces `token`.
- Consumes: nothing from Task 5.

- [ ] **Step 1: Write the failing `useApiRequest` tests**

In `use-api-fetch.test.ts`, change the import to `import { useApiFetch, useApiRequest } from "./use-api-fetch"` and append:

```ts
describe("useApiRequest", () => {
  function request() {
    return renderHook(() => useApiRequest()).result.current
  }

  it("returns the response unread, with the bearer token sent", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("data: x\n\n", { status: 200 })),
    )
    const response = await request()("/api/v1/stream", {
      method: "POST",
      body: "{}",
    })
    expect(response.bodyUsed).toBe(false)
    expect(await response.text()).toBe("data: x\n\n")
    expect(lastCall().url).toBe("http://localhost:8100/api/v1/stream")
    expect(lastCall().headers.get("Authorization")).toBe("Bearer tok-123")
    expect(lastCall().headers.get("Content-Type")).toBe("application/json")
  })

  // Review Focus 4: a refused stream's body reads as the hooks' does.
  it("throws ApiError with the JSON error body parsed", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse({ detail: "slow down" }, { status: 429 }),
        ),
    )
    const error = await rejection(request()("/api/v1/stream"))
    expect(error.status).toBe(429)
    expect(error.body).toEqual({ detail: "slow down" })
  })
})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd web-app && pnpm -s vitest run packages/api-client/src/use-api-fetch.test.ts`
Expected: FAIL, because `useApiRequest` is not exported.

- [ ] **Step 3: Split the transport out of `useApiFetch`**

In `use-api-fetch.ts`:
- Remove `export` from `resolveBaseUrl`.
- Replace everything from the `useApiFetch` doc comment to the end of the file with:

```ts
/** A request through the API's transport, with the session's token bound. */
export type ApiRequest = (url: string, init?: RequestInit) => Promise<Response>

/**
 * One request to the API: the base URL, the bearer token, a JSON content type
 * for a plain body, and an ApiError for any non-2xx. The response comes back
 * unread, so a streamed body can be consumed as it arrives.
 */
async function apiRequest(
  url: string,
  init: RequestInit | undefined,
  token: string | null,
): Promise<Response> {
  const fullUrl = /^https?:\/\//i.test(url) ? url : `${resolveBaseUrl()}${url}`
  const headers = new Headers(init?.headers)

  if (token && !headers.has("authorization")) {
    headers.set("Authorization", `Bearer ${token}`)
  }

  // Only set a JSON content type for plain bodies. Never for FormData — the
  // browser must set its own multipart boundary — nor for Blob or ArrayBuffer.
  const body = init?.body
  if (
    body != null &&
    !headers.has("content-type") &&
    !(body instanceof FormData) &&
    !(body instanceof Blob) &&
    !(body instanceof ArrayBuffer)
  ) {
    headers.set("Content-Type", "application/json")
  }

  const response = await fetch(fullUrl, { ...init, headers })
  if (!response.ok) {
    // Deliberately not response.statusText: the reason phrase is server-supplied
    // text, and server error text must never reach the UI. status, body and
    // requestId still carry everything needed to debug.
    throw new ApiError(
      `HTTP ${response.status}`,
      response.status,
      await parseErrorBody(response),
      response.headers.get("x-request-id"),
    )
  }
  return response
}

/**
 * The API's transport with the current session's token, read on every call.
 * For a caller that reads the body itself: the chat stream. Everything else
 * uses a generated hook, which goes through useApiFetch.
 */
export function useApiRequest(): ApiRequest {
  const { getToken } = useAppAuth()
  return useCallback(
    async (url, init) => apiRequest(url, init, await getToken()),
    [getToken],
  )
}

/**
 * The mutator every generated endpoint routes through.
 *
 * It is a hook, not a module-level singleton, and that is deliberate. A
 * module-scope client would be shared across concurrent requests in a Next.js
 * server process — one tenant's token serving another tenant's request — and
 * would freeze the first render's getToken closure. As a hook it reads the
 * current token on every call, needs no provider of its own, and makes the
 * provider ordering in the root layout irrelevant.
 *
 * orval recognises the `use` prefix and calls this inside each generated hook.
 */
export function useApiFetch() {
  const request = useApiRequest()

  return useCallback(
    async <T>(url: string, init?: RequestInit): Promise<T> => {
      const response = await request(url, init)

      if (response.status === 204) return undefined as T
      if (response.headers.get("content-length") === "0") return undefined as T

      const contentType = response.headers.get("content-type") ?? ""
      if (contentType.includes("application/json"))
        return (await response.json()) as T

      return (await response.text()) as unknown as T
    },
    [request],
  )
}
```

- [ ] **Step 4: Update the package surface**

Replace `packages/api-client/src/index.ts` with:

```ts
/**
 * The package's public runtime surface is deliberately tiny. Everything else is
 * reached through the subpath exports, so importing one tag does not pull in
 * the whole client.
 *
 * `useApiRequest` and `toastForError` are here for the one hand-written call
 * site: the chat stream, which orval does not generate (streaming routes are
 * excluded) but which must reach the API and report errors the same way.
 */
export { ApiError } from "./errors"
export { useApiFetch, useApiRequest, type ApiRequest } from "./use-api-fetch"
export { toastForError } from "./toast-for-error"
```

- [ ] **Step 5: Run the transport tests**

Run: `cd web-app && pnpm -s vitest run packages/api-client`
Expected: all pass. The existing `useApiFetch` tests (base URL, headers, 204, `ApiError`) are unchanged.

- [ ] **Step 6: Rewrite `streamChat` over `ApiRequest`**

In `stream-chat.ts`:
- Change the first import to `import type { ApiRequest } from "@app/api-client"`.
- Replace `StreamChatOptions` and `streamChat`'s doc comment and function head, down to and including the `if (!response.body)` line, with:

```ts
export type StreamChatOptions = {
  conversationId: string
  message: string
  /** useApiRequest's: it adds the session's token, and throws ApiError for a refused stream before anything is read. */
  request: ApiRequest
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
  request,
  signal,
}: StreamChatOptions): AsyncGenerator<string> {
  const response = await request(
    `/api/v1/chatbot/chat/${conversationId}/stream`,
    {
      method: "POST",
      headers: { Accept: "text/event-stream" },
      body: JSON.stringify({ message }),
      signal,
    },
  )
  if (!response.body) throw new StreamFailedError("The response has no body")
```

The rest of the function, `readEvents` and `parseEvent` stay as they are.

- [ ] **Step 7: Move the stream tests to a fake `request`**

In `stream-chat.test.ts`:
- Change `import { ApiError } from "@app/api-client"` to `import { ApiError, type ApiRequest } from "@app/api-client"`.
- Replace the helpers `mockFetch` and `run` with:

```ts
function respondWith(response: Response) {
  return vi.fn<ApiRequest>(async () => response)
}

function run(request: ApiRequest, signal = new AbortController().signal) {
  return collect(
    streamChat({ conversationId: "c1", message: "hi", request, signal }),
  )
}
```

Replace the whole `describe("streamChat", ...)` block with:

```ts
describe("streamChat", () => {
  it("posts the message to the conversation's stream and yields the chunks", async () => {
    const request = respondWith(
      new Response(bodyOf(frame("Hel") + frame("lo") + frame("", true))),
    )
    await expect(run(request)).resolves.toEqual(["Hel", "lo"])
    expect(request).toHaveBeenCalledWith(
      "/api/v1/chatbot/chat/c1/stream",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ message: "hi" }),
      }),
    )
  })

  it("lets a refused stream's ApiError through", async () => {
    const request = vi.fn<ApiRequest>(async () => {
      throw new ApiError("HTTP 429", 429, null, null)
    })
    await expect(run(request)).rejects.toMatchObject({ status: 429 })
  })

  it("treats a final event carrying content as a failure", async () => {
    const request = respondWith(
      new Response(
        bodyOf(frame("partial") + frame("An error occurred.", true)),
      ),
    )
    await expect(run(request)).rejects.toBeInstanceOf(StreamFailedError)
  })

  // Review Focus 2: a dropped connection must not leave the UI "running".
  it("treats a stream that ends without done as a failure", async () => {
    const request = respondWith(new Response(bodyOf(frame("partial"))))
    await expect(run(request)).rejects.toBeInstanceOf(StreamFailedError)
  })

  it("treats a malformed event as a failure", async () => {
    const request = respondWith(new Response(bodyOf('data: {"nope": 1}\n\n')))
    await expect(run(request)).rejects.toBeInstanceOf(StreamFailedError)
  })

  it("stops reading when aborted", async () => {
    const controller = new AbortController()
    const request = vi.fn<ApiRequest>(
      (_url, init) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () =>
            reject(new DOMException("aborted", "AbortError")),
          )
        }),
    )
    const pending = run(request, controller.signal)
    controller.abort()
    await expect(pending).rejects.toMatchObject({ name: "AbortError" })
  })
})
```

- [ ] **Step 8: Use `useApiRequest` in the provider**

In `chat-runtime-provider.tsx`:
- Change `import { ApiError, toastForError } from "@app/api-client"` to `import { ApiError, toastForError, useApiRequest } from "@app/api-client"`.
- Delete `import { useAppAuth } from "@app/auth"`.
- Replace `const { getToken } = useAppAuth()` with `const request = useApiRequest()`.
- In `onNew`'s `try`, delete `const token = await getToken()` and change the `streamChat({...})` argument's `token,` to `request,`.
- In `onNew`'s dependency array, replace `getToken` with `request`.

In `chat-runtime-provider.test.tsx`, in "creates a conversation on the first send…", change `token: "tok",` to `request: expect.any(Function),`. This is the only edit to that file in this plan.

- [ ] **Step 9: Run the web suite, type-check and checks**

Run: `cd web-app && pnpm -s vitest run`
Expected: all pass.

Run: `cd web-app && pnpm -s type-check && cd .. && make check-web`
Expected: clean. A leftover `resolveBaseUrl` import anywhere fails the type-check.

- [ ] **Step 10: Bring the docs in line**

In `docs/architecture/web-app.md`, replace the chat-screen bullet that starts with "**The stream is the one hand-written `fetch`**" (lines 159–161) with:

```markdown
- **The stream is the one hand-written call** (`apps/web/src/lib/chat/stream-chat.ts`),
  because orval excludes `streaming` routes. It goes through `useApiRequest`, the
  transport under `useApiFetch`, so its URL, token and `ApiError` are the generated
  hooks' own; it reads the body itself.
```

In `docs/guides/api-client-codegen.md` §6.1 (*The mutator — `src/use-api-fetch.ts`*), replace the TypeScript code block that copies the file with the new `use-api-fetch.ts` contents verbatim. Keep the surrounding prose; if any sentence there says `resolveBaseUrl` is exported, change it to say the file exports `useApiFetch`, `useApiRequest` and `ApiRequest`.

- [ ] **Step 11: Commit**

```bash
git add web-app/packages/api-client/src web-app/apps/web/src docs/architecture/web-app.md docs/guides/api-client-codegen.md
git commit -m "refactor(web): the chat stream goes through the generated hooks' transport"
```

---

### Task 7: Restructure `ChatRuntimeProvider` over a pure reducer and cache helpers

**Files:**
- Create: `web-app/apps/web/src/lib/chat/exchange.ts`
- Create: `web-app/apps/web/src/lib/chat/exchange.test.ts`
- Create: `web-app/apps/web/src/lib/chat/chat-cache.ts`
- Modify (rewrite): `web-app/apps/web/src/components/chat/chat-runtime-provider.tsx`
- Modify: `web-app/apps/web/src/components/chat/conversation-list.tsx`
- Modify: `docs/architecture/web-app.md` (the chat screen's first bullet)

**Interfaces:**
- Consumes: from Task 5, `isConversationNotFound` and `useChatHistory`, kept in the rewrite. From Task 6, `useApiRequest` and `streamChat({ conversationId, message, request, signal })`.
- Produces:
  - `exchange.ts`: `Send`, `Exchange`, `ExchangeAction`, `exchangeReducer(state: Exchange | null, action: ExchangeAction): Exchange | null`, `showsExchange(exchange: Exchange, activeId: string | null): boolean`, and `toThreadMessages(saved: Message[], exchange: Exchange | null, activeId: string | null, historyId: string | null): ThreadMessageLike[]`.
  - `chat-cache.ts`: `NO_MESSAGES`, plus these functions, each taking `client: QueryClient` first:
    - `replaceConversation`, `prependConversation` (pass the row)
    - `removeConversation` (pass `conversationId`)
    - `cachedHistory`
    - `seedEmptyHistory`, `refetchHistory`, `markHistoryStale`, `historyNeedsRefetch`

**Rule for this task:** `chat-runtime-provider.test.tsx` is not edited. It passes before and after, unchanged.

- [ ] **Step 1: Write the failing reducer and message tests**

Create `apps/web/src/lib/chat/exchange.test.ts`:

```ts
import type { Message } from "@app/api-client/types"
import { describe, expect, it } from "vitest"

import {
  exchangeReducer,
  toThreadMessages,
  type Exchange,
  type ExchangeAction,
  type Send,
} from "./exchange"

const sendIn = (conversationId: string | null): Send => ({
  controller: new AbortController(),
  conversationId,
})

/** One reducer step that the test knows leaves an exchange open. */
const step = (state: Exchange | null, action: ExchangeAction) =>
  exchangeReducer(state, action) as Exchange

function started(send: Send, baseCount = 0): Exchange {
  return exchangeReducer(null, {
    type: "start",
    send,
    userText: "hi",
    baseCount,
  }) as Exchange
}

describe("exchangeReducer", () => {
  it("start opens a running exchange, replacing any earlier one", () => {
    const first = started(sendIn("c1"))
    const second = sendIn("c1")
    const state = exchangeReducer(first, {
      type: "start",
      send: second,
      userText: "again",
      baseCount: 2,
    })
    expect(state).toEqual({
      send: second,
      baseCount: 2,
      userText: "again",
      replyText: "",
      status: "running",
    })
  })

  it("an action from a send that is no longer the exchange's changes nothing", () => {
    const old = sendIn("c1")
    const state = started(sendIn("c1"))
    expect(exchangeReducer(state, { type: "chunk", send: old, text: "x" })).toBe(
      state,
    )
    expect(exchangeReducer(state, { type: "cleared", send: old })).toBe(state)
  })

  it("chunks append; stopped, failed and cleared end the exchange", () => {
    const send = sendIn("c1")
    let state = started(send)
    state = step(state, { type: "chunk", send, text: "Hel" })
    state = step(state, { type: "chunk", send, text: "lo" })
    expect(state.replyText).toBe("Hello")
    expect(exchangeReducer(state, { type: "stopped", send })?.status).toBe(
      "stopped",
    )
    expect(exchangeReducer(state, { type: "failed", send })?.status).toBe(
      "error",
    )
    expect(exchangeReducer(state, { type: "cleared", send })).toBeNull()
  })

  it("created swaps in the send that names the conversation", () => {
    const send = sendIn(null)
    const next = { ...send, conversationId: "c1" }
    const state = step(started(send), { type: "created", send, next })
    expect(state.send).toBe(next)
    // The pre-create send no longer owns the exchange.
    expect(exchangeReducer(state, { type: "chunk", send, text: "x" })).toBe(
      state,
    )
  })

  it("leaving drops another conversation's exchange, /chat included, and keeps its own", () => {
    const state = started(sendIn("c1"))
    expect(exchangeReducer(state, { type: "left", activeId: "c1" })).toBe(state)
    expect(exchangeReducer(state, { type: "left", activeId: "c2" })).toBeNull()
    expect(exchangeReducer(state, { type: "left", activeId: null })).toBeNull()
  })
})

describe("toThreadMessages", () => {
  const saved: Message[] = [
    { role: "user", content: "older" },
    { role: "assistant", content: "reply" },
    { role: "user", content: "hi" }, // the in-flight message, saved mid-stream
  ]

  it("slices the history at baseCount so a mid-stream refetch shows the user's message once", () => {
    const send = sendIn("c1")
    const exchange = { ...started(send, 2), replyText: "Hel" }
    const messages = toThreadMessages(saved, exchange, "c1", "c1")
    expect(messages.map((m) => m.content)).toEqual([
      "older",
      "reply",
      "hi",
      "Hel",
    ])
    expect(messages.at(-1)?.status).toEqual({ type: "running" })
  })

  it("marks a stopped reply cancelled and a failed one an error", () => {
    const exchange = started(sendIn("c1"), 3)
    const last = (status: Exchange["status"]) =>
      toThreadMessages(saved, { ...exchange, status }, "c1", "c1").at(-1)
        ?.status
    expect(last("stopped")).toEqual({ type: "incomplete", reason: "cancelled" })
    expect(last("error")).toEqual({ type: "incomplete", reason: "error" })
  })

  it("shows a created conversation's exchange on /chat until the URL catches up", () => {
    const exchange = started(sendIn("c1"))
    expect(toThreadMessages([], exchange, null, "c1")).toHaveLength(2)
  })

  it("hides another conversation's exchange and shows the history whole", () => {
    const exchange = started(sendIn("c1"), 1)
    expect(toThreadMessages(saved, exchange, "c2", "c2")).toHaveLength(3)
  })
})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd web-app && pnpm -s vitest run apps/web/src/lib/chat/exchange.test.ts`
Expected: FAIL, because `./exchange` cannot be resolved.

- [ ] **Step 3: Create `exchange.ts`**

```ts
import type { ThreadMessageLike } from "@assistant-ui/react"
import type { Message } from "@app/api-client/types"

/**
 * One send. Stop aborts its controller; `conversationId` is the conversation
 * it belongs to, null while a send from /chat creates it. Immutable: once the
 * conversation exists, the send is replaced by a copy naming it (the
 * `created` action), and identity is what says which send is current.
 */
export type Send = {
  readonly controller: AbortController
  readonly conversationId: string | null
}

/**
 * The exchange being sent, kept beside the saved history until the server has
 * it. It opens before the first await of a send, so the user's message shows
 * and the composer is in its running state (a second send is refused) while
 * the conversation is created or the history refetched.
 *
 * `baseCount` is how many history messages preceded it: the history query can
 * refetch mid-stream (it gains the user's message as soon as the graph
 * starts), and slicing at baseCount is what keeps that message from showing
 * twice.
 */
export type Exchange = {
  send: Send
  baseCount: number
  userText: string
  replyText: string
  status: "running" | "stopped" | "error"
}

export type ExchangeAction =
  | { type: "start"; send: Send; userText: string; baseCount: number }
  | { type: "created"; send: Send; next: Send }
  | { type: "rebased"; send: Send; baseCount: number }
  | { type: "chunk"; send: Send; text: string }
  | { type: "stopped"; send: Send }
  | { type: "failed"; send: Send }
  | { type: "cleared"; send: Send }
  | { type: "left"; activeId: string | null }

export function exchangeReducer(
  state: Exchange | null,
  action: ExchangeAction,
): Exchange | null {
  if (action.type === "start") {
    return {
      send: action.send,
      baseCount: action.baseCount,
      userText: action.userText,
      replyText: "",
      status: "running",
    }
  }
  // Leaving drops the exchange of any other conversation, /chat included. Not
  // the rendering rule (showsExchange): /chat shows a first send's exchange
  // while its URL catches up, but going to /chat from a conversation leaves it.
  if (action.type === "left") {
    return state && state.send.conversationId !== action.activeId
      ? null
      : state
  }
  // Every other action comes from a send, and one that is no longer the
  // exchange's (replaced by a newer send, or dropped by leaving) changes nothing.
  if (state === null || state.send !== action.send) return state
  switch (action.type) {
    case "created":
      return { ...state, send: action.next }
    case "rebased":
      return { ...state, baseCount: action.baseCount }
    case "chunk":
      return { ...state, replyText: state.replyText + action.text }
    case "stopped":
      return { ...state, status: "stopped" }
    case "failed":
      return { ...state, status: "error" }
    case "cleared":
      return null
  }
}

/**
 * Whether the exchange shows on this screen: on its own conversation, and on
 * /chat, where a first send's reply can end before the URL names the
 * conversation it created.
 */
export function showsExchange(
  exchange: Exchange,
  activeId: string | null,
): boolean {
  return exchange.send.conversationId === activeId || activeId === null
}

/** The thread: the saved history, then the exchange in flight if it shows here. */
export function toThreadMessages(
  saved: Message[],
  exchange: Exchange | null,
  activeId: string | null,
  historyId: string | null,
): ThreadMessageLike[] {
  const visible =
    exchange && showsExchange(exchange, activeId) ? exchange : null
  const base = visible ? saved.slice(0, visible.baseCount) : saved
  const converted: ThreadMessageLike[] = base.map((m, i) => ({
    id: `${historyId}-${i}`,
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
          : {
              type: "incomplete",
              reason: visible.status === "stopped" ? "cancelled" : "error",
            },
    },
  ]
}
```

- [ ] **Step 4: Run the exchange tests**

Run: `cd web-app && pnpm -s vitest run apps/web/src/lib/chat/exchange.test.ts`
Expected: all pass.

- [ ] **Step 5: Create `chat-cache.ts`**

```ts
import { getListChatMessagesQueryKey } from "@app/api-client/endpoints/chatbot"
import { getListConversationsQueryKey } from "@app/api-client/endpoints/conversation"
import type {
  ConversationHistory,
  ConversationResponse,
  Message,
} from "@app/api-client/types"
import type { QueryClient } from "@tanstack/react-query"

/** One empty list, so a memo over "no messages" keeps its identity. */
export const NO_MESSAGES: Message[] = []

/** Write a conversation's new row (a rename, a generated title) into the loaded list. */
export function replaceConversation(
  client: QueryClient,
  updated: ConversationResponse,
): void {
  client.setQueryData<ConversationResponse[]>(
    getListConversationsQueryKey(),
    (rows) =>
      rows?.map((r) =>
        r.conversation_id === updated.conversation_id ? updated : r,
      ),
  )
}

/**
 * Put a new conversation at the top of the list, then refetch it. Only into a
 * list already loaded: its cache can be empty here (its first fetch failed or
 * is still in flight), and seeding it would show a one-row list until it went
 * stale. The refetch also covers a list whose first fetch was in flight.
 */
export function prependConversation(
  client: QueryClient,
  created: ConversationResponse,
): void {
  const key = getListConversationsQueryKey()
  client.setQueryData<ConversationResponse[]>(
    key,
    (rows) => rows && [created, ...rows],
  )
  void client.invalidateQueries({ queryKey: key })
}

export function removeConversation(
  client: QueryClient,
  conversationId: string,
): void {
  client.setQueryData<ConversationResponse[]>(
    getListConversationsQueryKey(),
    (rows) => rows?.filter((r) => r.conversation_id !== conversationId),
  )
}

/** The conversation's saved messages in the cache; none for /chat or an unloaded history. */
export function cachedHistory(
  client: QueryClient,
  conversationId: string | null,
): Message[] {
  if (conversationId === null) return NO_MESSAGES
  return (
    client.getQueryData<ConversationHistory>(
      getListChatMessagesQueryKey(conversationId),
    )?.messages ?? NO_MESSAGES
  )
}

/**
 * A new conversation's history is known to be empty. Seeding it means
 * /chat/[id] renders the thread at once instead of a loading skeleton that
 * would hide the reply as it starts streaming.
 */
export function seedEmptyHistory(
  client: QueryClient,
  conversationId: string,
): void {
  client.setQueryData<ConversationHistory>(
    getListChatMessagesQueryKey(conversationId),
    { messages: [] },
  )
}

export function refetchHistory(
  client: QueryClient,
  conversationId: string,
): Promise<void> {
  return client.refetchQueries({
    queryKey: getListChatMessagesQueryKey(conversationId),
  })
}

/**
 * Mark a history stale after a Stop or a failure, without refetching: the
 * server may still be saving the stopped turn. The next send (see
 * historyNeedsRefetch) or the conversation's next mount fetches it.
 */
export function markHistoryStale(
  client: QueryClient,
  conversationId: string,
): void {
  void client.invalidateQueries({
    queryKey: getListChatMessagesQueryKey(conversationId),
    refetchType: "none",
  })
}

/** Whether a Stop or failure has left this history stale since it was last fetched. */
export function historyNeedsRefetch(
  client: QueryClient,
  conversationId: string,
): boolean {
  return (
    client.getQueryState(getListChatMessagesQueryKey(conversationId))
      ?.isInvalidated ?? false
  )
}
```

- [ ] **Step 6: Rewrite `chat-runtime-provider.tsx`**

Replace the whole file with the version below. It keeps `useActiveConversationId`, and `isConversationNotFound` / `useChatHistory` from Task 5, as they are.

```tsx
"use client"

import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from "@assistant-ui/react"
import { ApiError, toastForError, useApiRequest } from "@app/api-client"
import { useListChatMessages } from "@app/api-client/endpoints/chatbot"
import {
  getListConversationsQueryKey,
  useCreateConversation,
  useGenerateConversationTitle,
} from "@app/api-client/endpoints/conversation"
import type { ConversationResponse } from "@app/api-client/types"
import { useQueryClient } from "@tanstack/react-query"
import { useParams, useRouter } from "next/navigation"
import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react"

import {
  cachedHistory,
  historyNeedsRefetch,
  markHistoryStale,
  NO_MESSAGES,
  prependConversation,
  refetchHistory,
  replaceConversation,
  seedEmptyHistory,
} from "@/lib/chat/chat-cache"
import {
  exchangeReducer,
  toThreadMessages,
  type Send,
} from "@/lib/chat/exchange"
import { streamChat } from "@/lib/chat/stream-chat"

export function useActiveConversationId(): string | null {
  const params = useParams<{ conversationId?: string }>()
  return params.conversationId ?? null
}

/**
 * A malformed id is answered 422 by the path's UUID validation: to the user it
 * is a conversation that doesn't exist, the same as a 404.
 */
export function isConversationNotFound(error: unknown): boolean {
  return (
    error instanceof ApiError && (error.status === 404 || error.status === 422)
  )
}

/**
 * A conversation's saved messages. Every observer of this query goes through
 * here, because a query's meta is whichever observer set its options last.
 * Not-found is silenced: ConversationPage renders it as a screen, which a
 * toast would only repeat. Every other error toasts by QueryProvider's rule.
 */
export function useChatHistory(conversationId: string | null) {
  return useListChatMessages(conversationId ?? "", {
    query: {
      enabled: conversationId !== null,
      meta: { silentError: isConversationNotFound },
    },
  })
}

/**
 * Whether `send` is still the one in flight. Leaving (or unmounting) drops it
 * from the ref; Stop aborts it but leaves it there. So ownership, not the
 * abort, is what says the user is still on this send's screen.
 */
function owns(ref: RefObject<Send | null>, send: Send): boolean {
  return ref.current === send
}

/** End a send's hold on the ref, unless the user already left it. */
function release(ref: RefObject<Send | null>, send: Send): void {
  if (ref.current === send) ref.current = null
}

export function ChatRuntimeProvider({ children }: { children: ReactNode }) {
  const activeId = useActiveConversationId()
  const router = useRouter()
  const queryClient = useQueryClient()
  const request = useApiRequest()
  const createConversation = useCreateConversation()
  // The cache update is in the hook's options, not the mutate call: a call's
  // own callbacks run only for the latest call, so a title for one
  // conversation would be lost if another's was asked for before it landed.
  // Silent: the title is asked for in the background, and the server
  // already treats a failed one as cosmetic.
  const generateTitle = useGenerateConversationTitle({
    mutation: {
      meta: { silentError: true },
      onSuccess: (updated) => replaceConversation(queryClient, updated),
    },
  })
  // A conversation created by a send from /chat, until the URL names it. The
  // reply can end before router.replace commits (a route compiling in dev):
  // the thread then shows this conversation's history, not an empty /chat,
  // and the history refetch at the end of the send has an observer to run.
  const [createdId, setCreatedId] = useState<string | null>(null)
  const historyId = activeId ?? createdId
  const history = useChatHistory(historyId)

  const [exchange, dispatch] = useReducer(exchangeReducer, null)
  const sendRef = useRef<Send | null>(null)
  const restoreTextRef = useRef<(text: string) => void>(() => {})

  // Leaving a conversation abandons its send, and with WS7 the server stops
  // the model call. A first send on /chat names its new conversation before
  // moving the URL there: that move is not leaving.
  useEffect(() => {
    const send = sendRef.current
    if (send !== null && send.conversationId !== activeId) {
      send.controller.abort()
      sendRef.current = null
    }
    dispatch({ type: "left", activeId })
    setCreatedId(null)
  }, [activeId])

  useEffect(
    () => () => {
      sendRef.current?.controller.abort()
      sendRef.current = null
    },
    [],
  )

  const requestTitle = useCallback(
    (conversationId: string) => {
      const rows = queryClient.getQueryData<ConversationResponse[]>(
        getListConversationsQueryKey(),
      )
      const row = rows?.find((r) => r.conversation_id === conversationId)
      // `name` is optional in the contract: absent and "" both mean untitled.
      // No list in the cache (its fetch failed or is still in flight) asks
      // too: the server answers a named conversation unchanged.
      if (row?.name) return
      generateTitle.mutate({ conversationId })
    },
    [generateTitle, queryClient],
  )

  // A send from /chat creates its conversation first. Resolves to the send
  // naming its conversation, or null when the send ended here: the create
  // failed (the mutation cache has toasted) or the user left while it ran.
  const ensureConversation = useCallback(
    async (
      send: Send,
      text: string,
    ): Promise<{ send: Send; conversationId: string } | null> => {
      if (send.conversationId !== null) {
        return { send, conversationId: send.conversationId }
      }
      let created: ConversationResponse
      try {
        created = await createConversation.mutateAsync()
      } catch {
        const stillHere = owns(sendRef, send)
        dispatch({ type: "cleared", send })
        release(sendRef, send)
        if (stillHere) restoreTextRef.current(text)
        return null
      }
      prependConversation(queryClient, created)
      // Left for another conversation while this one was being created (a
      // Stop first included): it exists, but the user is elsewhere now.
      if (!owns(sendRef, send)) return null
      const conversationId = created.conversation_id
      const next: Send = { ...send, conversationId }
      seedEmptyHistory(queryClient, conversationId)
      // Named before the URL moves, so the move is not taken for leaving.
      sendRef.current = next
      dispatch({ type: "created", send, next })
      setCreatedId(conversationId)
      router.replace(`/chat/${conversationId}`)
      return { send: next, conversationId }
    },
    [createConversation, queryClient, router],
  )

  // A Stop or failure leaves the history stale: the saved history may have
  // moved on (it holds the stopped turn's user message), so count from fresh
  // data. Until then the slice at the cached length keeps the thread steady.
  // A completed send already ended with a refetch.
  const rebaseIfStale = useCallback(
    async (send: Send, conversationId: string) => {
      if (!historyNeedsRefetch(queryClient, conversationId)) return
      await refetchHistory(queryClient, conversationId)
      dispatch({
        type: "rebased",
        send,
        baseCount: cachedHistory(queryClient, conversationId).length,
      })
    },
    [queryClient],
  )

  // How a send that threw ends: a Stop (or leaving) aborted it; a refused
  // stream start is an ApiError with nothing streamed; anything else failed
  // mid-reply.
  const settle = useCallback(
    (send: Send, conversationId: string, text: string, error: unknown) => {
      if (send.controller.signal.aborted) {
        dispatch({ type: "stopped", send })
        markHistoryStale(queryClient, conversationId)
      } else if (error instanceof ApiError) {
        // Refused before anything streamed: nothing to show but the toast,
        // and the user's text goes back in the composer.
        toastForError(error)
        dispatch({ type: "cleared", send })
        restoreTextRef.current(text)
      } else {
        dispatch({ type: "failed", send })
        markHistoryStale(queryClient, conversationId)
      }
    },
    [queryClient],
  )

  const onNew = useCallback(
    async (message: AppendMessage) => {
      const part = message.content[0]
      if (part?.type !== "text") return
      const text = part.text

      // Open the exchange before anything is awaited: from here the thread
      // shows the message, isRunning is true and Stop reaches this send.
      const opened: Send = {
        controller: new AbortController(),
        conversationId: activeId,
      }
      sendRef.current = opened
      dispatch({
        type: "start",
        send: opened,
        userText: text,
        baseCount: cachedHistory(queryClient, activeId).length,
      })

      const ready = await ensureConversation(opened, text)
      if (ready === null) return
      const { send, conversationId } = ready
      await rebaseIfStale(send, conversationId)

      // Stopped before the stream started: nothing was sent, nothing to stream.
      if (send.controller.signal.aborted) {
        dispatch({ type: "stopped", send })
        release(sendRef, send)
        return
      }

      try {
        for await (const chunk of streamChat({
          conversationId,
          message: text,
          request,
          signal: send.controller.signal,
        })) {
          dispatch({ type: "chunk", send, text: chunk })
        }
        await refetchHistory(queryClient, conversationId)
        dispatch({ type: "cleared", send })
        requestTitle(conversationId)
      } catch (error) {
        settle(send, conversationId, text, error)
      } finally {
        release(sendRef, send)
      }
    },
    [
      activeId,
      ensureConversation,
      queryClient,
      rebaseIfStale,
      request,
      requestTitle,
      settle,
    ],
  )

  const onCancel = useCallback(async () => {
    sendRef.current?.controller.abort()
  }, [])

  const savedMessages = history.data?.messages ?? NO_MESSAGES
  const messages = useMemo(
    () => toThreadMessages(savedMessages, exchange, activeId, historyId),
    [activeId, exchange, historyId, savedMessages],
  )

  const runtime = useExternalStoreRuntime<ThreadMessageLike>({
    messages,
    isRunning: exchange?.status === "running",
    convertMessage: (m) => m,
    onNew,
    onCancel,
  })

  // Set in an effect, not during render: React 19's lint rules forbid writing refs while rendering.
  useEffect(() => {
    restoreTextRef.current = (text: string) =>
      runtime.thread.composer.setText(text)
  }, [runtime])

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  )
}
```

- [ ] **Step 7: Use the cache helpers in `conversation-list.tsx`**

- Delete the `getListConversationsQueryKey` import and `import type { ConversationResponse } from "@app/api-client/types"`.
- Add `import { removeConversation, replaceConversation } from "@/lib/chat/chat-cache"`.
- Delete `const listKey = getListConversationsQueryKey()`.
- Change rename's `onSuccess` to `onSuccess: (updated) => replaceConversation(queryClient, updated),`.
- Change delete's `onSuccess` body's `setQueryData` call to `removeConversation(queryClient, conversationId)`.

- [ ] **Step 8: Run the provider tests unchanged**

Run: `git diff --quiet -- web-app/apps/web/src/components/chat/chat-runtime-provider.test.tsx && echo unchanged`
Expected: `unchanged`. Task 6's one-line edit is already committed.

Run: `cd web-app && pnpm -s vitest run apps/web/src/components/chat apps/web/src/lib/chat`
Expected: all pass. In particular these must pass with no test edits:
- "opens the exchange before the conversation exists, so a second send is refused"
- "Stop, then leaving while the conversation is created, does not pull the user back"
- "a first send whose reply ends before the URL moves keeps showing the exchange"
- "a send after a Stop refetches the history before it streams"
- "keeps the user's message once when history refetches mid-stream"

If one fails, the rewrite changed behaviour. Fix the rewrite, not the test.

- [ ] **Step 9: Type-check, lint, and check the size**

Run: `cd web-app && pnpm -s type-check && cd .. && make check-web`
Expected: clean, with no `react-hooks` warnings.

Run: `wc -l web-app/apps/web/src/components/chat/chat-runtime-provider.tsx web-app/apps/web/src/lib/chat/exchange.ts web-app/apps/web/src/lib/chat/chat-cache.ts`
Expected: the provider at about 330 lines or fewer under Prettier's wrapping, down from 370. `onNew` is about 60 lines.

- [ ] **Step 10: Update the architecture note**

In `docs/architecture/web-app.md`, replace the chat-screen bullet that starts with "**assistant-ui's `ExternalStoreRuntime`.**" with:

```markdown
- **assistant-ui's `ExternalStoreRuntime`.** TanStack Query (the generated hooks) holds
  conversations and history; the runtime only renders them plus the in-flight exchange. It
  opens that exchange before its first await, so a send cannot be doubled while the
  conversation is created. The exchange is a pure reducer over one immutable `Send` per
  send (`lib/chat/exchange.ts`); the provider's cache edits are `lib/chat/chat-cache.ts`.
```

- [ ] **Step 11: Commit**

```bash
git add web-app/apps/web/src docs/architecture/web-app.md
git commit -m "refactor(chat): the runtime is a pure exchange reducer over one Send per send"
```

---

### Task 8: Whole-branch verification and the PR's migration note

**Files:** none changed, unless a check fails.

- [ ] **Step 1: Run every gate**

Run, from the repo root:

```bash
make check
make test-web
make -C server test-unit
make -C server test-integration
make check-contract
cd web-app && pnpm -s type-check
```

Expected: every command exits 0, and `make check-contract` reports no drift.

- [ ] **Step 2: Draft the PR #11 migration note and show it to the user**

Do not edit the PR without the user's go-ahead; it is outward-facing. Draft this addition to the PR description:

```markdown
### Migrating an existing env file

The server now refuses to start on an unprefixed model id. In every `server/.env.*`
(local, staging, production):

- `OPENAI_API_KEY` → `OPENROUTER_API_KEY` (an OpenRouter key)
- `DEFAULT_LLM_MODEL`, `LONG_TERM_MEMORY_MODEL`, `LONG_TERM_MEMORY_EMBEDDER_MODEL`,
  `EVALUATION_LLM`: prefix the provider — `openai/gpt-5-mini`, not `gpt-5-mini`
- `EVALUATION_BASE_URL=https://openrouter.ai/api/v1` (or remove it to take the default)
```

On approval: `gh pr edit 11 --body-file <file>`. Write the file in the scratchpad, starting from `gh pr view 11 --json body -q .body`.
