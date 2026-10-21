# 7b Agent core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the chat agent on LangChain 1.3's `create_agent` and middleware, the chat's tools as `StructuredTool`s under `conversation/tools/`, the one-call agents on `with_structured_output`, and the LLM integration as a model factory with fallbacks, with no visible change in the chat.

**Architecture:** `app/agents/core/` is what every agent shares (checkpointing, memory, observability, structured calls, message helpers); `app/agents/chatbot/` is `build_chatbot()` (`create_agent` + six middleware classes) and a thin `ChatbotAgent` over the compiled graph; the chat's wire types and the pure translations from graph messages to history and stream events belong to `conversation`. The old hand-rolled loop, `BaseAgent`, `Toolkit`, `LLMService` and the model registry are deleted. Old and new code coexist until one cutover task switches the wiring.

**Tech Stack:** FastAPI, langchain 1.3.18, langchain-core 1.2.7, langgraph 1.0.5, langchain-openai 1.6.0, openai 3.7.0, mem0, pytest (unit: `-m unit`; integration: `-m integration`, testcontainers Postgres), import-linter.

**Spec:** `.superpowers/specs/2026-10-21-agent-core-design.md` (the plan argues from it; §17 is the verified library appendix).

## Global Constraints

- Behaviour frozen (spec §12): the SSE frames, the history JSON, each tool's `content` and `display`, the preamble wording, the error texts, the metric names and labels, the Langfuse tool span names and the graph name `f"{PROJECT_NAME} Agent ({settings.ENVIRONMENT.value})"` are identical. `make check-contract` shows no client diff. The web app is not touched.
- Layering: `app.agents` imports no `app.modules` package (R2). R1, R6, R9, R10 unchanged; `conversation`'s R10 row forbids `app.modules.conversation.tools` after the cutover. `lint-imports` and `tests/unit/test_module_contracts.py` pass at every commit.
- No new dependency. Pins may move within their majors only if a middleware needs it; `tenacity` leaves `pyproject.toml` once nothing imports it.
- Settings keep their names and meanings: `CHAT_MAX_STEPS` (8), `CHAT_REPLY_MAX_TOKENS` (8000), `CHAT_HISTORY_MAX_TOKENS` (24000), `CHAT_REASONING_EFFORT` (`medium`), `MAX_TOKENS` (2000), `MAX_LLM_CALL_RETRIES` (3), `DEFAULT_LLM_MODEL` (`openai/gpt-5-mini`). New: `LLM_FALLBACK_MODELS` default `["openai/gpt-5", "openai/gpt-5-nano"]`, `CHAT_SUMMARY_MODEL` default `openai/gpt-5-nano`. Removed: `DEFAULT_LLM_TEMPERATURE`.
- The model lineup is the gpt-5 family; a model reasons when its bare name (after the `/`) starts with `gpt-5`; default efforts `gpt-5-mini` `low`, `gpt-5` `medium`, `gpt-5-nano` `minimal`; any other name gets no reasoning parameters.
- Fixed texts, verbatim from today's `app/agents/chatbot/graph.py`: `TOOL_FAILED_MESSAGE = "The tool failed to run. Tell the user this information could not be retrieved right now."`, `TOOL_UNKNOWN_MESSAGE = "That tool does not exist. Answer without it."`, `WRAP_UP_INSTRUCTION = "Tools are no longer available this turn. Answer from the results above and say that the answer may be incomplete."`, `STOPPED_FALLBACK_TEXT = "I could not finish looking into this, so I have no complete answer. Try asking again, or narrow the question."`, `STUB_TEMPLATE = "{title}{period}: result omitted from an earlier turn; call the tool again for figures."`, the validation wording `"Invalid arguments: {problems}"` with problems joined by `"; "` as `"{loc or 'arguments'}: {msg}"`, `NO_MEMORY = "No relevant memory found."`, `TOOL_ARGS_LOG_LIMIT = 200`, recursion limit `2 * CHAT_MAX_STEPS + 3`.
- Every LLM caller takes a `model=None` keyword as its test seam; a test never patches a module-level client.
- Every commit passes `make check-server` (from the repo root) and the unit suite; the integration suite passes at the cutover (Task 13) and after.
- Test commands run from `server/`: `APP_ENV=test uv run pytest <path> -v`. Integration tests need Docker running.

## Spike findings

Filled in by Tasks 1 and 2; the later tasks that depend on them say so.

| Spike | Finding |
|---|---|
| 1. Reasoning through OpenRouter on standard blocks | **(a) NO: item boundaries do not survive in `content_blocks`.** A streamed chunk's `content_blocks` holds `{"type": "reasoning", "index": "lc_rs_305f30", "reasoning": " user"}` (plus `id` on the first chunk): a flat `reasoning` string delta, no `summary` list, no per-item index; `index` is a synthetic constant string for the whole message, so nothing in it marks where one summary item ends. `events()` cannot key a paragraph break on `content_blocks`. **(b) YES: the raw `content` still carries today's shape.** A streamed chunk's `content` is a `list` holding `{"summary": [{"index": 0, "type": "summary_text", "text": " user"}], "index": 0, "type": "reasoning"}` (the first chunk is `{"id": "rs_…", "summary": [], "type": "reasoning", "status": "in_progress", "index": 0}`); both `index` and `summary[].index` are present, so `_summary_items` and `_reasoning_text` keep working on `content`. Surprise: through OpenRouter `summary[].index` was 0 on every chunk across two runs (one short, one 838-chunk reasoning-heavy turn) and the persisted block holds ONE `summary` item whose text has the provider's items run together with no separator (`…relate.**Computing values and sums**\n\nI need…`), so real item boundaries never reach `content` either; today's `\n\n` separator logic is dead for this route and any paragraph break has to come from the `**Title**` markers in the text. The persisted `AIMessage.content_blocks` is likewise one `reasoning` block with the merged text and `encrypted_content`; `additional_kwargs` is empty (no responses-API blocks, no reasoning outside `content`). **(c) YES: the history round-trips.** Turn 2 on the same thread (reasoning block with `encrypted_content`, `status: in_progress`, in the checkpointed history) was accepted with no 400 and answered correctly, in both runs. **Task 13 Step 9 branches on (a) = no:** keep parsing `content` with `_summary_items`; do not use `content_blocks`. |
| 2. Structured output through OpenRouter | _(Task 2 records: which `with_structured_output` method works for gpt-5-mini and gpt-5-nano on the three shapes; whether `max_length` on the root passes)_ |

Already found while writing this plan (verified against the lock on 21 Oct 2026, scripts not kept):

- A `StructuredTool.from_function(coroutine=…, args_schema=Model)` whose coroutine declares `runtime: ToolRuntime[…]` fails at execution with the library's `"Error invoking tool …"` text when `Model` has no `runtime` field: the node injects `runtime` into the arguments and the explicit schema rejects it. It works when the schema declares the slot as `runtime: Annotated[SkipValidation[Optional[ToolRuntime]], InjectedToolArg] = Field(None, exclude=True)` with `arbitrary_types_allowed=True`: the slot is left out of the schema the model sees, `Model.model_validate({"months": 1})` still works (so the middleware can pre-validate), `extra="forbid"` and the `model_validator`s still apply, and the coroutine may be `async def run(runtime: ToolRuntime[Ctx], **kwargs)`. Task 12 uses this.
- The schema the model sees is `tool.tool_call_schema` (what `bind_tools` sends), which carries each field's `description`, `default`, `minimum`/`maximum` and `anyOf` as today, but not `additionalProperties: false` and not the per-property `title` that `args_schema.model_json_schema()` emitted. This is the one model-facing change of the step; unknown argument names are still rejected at validation. `test_schemas.py` guards `tool_call_schema` from Task 12 on.
- `GenericFakeChatModel` and `FakeMessagesListChatModel` do not implement `bind_tools` (raises `NotImplementedError`), and `GenericFakeChatModel` yields no generation for a message with empty content. The integration seam is an own `ScriptedChatModel` (Task 13).
- `wrap_model_call` may return `ExtendedModelResponse(model_response=…, command=Command(update={…}))` to write state from inside the hook; a hook may call `handler` twice and only the returned response is persisted. `ToolCallRequest.runtime.stream_writer` writes the custom stream from `wrap_tool_call`. `create_agent`'s nodes are `model` and `tools`. All three confirmed end to end with a scripted model.

## Review Focus

Inputs the spec implies that no task's tests exercised in the first draft; each now has its test in the task named.

1. **A checkpoint written before this step** (no `summary`/`summary_through`, a stale `turn_steps`): the next turn must run and the request-shaping middleware must treat the cutoff as unset. Pinned in Task 13 (`test_a_thread_checkpointed_before_this_step_still_answers`).
2. **A wrap-up call that answers with tool calls or empty text** (the model ignores `tools=[]`): the turn ends with `STOPPED_FALLBACK_TEXT`, never with a dangling call. Pinned in Task 10.
3. **A finished tool whose artifact no longer validates** on the live stream: `tool_finished` carries `display: null` and logs, as the history does; the stream does not crash. Pinned in Task 13 (`test_an_artifact_that_does_not_validate_streams_a_null_display`).
4. **`LLM_FALLBACK_MODELS` naming the primary, or empty**: the primary is never tried twice, and an empty list means no wrapper (and, in `build_chatbot`, no fallback middleware). Pinned in Task 4.
5. **One response with a valid call and an invalid-arguments call**: both run, results come back in call order, the stream carries started and finished for each, and the metrics count one `success` and one `invalid_args`. Pinned in Task 11.

---

## File structure

Created (★) or kept and changed (✎); everything in `app/agents/base/`, `app/agents/shared/`, `app/agents/factory.py`, `app/agents/graph.py`, `app/agents/messages.py`, `app/agents/chatbot/toolkit.py`, `app/agents/chatbot/events.py`, `app/agents/chatbot/legacy.py` (the parked old loop), `app/integrations/llm/service.py` and `app/modules/conversation/finance/` is deleted by Task 13 or 14.

```
server/app/agents/
  __init__.py ✎                       docstring only
  core/ ★
    __init__.py                       re-exports
    checkpointing.py                  shared/checkpointing/postgres.py moved
    memory.py                         shared/memory/factory.py moved
    observability.py                  shared/observability/langfuse.py moved
    messages.py                       drop_unanswered_tool_calls
    structured.py                     ask(), InvalidModelAnswer
  chatbot/
    __init__.py ✎                     build_chatbot, ChatbotAgent, TurnContext
    agent.py ★                        ChatbotAgent
    graph.py ✎                        build_chatbot, turn_recursion_limit (old content parked as legacy.py in Task 13, deleted in Task 13)
    context.py ✎                      TurnContext (trimming code deleted in Task 13)
    state.py ✎                        ChatState
    title.py ✎                        generate_title on the factory; first_exchange leaves
    prompts/__init__.py ✎  system.md  summary.md ★
    middleware/ ★  __init__.py memory.py request_shaping.py summary.py turn_bound.py tool_events.py model_timing.py
  csv_mapping/mapper.py ✎  insights/writer.py ✎  transaction_labeler/labeler.py ✎   (call core.structured.ask)
server/app/integrations/llm/
  __init__.py ✎  models.py ★  exceptions.py
server/app/modules/conversation/
  tools/ ★  __init__.py base.py analytics.py search.py display.py periods.py
  schemas.py ✎  domain/chat.py ★  router/chatbot.py ✎  service.py ✎  dependencies.py ✎  __init__.py ✎
server/app/main.py ✎   server/app/core/config.py ✎   server/pyproject.toml ✎   server/.env.example ✎  server/.env.test ✎
server/tests/fakes/ ★  __init__.py  chat_model.py
```

`tools/base.py` is one file more than the spec's §3 lists: it holds the argument-model base with the injected runtime slot (spike finding above), the per-turn history load and the `StructuredTool` builder, which `analytics.py` and `search.py` both need.

---

### Task 1: Spike — reasoning through OpenRouter on the standard content blocks

Throwaway. Needs `OPENROUTER_API_KEY` in `server/.env.development`; run with `APP_ENV=development`. Nothing is committed but the findings row of this plan.

**Files:**
- Create (scratch, not committed): `/private/tmp/…/scratchpad/spike_reasoning.py`
- Modify: `.superpowers/plans/2026-10-21-agent-core.md` (the Spike findings table)

- [ ] **Step 1: Write the script**

A `ChatOpenAI(model="openai/gpt-5-mini", api_key=settings.llm.OPENROUTER_API_KEY.get_secret_value(), base_url=settings.llm.LLM_BASE_URL, reasoning={"effort": "medium", "summary": "auto"}, max_tokens=2000, tiktoken_model_name="gpt-5-mini")`; a `create_agent(model, [one trivial StructuredTool], checkpointer=MemorySaver())`; one turn streamed with `stream_mode=["messages"]` that forces a tool call ("call the tool, then answer"). Print, for each `AIMessageChunk` from node `model`: `type(chunk.content)`, `chunk.content` when it holds a `reasoning` block, `chunk.content_blocks`, and whether a reasoning block carries `index`/`summary[].index`. After the turn print the persisted `AIMessage.content` and `.content_blocks` from `aget_state`. Then run a second turn on the same thread and confirm the provider accepts the first turn's reasoning blocks back (no 400).

- [ ] **Step 2: Run it**

Run: `cd server && APP_ENV=development .venv/bin/python <script>`
Expected: output showing the three answers; a 400 on the second turn is itself a finding.

- [ ] **Step 3: Record the finding in the Spike findings table**

One row: (a) do reasoning summaries appear in `content_blocks` as `{"type": "reasoning", …}` with a boundary between summary items that `events()` can key on; (b) does the raw `content` still carry `{"type": "reasoning", "index", "summary": [{"index", "text"}]}` as today's parsing expects; (c) does the history round-trip. Task 13 Step 9 branches on (a).

- [ ] **Step 4: Commit the plan**

```bash
git add .superpowers/plans/2026-10-21-agent-core.md
git commit -m "Plan: spike 1 finding (reasoning blocks through OpenRouter)"
```

---

### Task 2: Spike — structured output through OpenRouter

Throwaway, same setup as Task 1.

**Files:**
- Create (scratch, not committed): `/private/tmp/…/scratchpad/spike_structured.py`
- Modify: the Spike findings table

- [ ] **Step 1: Write the script**

For each model in (`openai/gpt-5-mini`, `openai/gpt-5-nano`) and each method in (`json_schema`, `function_calling`, `json_mode`), call `model.with_structured_output(shape, method=method).ainvoke([SystemMessage(system), HumanMessage(user)])` for the three shapes used in `app/agents/`: `RootModel[dict[str, str]]` (csv mapping), `RootModel[list[_Answer]]` with `_Answer(id: int, category: str, confidence: float)` (labeller), and the insights `_Insights` root (`RootModel[list[_Insight]]` with `Field(max_length=10)` and nested optionals, copied from `app/agents/insights/writer.py`). Print the method, the shape, whether the result validated, and the exception type and message otherwise. A `RootModel` may need `include_raw=True` or a wrapping object schema on some methods; note what was needed.

- [ ] **Step 2: Run it**

Run: `cd server && APP_ENV=development .venv/bin/python <script>`
Expected: an 18-row table of outcomes.

- [ ] **Step 3: Record the finding**

The row states the `method` Task 5 pins as `STRUCTURED_OUTPUT_METHOD`, whether root-model shapes need wrapping, and whether `max_length` on the root passes the provider. If no method is reliable for a shape, the row says so and Task 5 keeps the fence-tolerant JSON parse behind `ask`.

- [ ] **Step 4: Commit the plan**

```bash
git add .superpowers/plans/2026-10-21-agent-core.md
git commit -m "Plan: spike 2 finding (structured output through OpenRouter)"
```

---

### Task 3: `agents/core/` — the shared layer, moved

Mechanical: `shared/` becomes `core/` with flat files, and `drop_unanswered_tool_calls` gets its lasting home. No behaviour change.

**Files:**
- Create: `server/app/agents/core/__init__.py`, `core/checkpointing.py` (from `shared/checkpointing/postgres.py`), `core/memory.py` (from `shared/memory/factory.py`), `core/observability.py` (from `shared/observability/langfuse.py`), `core/messages.py` (`drop_unanswered_tool_calls` from `agents/graph.py`)
- Delete: `server/app/agents/shared/` (all of it except `shared/structured.py`, which Task 5 deletes)
- Modify: `server/app/agents/graph.py` (drop the moved function, import it from core where `context.py` needs it), `app/agents/chatbot/context.py:16`, `app/agents/chatbot/title.py:12`, `app/agents/base/agent.py:45-49`, `app/agents/csv_mapping/mapper.py:11`, `app/agents/insights/writer.py:17`, `app/agents/transaction_labeler/labeler.py:18`, `app/modules/account/service.py:8`, `app/modules/conversation/handlers.py:7`, `app/modules/conversation/router/chatbot.py:14`, `app/main.py:76`, `app/agents/__init__.py`
- Move tests: `tests/unit/agents/checkpointing/test_postgres.py` → `tests/unit/agents/core/test_checkpointing.py`; `tests/unit/agents/memory/test_memory_factory.py` → `tests/unit/agents/core/test_memory.py`; `tests/unit/agents/test_graph_config.py` → `tests/unit/agents/core/test_observability.py`; `tests/unit/agents/test_drop_unanswered_tool_calls.py` → `tests/unit/agents/core/test_messages.py` (patch targets inside them follow the new module paths)

**Interfaces:**
- Produces: `app.agents.core` exporting `create_postgres_saver`, `create_connection_pool`, `close_connection_pool`, `delete_conversation_checkpoints`, `delete_conversations_checkpoints`, `create_memory`, `get_relevant_memory`, `update_memory`, `delete_user_memory`, `MEMORY_INSTRUCTIONS`, `create_graph_config`, `create_trace_config`, `drop_unanswered_tool_calls`. Signatures unchanged from the moved files.

- [ ] **Step 1: `git mv` the four files and rewrite every import listed above; write `core/__init__.py` with the re-exports; `agents/__init__.py` keeps exporting `ChatbotAgent` for now**
- [ ] **Step 2: Move the four test files and fix their imports and `patch("…")` targets**
- [ ] **Step 3: Run the unit suite and the import contracts**

Run: `cd server && APP_ENV=test uv run pytest tests/unit -q -m unit && uv run lint-imports`
Expected: all pass; `lint-imports` reports every contract kept.

- [ ] **Step 4: Commit**

```bash
git add -A server/app/agents server/app/modules server/app/main.py server/tests/unit/agents
git commit -m "agents: shared/ becomes core/; drop_unanswered_tool_calls moves to core/messages"
```

---

### Task 4: `integrations/llm/models.py` — the factory, the fallback list, the error translation

`service.py` stays alive for the old chatbot until Task 14; `DEFAULT_LLM_TEMPERATURE` stays in settings until then too (the registry's class body reads it).

**Files:**
- Create: `server/app/integrations/llm/models.py`
- Modify: `server/app/integrations/llm/__init__.py` (export the new names beside the old), `server/app/core/config.py:114-132` (add `LLM_FALLBACK_MODELS: list[OpenRouterModel] = Field(default_factory=lambda: ["openai/gpt-5", "openai/gpt-5-nano"])` and `CHAT_SUMMARY_MODEL: OpenRouterModel = "openai/gpt-5-nano"`), `server/.env.example:14-26` and `server/.env.test` (add `LLM_FALLBACK_MODELS='["openai/gpt-5","openai/gpt-5-nano"]'` and `CHAT_SUMMARY_MODEL=openai/gpt-5-nano`)
- Test: `server/tests/unit/integrations/llm/test_models.py`

**Interfaces:**
- Produces, in `app.integrations.llm`:
  - `PLACEHOLDER_KEY = "openrouter-key-not-set"`
  - `REASONING_EFFORT_DEFAULTS: dict[str, str] = {"gpt-5-mini": "low", "gpt-5": "medium", "gpt-5-nano": "minimal"}`
  - `is_reasoning_model(name: str) -> bool` — bare name starts with `gpt-5`
  - `chat_model(name: str | None = None, *, max_tokens: int | None = None, reasoning_effort: str | None = None) -> BaseChatModel` — `name` defaults to `settings.llm.DEFAULT_LLM_MODEL`, `max_tokens` to `settings.llm.MAX_TOKENS`; builds `ChatOpenAI(model=name, tiktoken_model_name=bare, api_key=key or PLACEHOLDER_KEY, base_url=settings.llm.LLM_BASE_URL, max_tokens=…, max_retries=settings.llm.MAX_LLM_CALL_RETRIES, reasoning={"effort": effort, "summary": "auto"} if is_reasoning_model(name) else nothing)` where `effort` is the argument or the table's default (a reasoning name outside the table gets `None` effort: no `reasoning` parameter); cached in a module-level `_clients: dict[tuple[str, int, str | None], BaseChatModel]` keyed by the resolved `(name, max_tokens, reasoning_effort)`.
  - `fallback_models(*, primary: str | None = None, max_tokens=None, reasoning_effort=None) -> list[BaseChatModel]` — `settings.llm.LLM_FALLBACK_MODELS` in order, skipping a name equal to `primary` (default `settings.llm.DEFAULT_LLM_MODEL`), each through `chat_model` with the same tuning.
  - `with_fallbacks(model: BaseChatModel, *, max_tokens=None, reasoning_effort=None) -> Runnable` — `model.with_fallbacks(fallback_models(primary=model.model_name, …))`, or `model` itself when the list is empty.
  - `translate_error(error: BaseException) -> LLMServiceError` — `RateLimitError` → `LLMRateLimitError`, `APITimeoutError` → `LLMTimeoutError`, anything else → `LLMAPIError`; message `f"model call failed with {type(error).__name__}"`, `last_error_type=type(error).__name__` in its details (the exceptions' constructor as `service.py:301-307` uses it, without `models_tried`/`starting_model`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/integrations/llm/test_models.py   (pytestmark = pytest.mark.unit)
def test_a_gpt5_name_reasons_at_its_table_effort_and_asks_for_summaries():
    m = chat_model("openai/gpt-5-mini")
    assert m.reasoning == {"effort": "low", "summary": "auto"} and m.model_name == "openai/gpt-5-mini"
    assert m.tiktoken_model_name == "gpt-5-mini" and m.max_retries == settings.llm.MAX_LLM_CALL_RETRIES

def test_the_chat_passes_its_own_effort_and_budget():
    m = chat_model(max_tokens=8000, reasoning_effort="high")
    assert m.reasoning["effort"] == "high" and m.max_tokens == 8000

def test_a_non_reasoning_name_gets_no_reasoning_parameters():
    m = chat_model("openai/gpt-4o-mini")
    assert m.reasoning is None and m.model_name == "openai/gpt-4o-mini"

def test_same_arguments_share_one_client_and_different_tuning_does_not():
    assert chat_model() is chat_model() and chat_model(max_tokens=10) is not chat_model()

def test_without_a_key_the_client_still_builds(monkeypatch):
    monkeypatch.setattr(settings.llm, "OPENROUTER_API_KEY", SecretStr(""))
    monkeypatch.setattr(models, "_clients", {})          # the factory's cache, a module-level dict
    assert chat_model().openai_api_key.get_secret_value() == PLACEHOLDER_KEY

def test_fallbacks_follow_the_setting_and_skip_the_primary(monkeypatch):
    monkeypatch.setattr(settings.llm, "LLM_FALLBACK_MODELS", ["openai/gpt-5-mini", "openai/gpt-5", "openai/gpt-5-nano"])
    assert [m.model_name for m in fallback_models()] == ["openai/gpt-5", "openai/gpt-5-nano"]

def test_an_empty_fallback_list_returns_the_model_itself(monkeypatch):
    monkeypatch.setattr(settings.llm, "LLM_FALLBACK_MODELS", [])
    m = chat_model()
    assert with_fallbacks(m) is m

def test_with_fallbacks_wraps_in_order(monkeypatch):
    wrapped = with_fallbacks(chat_model())
    assert [f.model_name for f in wrapped.fallbacks] == ["openai/gpt-5", "openai/gpt-5-nano"]

@pytest.mark.parametrize("raw, typed", [(RateLimitError, LLMRateLimitError), (APITimeoutError, LLMTimeoutError), (APIError, LLMAPIError), (ValueError, LLMAPIError)])
def test_translate_error_follows_the_failure(raw, typed): ...
```
(Build the openai errors as `test_service.py` does today; the fixture there is the reference.)

- [ ] **Step 2: Run to verify they fail**

Run: `APP_ENV=test uv run pytest tests/unit/integrations/llm/test_models.py -v`
Expected: FAIL, `ImportError` on `app.integrations.llm.models`.

- [ ] **Step 3: Implement `models.py` and the settings; mem0's `_NO_KEY` in `core/memory.py` becomes an import of `PLACEHOLDER_KEY`**
- [ ] **Step 4: Run the tests and the existing import-without-credentials test**

Run: `APP_ENV=test uv run pytest tests/unit/integrations/llm -v`
Expected: PASS (the old registry and service tests still pass: nothing of theirs changed).

- [ ] **Step 5: Commit**

```bash
git add server/app/integrations/llm server/app/core/config.py server/app/agents/core/memory.py server/.env.example server/.env.test server/tests/unit/integrations/llm/test_models.py
git commit -m "llm: chat_model factory, fallback list and error translation beside the old service"
```

---

### Task 5: `core/structured.py` — `ask()`; the one-call agents and the title on the factory

**Files:**
- Create: `server/app/agents/core/structured.py`
- Delete: `server/app/agents/shared/structured.py`, `server/app/agents/shared/` (now empty)
- Modify: `app/agents/csv_mapping/mapper.py:11-12,49-56`, `app/agents/insights/writer.py:17-18,141`, `app/agents/transaction_labeler/labeler.py:18-22,95-98,117-119,137`, `app/modules/insights/service.py:12` (import `InvalidModelAnswer` from `app.agents.core`), `app/agents/chatbot/title.py` (`generate_title` on the factory; `first_exchange` stays until Task 13), `app/agents/chatbot/graph.py:284-287` (the old `title_for` drops the `model_name` argument), `app/agents/core/__init__.py`
- Tests: rewrite `tests/unit/agents/test_structured.py`; update `tests/unit/agents/csv_mapping/test_mapper.py`, `tests/unit/agents/insights/test_writer.py`, `tests/unit/agents/transaction_labeler/test_labeler.py` (patch `ask` instead of `ask_json`; the `structured_llm_service` patches become a fake passed as `model=` or a patched `ask`), `tests/unit/agents/chatbot/test_title.py` (a fake `model=`)

**Interfaces:**
- Produces: `app.agents.core.structured.ask(shape: type[T], system: str, user: str, config: RunnableConfig, *, model: BaseChatModel | None = None) -> T`; `InvalidModelAnswer(ValueError)`; `STRUCTURED_OUTPUT_METHOD` (the literal Task 2 found). `ask` builds `runnable = structured(primary).with_fallbacks([structured(m) for m in fallback_models()])` where `structured(m) = m.with_structured_output(shape, method=STRUCTURED_OUTPUT_METHOD)` (`model` given: that model alone, no fallbacks), invokes it with `[SystemMessage(system), HumanMessage(user)]` and `config`, retries **once** on a parse/validation failure (the library raises `OutputParserException`/`ValidationError`/`StructuredOutputValidationError`; treat all as invalid), then raises `InvalidModelAnswer(type(e).__name__)`; any `OpenAIError` (after the fallbacks) is raised as `translate_error(e)`. If Task 2 found no reliable method for a shape, `ask` instead invokes the plain model and parses with today's `parse_answer` (fence regex `^```(?:json)?\s*|\s*```$`); the signature is the same either way.
- `generate_title(user_text: str, reply_text: str, conversation_id: uuid.UUID, user_id: uuid.UUID, *, model=None) -> str | None` — `model` defaults to `with_fallbacks(chat_model())`; prompt, truncation (`TITLE_INPUT_LIMIT = 1000`), `clean_title` and the `create_graph_config` tracing unchanged.
- Consumes: Task 4's factory.

- [ ] **Step 1: Write the failing tests for `ask`**

```python
# tests/unit/agents/test_structured.py — a fake BaseChatModel whose with_structured_output returns a RunnableLambda over a queue of answers/exceptions
async def test_returns_the_shape_on_a_valid_answer()
async def test_asks_once_more_after_an_invalid_answer()           # queue: [ValidationError-raising, valid] → valid, two calls
async def test_gives_up_after_two_invalid_answers()               # raises InvalidModelAnswer, two calls
async def test_a_model_error_propagates_translated_without_a_second_ask()   # RateLimitError → LLMRateLimitError, one call
async def test_the_config_reaches_the_model()
```

- [ ] **Step 2: Run to verify they fail** — `APP_ENV=test uv run pytest tests/unit/agents/test_structured.py -v` → FAIL on import.
- [ ] **Step 3: Implement `core/structured.py`; port the three callers (`ask(_Mapping, _PROMPT, json.dumps(payload), config)` etc.; the labeller's `_label_batch` loses its `service` parameter); port `title.py`; delete `shared/`**
- [ ] **Step 4: Update the four callers' tests** so they patch `app.agents.<pkg>.<module>.ask` (same stubs as today, one fewer positional argument) and the title tests pass a fake `model=`. `write_insights` keeps its signature: the insights tests that today patch `structured_llm_service` with a fake service instead patch `ask`, and the `_dropped` and "every insight invalid" cases drive `_Insights.model_validate` directly, as they already do.
- [ ] **Step 5: Run the agents' unit tests and the import contracts**

Run: `APP_ENV=test uv run pytest tests/unit/agents tests/unit/modules/insights -v && uv run lint-imports`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A server/app/agents server/app/modules/insights/service.py server/tests/unit/agents
git commit -m "agents: core.structured.ask over with_structured_output; one-call agents and the title on the model factory"
```

---

### Task 6: `TurnContext` in `agents/chatbot/context.py` with a typed history slot

Closes the "untyped `TurnContext.cache`" TODO bullet. The old toolkit re-exports the name so nothing else moves yet.

**Files:**
- Modify: `server/app/agents/chatbot/context.py` (add the dataclass at the top; the trimming code below it stays until Task 13), `server/app/agents/chatbot/toolkit.py:18-29` (delete the class, `from app.agents.chatbot.context import TurnContext` and keep it in `__all__`), `server/app/modules/conversation/finance/service.py:50,61-71` (`turn_history` uses the slot)
- Tests: `tests/unit/agents/chatbot/test_toolkit.py:38` (`test_turn_context_cache_is_per_instance` becomes `test_turn_context_history_slot_starts_empty`), `tests/unit/modules/conversation/finance/test_service.py:117` (`test_concurrent_calls_share_one_history_load` reads `ctx.history`)

**Interfaces:**
- Produces: `@dataclass class TurnContext: user_id: uuid.UUID; session_factory: async_sessionmaker; history: Any = None` — docstring: the per-turn load of the user's analytics history, a `Future` the chat's tools set and share; `Any` because `agents` does not know the type.

- [ ] **Step 1: Change the two tests; run them to see them fail** (`AttributeError: history`)
- [ ] **Step 2: Implement; `turn_history` becomes: `if ctx.history is None: ctx.history = asyncio.ensure_future(_load_history(ctx)); return await ctx.history`**
- [ ] **Step 3: Run** `APP_ENV=test uv run pytest tests/unit/agents/chatbot tests/unit/modules/conversation -v` → PASS.
- [ ] **Step 4: Commit** — `git commit -am "chatbot: TurnContext lives in context.py with a typed history slot"`

---

### Task 7: Memory middleware

**Files:**
- Create: `server/app/agents/chatbot/middleware/__init__.py` (empty docstring), `server/app/agents/chatbot/middleware/memory.py`, `server/app/agents/chatbot/state.py` gains `ChatState` (beside `GraphState`, which Task 13 deletes)
- Test: `server/tests/unit/agents/chatbot/middleware/__init__.py`, `test_memory.py`

**Interfaces:**
- Produces: `class ChatState(AgentState): long_term_memory: NotRequired[str]; stopped: NotRequired[dict[str, str]]; summary: NotRequired[str]; summary_through: NotRequired[str | None]` (a `TypedDict`; readers use `state.get(key, default)`).
- Produces: `NO_MEMORY = "No relevant memory found."`; `class MemoryMiddleware(AgentMiddleware[ChatState, TurnContext])` with `state_schema = ChatState`; `abefore_agent(state, runtime) -> dict` returns `{"long_term_memory": await get_relevant_memory(runtime.context.user_id, last_user_text) or NO_MEMORY}`; `aafter_agent(state, runtime) -> None` schedules `update_memory(runtime.context.user_id, [{"role": "user", "content": last_user_text}], get_config().get("metadata", {}))` with `asyncio.create_task`, keeping the task in a module-level set until done so it is not collected. `last_user_text` is the text of the last `HumanMessage` in `state["messages"]`. Both hooks import from `app.agents.core`.

- [ ] **Step 1: Write the failing tests** (drive the hooks directly with a `Runtime`-shaped stub carrying `context=TurnContext(...)`; patch `app.agents.chatbot.middleware.memory.get_relevant_memory/update_memory`)

```python
async def test_before_agent_puts_the_relevant_memory_in_state()
async def test_before_agent_uses_the_fixed_text_when_memory_is_empty()      # == NO_MEMORY
async def test_after_agent_sends_memory_only_this_turns_user_message()      # update_memory called with [{"role": "user", "content": "…"}] and the user id, not the reply or tool results
async def test_a_memory_failure_is_logged_and_the_turn_proceeds()           # get_relevant_memory returns "" (its own try/except); before_agent still returns NO_MEMORY
```

- [ ] **Step 2: Run** → FAIL on import. **Step 3: Implement.** **Step 4: Run** `APP_ENV=test uv run pytest tests/unit/agents/chatbot/middleware/test_memory.py -v` → PASS.
- [ ] **Step 5: Commit** — `git add server/app/agents/chatbot/middleware server/app/agents/chatbot/state.py server/tests/unit/agents/chatbot/middleware && git commit -m "chatbot: memory middleware and ChatState"`

---

### Task 8: Request-shaping middleware

Replaces `build_model_context`, `render_turn_context` and the drop-oldest trim. The request is shaped from `request.messages`, never from state, so a wrap-up instruction a surrounding hook appended survives at the end.

**Files:**
- Create: `server/app/agents/chatbot/middleware/request_shaping.py`
- Test: `server/tests/unit/agents/chatbot/middleware/test_request_shaping.py` (the cases of `tests/unit/agents/chatbot/test_context.py` classes `TestCurrentTurn`, `TestEarlierTurns`, `TestLayout`; the `TestPrompts` cases move to `tests/unit/agents/chatbot/test_prompts.py` in this task; `TestEstimate` is dropped with the estimator)

**Interfaces:**
- Produces, module level: `STUB_TEMPLATE` (verbatim), `SUMMARY_PREFIX = "Earlier in this conversation: "`; `split_turns(messages: list[BaseMessage]) -> tuple[list[list[BaseMessage]], list[BaseMessage]]` (today's `_split_turns`); `shape_turn(turn: list[BaseMessage]) -> list[BaseMessage]` (tool results stubbed by title/period from the artifact, falling back to the call's tool name, then the message name, then `"Tool"`; AI messages without their reasoning blocks; tool calls kept); `turns_after(turns, summary_through: str | None) -> list[list[BaseMessage]]` (the turns that follow the message whose id is `summary_through`; all of them when it is `None` or not found); `render_turn_context(*, today: dt.date, memory: str, preamble: str) -> str` (verbatim wording from today's `context.py:162-170`); `count_tokens = count_tokens_approximately` (from `langchain_core.messages.utils`).
- Produces: `class RequestShapingMiddleware(AgentMiddleware[ChatState, TurnContext])` with `__init__(self, preamble: Callable[[TurnContext], Awaitable[str]])` and `awrap_model_call(request, handler)`: `messages = drop_unanswered_tool_calls(request.messages)`; `earlier, current = split_turns(messages)`; `shaped = [shape_turn(t) for t in turns_after(earlier, request.state.get("summary_through"))]`; drop the oldest of `shaped` while `sum(count_tokens(t) for t in shaped) > settings.llm.CHAT_HISTORY_MAX_TOKENS`; `preamble` awaited inside try/except (empty string and `logger.exception("chat_preamble_failed", thread_id=…)` on failure); `turn_context = SystemMessage(render_turn_context(today=dt.date.today(), memory=request.state.get("long_term_memory", ""), preamble=preamble_text))`; `summary = [SystemMessage(SUMMARY_PREFIX + s)] if (s := request.state.get("summary")) else []`; `return await handler(request.override(messages=[*summary, *flatten(shaped), turn_context, *current]))`. The system prompt stays on `request.system_message`. The budget applies to the shaped earlier turns alone (**call**: today the head, the turn context and the current turn counted too; they were never trimmable, so this only shifts the trigger point by their size, and Task 9 measures the same quantity).
- Consumes: `drop_unanswered_tool_calls` (Task 3), `TurnContext` (Task 6), `ChatState` (Task 7).

- [ ] **Step 1: Write the failing tests** (a `request` built with `ModelRequest(model=MagicMock(), messages=…, system_message=SystemMessage("sys"), tool_choice=None, tools=[], response_format=None, state={...}, runtime=stub, model_settings={})`; `handler` records the request it gets and returns `ModelResponse(result=[AIMessage("ok")])`)

```python
async def test_current_turn_is_never_trimmed_even_over_budget(monkeypatch)        # CHAT_HISTORY_MAX_TOKENS=1
async def test_current_turn_keeps_its_reasoning_blocks_and_full_tool_results()
async def test_earlier_tool_results_become_stubs()                                 # "Spending overview · September 2026: result omitted …"
async def test_stub_without_a_period_has_none()                                    # "Spending overview: result omitted …"
async def test_error_result_without_artifact_is_stubbed_by_the_tool_name()
async def test_error_result_with_no_known_name_is_stubbed_as_tool()                # "Tool: result omitted …"
async def test_reasoning_blocks_are_stripped_from_earlier_turns()
async def test_an_earlier_tool_call_message_emptied_by_stripping_stays_with_its_pair()
async def test_oldest_turns_drop_first_and_tool_pairs_stay_whole(monkeypatch)
async def test_a_tool_call_without_a_result_is_not_sent()
async def test_turn_context_comes_after_the_history_and_before_the_current_turn()  # [*earlier, SystemMessage(turn ctx), HumanMessage(current)]
async def test_the_summary_comes_first_and_only_turns_after_the_cutoff_follow()    # state summary="…", summary_through=<id of turn 1's last message>
async def test_a_cutoff_id_that_is_not_in_the_history_means_no_cutoff()
async def test_a_failed_preamble_still_shapes_the_request_and_logs()
async def test_the_turn_context_carries_date_preamble_and_memory()                 # render_turn_context: three sections joined by "\n\n", memory "Nothing yet." when empty
```

- [ ] **Step 2: Run** → FAIL on import. **Step 3: Implement.** **Step 4: Run** `APP_ENV=test uv run pytest tests/unit/agents/chatbot -v` → PASS (old `test_context.py` still passes: nothing of the old code changed).
- [ ] **Step 5: Commit** — `git commit -m "chatbot: request-shaping middleware (stubs, reasoning strip, turn context, budget)"`

---

### Task 9: Summary middleware and `prompts/summary.md`

**Files:**
- Create: `server/app/agents/chatbot/middleware/summary.py`, `server/app/agents/chatbot/prompts/summary.md`
- Modify: `server/app/agents/chatbot/prompts/__init__.py` (add `load_summary_prompt()`)
- Test: `server/tests/unit/agents/chatbot/middleware/test_summary.py`, `tests/unit/agents/chatbot/test_prompts.py` (one case for the new prompt)

**Interfaces:**
- Produces: `render_for_summary(turns: list[list[BaseMessage]]) -> str` — each shaped message on its own line: `"User: …"`, `"Assistant: …"` (text only), `"Tool result: <stub text>"`; `class SummaryMiddleware(AgentMiddleware[ChatState, TurnContext])` with `__init__(self, *, model: Runnable | None = None)` (default `with_fallbacks(chat_model(settings.llm.CHAT_SUMMARY_MODEL))`, built lazily on first use so importing compiles no client) and `abefore_model(state, runtime) -> dict | None`: `earlier, _ = split_turns(drop_unanswered_tool_calls(state["messages"]))`; `pending = [shape_turn(t) for t in turns_after(earlier, state.get("summary_through"))]`; return `None` unless `sum(count_tokens(t) for t in pending) > settings.llm.CHAT_HISTORY_MAX_TOKENS`; otherwise call the model with `[SystemMessage(load_summary_prompt()), HumanMessage(f"Summary so far:\n{state.get('summary') or '(none)'}\n\nTurns to fold in:\n{render_for_summary(pending)}")]` and return `{"summary": response.text.strip(), "summary_through": pending[-1][-1].id}`; on any exception `logger.exception("chat_summary_failed", thread_id=…)` and return `None` (Task 8's drop-oldest is then the fallback). Folds every pending turn (**call**: whole turns, all of them, so the summary is always current).
- `prompts/summary.md` (exact copy to ship):

```
You keep a running summary of a conversation between a user and Finsight's personal-finance assistant. Fold the new turns into the summary so far and return the updated summary only, in plain prose, under 200 words.

Keep: what the user asked, what the assistant answered in substance, decisions and preferences, and anything the user said about themselves (goals, circumstances, plans).

Never include amounts, counts, percentages, rates, dates of transactions, or anything describing a period's spending or activity, even if the earlier text states them: figures must come from a fresh lookup, never from this summary. Never include a tool result.
```

- Consumes: `split_turns`, `shape_turn`, `turns_after`, `count_tokens` (Task 8); `chat_model`, `with_fallbacks` (Task 4).

- [ ] **Step 1: Write the failing tests** (`model=` a `RunnableLambda` recording its input and returning `AIMessage("Earlier the user asked about groceries.")`)

```python
async def test_under_budget_does_nothing(monkeypatch)
async def test_over_budget_folds_every_earlier_turn_and_sets_the_cutoff(monkeypatch)   # CHAT_HISTORY_MAX_TOKENS=1; returns both keys; summary_through == last earlier message's id; current turn not sent
async def test_the_summariser_reads_stubbed_turns_not_raw_tool_results()               # a ToolMessage with "180.50 EUR" in content: "180.50" not in what the model received; the stub is
async def test_the_existing_summary_is_folded_in()
async def test_a_failed_summary_call_is_logged_and_the_turn_proceeds()                 # model raises → None
async def test_the_prompt_forbids_figures()                                            # "Never include amounts" in load_summary_prompt()
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** `APP_ENV=test uv run pytest tests/unit/agents/chatbot -v` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "chatbot: own summary middleware; the transcript stays, only the request is folded"`

---

### Task 10: Turn-bound middleware

Exactly today's semantics (`tests/unit/agents/chatbot/test_graph.py::TestTurnLimits`, `TestRepeatedCall`, `TestEmptyReply` are the reference).

**Files:**
- Create: `server/app/agents/chatbot/middleware/turn_bound.py`
- Test: `server/tests/unit/agents/chatbot/middleware/test_turn_bound.py`

**Interfaces:**
- Produces: `WRAP_UP_INSTRUCTION`, `STOPPED_FALLBACK_TEXT` (verbatim); `turn_steps(messages) -> int` (AI messages with tool calls after the last `HumanMessage`); `repeated_call(messages) -> bool` (today's function, moved); `class TurnBoundMiddleware(AgentMiddleware[ChatState, TurnContext])` with `awrap_model_call(request, handler)`:
  1. `response = await handler(request)`; `message = response.result[0]`.
  2. No tool calls: if `not message.text.strip()` → `logger.warning("llm_empty_response", conversation_id=thread id from get_config(), model=message.response_metadata.get("model_name"), status=…, incomplete_details=…)` and `raise Exception("the model returned an empty reply")`; else return `response`.
  3. Tool calls: `steps = turn_steps(request.state["messages"])`; `reason = "step_limit" if steps + 1 >= settings.llm.CHAT_MAX_STEPS else "repeated_call" if repeated_call([*request.state["messages"], message]) else None`; `None` → return `response`.
  4. `logger.warning("chat_turn_stopped", conversation_id=…, reason=reason, steps=steps)`; wrap-up: `try: final = (await handler(request.override(tools=[], messages=[*request.messages, SystemMessage(WRAP_UP_INSTRUCTION)]))).result[0]` and accept it only if `final.text.strip() and not final.tool_calls`; otherwise (or on exception, logged `llm_wrap_up_failed`) `final = AIMessage(content=STOPPED_FALLBACK_TEXT)`; `final.id = final.id or str(uuid.uuid4())`; return `ExtendedModelResponse(model_response=ModelResponse(result=[final]), command=Command(update={"stopped": {**request.state.get("stopped", {}), final.id: reason}}))`.
- The dropped tool-calling response is never returned, so never persisted or executed.

- [ ] **Step 1: Write the failing tests** (a `handler` fed a queue of `AIMessage`s or exceptions and recording each request's `tools` and `messages`)

```python
async def test_every_call_up_to_the_cap_is_made_with_tools_and_goes_on_to_the_tools(monkeypatch)   # CHAT_MAX_STEPS=2, steps so far 0 → returned as is
async def test_the_capth_tool_calling_response_is_dropped_and_a_tool_less_wrap_up_answers(monkeypatch)  # steps so far 1, cap 2: handler called twice, second with tools=[] and a trailing SystemMessage(WRAP_UP_INSTRUCTION); command sets stopped[final.id] == "step_limit"; the first response's calls are not in the result
async def test_a_text_answer_on_the_last_allowed_call_ends_the_turn_unstopped(monkeypatch)
async def test_a_repeated_call_stops_the_loop_with_its_reason()                                     # stopped[...] == "repeated_call"
async def test_a_failing_wrap_up_falls_back_to_the_fixed_text()                                     # second handler call raises → STOPPED_FALLBACK_TEXT, still stopped
async def test_an_empty_wrap_up_falls_back_to_the_fixed_text()
async def test_a_wrap_up_that_asks_for_tools_falls_back_to_the_fixed_text()                         # Review Focus 2
async def test_an_empty_reply_fails_the_turn_and_is_logged_with_the_model()                         # pytest.raises(Exception, match="empty reply"); log has model and status
async def test_stopped_keeps_earlier_entries()                                                      # state stopped={"old": "step_limit"} → both keys in the command
def test_turn_steps_counts_only_this_turn()
def test_repeated_call_cases()                                                                      # the three cases of TestRepeatedCall
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** the file → PASS.
- [ ] **Step 5: Commit** — `git commit -m "chatbot: turn-bound middleware (step cap, repeat detection, wrap-up)"`

---

### Task 11: Tool-events middleware and model-timing middleware

**Files:**
- Create: `server/app/agents/chatbot/middleware/tool_events.py`, `server/app/agents/chatbot/middleware/model_timing.py`
- Test: `server/tests/unit/agents/chatbot/middleware/test_tool_events.py`, `test_model_timing.py`

**Interfaces:**
- Produces (`tool_events.py`): `TOOL_FAILED_MESSAGE`, `TOOL_UNKNOWN_MESSAGE`, `TOOL_ARGS_LOG_LIMIT` (verbatim); `@dataclass(frozen=True) class ToolCallStarted: id: str; name: str`; `@dataclass(frozen=True) class ToolCallFinished: id: str; ok: bool; artifact: dict | None`; `format_tool_args(args: dict) -> str` and `format_validation_error(error: ValidationError) -> str` (today's functions); `class ToolEventsMiddleware(AgentMiddleware)` with `awrap_tool_call(request, handler)`:
  1. `call = request.tool_call`; `writer = request.runtime.stream_writer`; `error(content) = ToolMessage(content=content, name=call["name"], tool_call_id=call["id"], status="error")`.
  2. `request.tool is None` → `logger.error("tool_call_unknown_tool", tool_name=call["name"])` (the hook does not see the tool list, so the line no longer carries `known_tools`), `tool_calls_total.labels(tool=name, outcome="unknown_tool").inc()`, return `error(TOOL_UNKNOWN_MESSAGE)`; **no** started/finished event (today announces nothing for an unknown tool).
  3. `writer(ToolCallStarted(id=call["id"], name=call["name"]))`; `logger.debug("tool_call_started", tool_name, tool_args=format_tool_args(call["args"]))`; `started = time.perf_counter()`; `finish(outcome)` observes `tool_call_duration_seconds{tool}` and increments `tool_calls_total{tool, outcome}`, returning the duration.
  4. `request.tool.args_schema.model_validate(call["args"])` → on `ValidationError`: `finish("invalid_args")`, `logger.warning("tool_call_invalid_args", …)`, `message = error(format_validation_error(e))`.
  5. Else `try: message = await handler(request)` → `ToolException` → `finish("invalid_args")`, `logger.warning("tool_call_rejected_args", …)`, `error(str(e))`; any other `Exception` → `finish("error")`, `logger.exception("tool_call_failed", …)`, `error(TOOL_FAILED_MESSAGE)`; success → `finish("success")`, `logger.info("tool_call_completed", …, result_chars=len(message.content))`.
  6. `writer(ToolCallFinished(id=call["id"], ok=message.status != "error", artifact=message.artifact if message.status != "error" else None))`; return `message`.
- Produces (`model_timing.py`): `class ModelTimingMiddleware(AgentMiddleware)` with `awrap_model_call(request, handler)`: time the handler; `answering = result.response_metadata.get("model_name") or request.model.model_name`; `llm_inference_duration_seconds.labels(model=answering).observe(elapsed)`; `logger.info("llm_response_generated", model=answering, wrap_up=not request.tools, environment=settings.ENVIRONMENT.value)`; an `OpenAIError` escaping the handler is re-raised as `translate_error(e)` (logged `llm_call_failed_all_models` with `conversation_id`).

- [ ] **Step 1: Write the failing tests** (a `ToolCallRequest(tool_call=…, tool=StructuredTool|None, state={}, runtime=stub with `stream_writer=list.append`)`; a tool built as Task 12 will build them: `args_schema` with an `n: int` field; metric deltas read from `prometheus_client.REGISTRY.get_sample_value` as `test_graph.py:65-75` does)

```python
async def test_success_carries_the_artifact_and_emits_started_then_finished()
async def test_invalid_arguments_return_the_validation_message_and_count_invalid_args()   # "Invalid arguments: n: Input should be a valid integer…"; finished ok=False, artifact None
async def test_tool_exception_text_reaches_the_model_as_invalid_args()
async def test_a_crash_returns_the_fixed_message_and_counts_error()
async def test_an_unknown_tool_returns_the_fixed_text_without_events_and_counts_unknown_tool()
async def test_duration_is_observed_on_every_outcome()
async def test_long_args_are_truncated_in_the_log()                                        # TOOL_ARGS_LOG_LIMIT
async def test_one_valid_and_one_invalid_call_both_report()                                # Review Focus 5: two requests through the hook; two started, two finished, outcomes success+invalid_args
async def test_timing_labels_the_answering_model_from_the_response_metadata()
async def test_timing_falls_back_to_the_requested_model_name()
async def test_a_provider_error_is_translated()                                            # RateLimitError → LLMRateLimitError
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** the two files → PASS.
- [ ] **Step 5: Commit** — `git commit -m "chatbot: tool-events and model-timing middleware"`

---

### Task 12: `conversation/tools/` — the seven tools as `StructuredTool`s; `ToolDisplay` family in `conversation/schemas.py`

`finance/` stays untouched and keeps serving the old agent; `tools/` is built from a copy and tested on its own. Task 13 deletes `finance/`. The display models are defined in `conversation/schemas.py` from here on (duplicating `toolkit.py`'s for one commit).

**Files:**
- Create: `server/app/modules/conversation/tools/__init__.py`, `tools/base.py`, `tools/analytics.py` (from `finance/service.py` + `finance/schemas.py`'s `PeriodArgs`, `TopMerchantsArgs`), `tools/search.py` (from `finance/domain/search.py` + `SearchArgs`, `Amount`), `tools/display.py` (copy of `finance/display.py`, imports changed), `tools/periods.py` (from `finance/domain/periods.py` + `resolve_period`, `preamble`)
- Modify: `server/app/modules/conversation/schemas.py` (add `SummaryKind`, `ColumnKind`, `SummaryItem`, `TableColumn`, `ToolTable`, `ToolDisplay`, verbatim from `toolkit.py:41-89` with their docstrings; `conversation/__init__.py` does **not** export `chat_tools` yet)
- Tests: `tests/unit/modules/conversation/tools/{__init__,test_analytics,test_search,test_display,test_periods,test_schemas}.py` (moved from `tests/unit/modules/conversation/finance/`, imports and the toolkit-shaped assertions updated), `tests/integration/modules/conversation/tools/{__init__,conftest,test_tools}.py` (moved from `…/finance/`), `tests/unit/modules/conversation/test_schemas.py` (+ `test_display_models_forbid_unknown_fields` from `test_toolkit.py:46`)

**Interfaces:**
- `tools/base.py`: `class ToolArgs(BaseModel)` with `model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)` and `runtime: Annotated[SkipValidation[Optional[ToolRuntime]], InjectedToolArg] = Field(None, exclude=True)`; `async def turn_history(ctx: TurnContext) -> AnalyticsHistory` (Task 6's slot); `def chat_tool(coroutine, *, name: str, title: str, description: str, args_schema: type[ToolArgs]) -> StructuredTool` = `StructuredTool.from_function(coroutine=coroutine, name=name, description=description, args_schema=args_schema, response_format="content_and_artifact", metadata={"title": title})`. `NO_TRANSACTIONS = "The user has no transactions yet."`.
- `tools/periods.py`: today's naming functions; `resolve_period(args: PeriodArgs, history) -> tuple[DateRange, str]` raising `ToolException` (the library's) with today's messages; `async def preamble(ctx: TurnContext) -> str` (verbatim wording).
- `tools/analytics.py`: `PeriodArgs(ToolArgs)`, `TopMerchantsArgs(PeriodArgs)` (fields and validators verbatim); `PERIOD_HELP`, `CATEGORY_TOP_N`, `ANOMALY_STD_THRESHOLD = 2.5`, `ANOMALY_WINDOW_DAYS = 30`; `_analytics_tool(name, title, description, args_schema, fetch, render) -> StructuredTool` whose coroutine is `async def run(runtime: ToolRuntime[TurnContext], **kwargs) -> tuple[str, dict]`: `args = args_schema(**kwargs)`; `history = await turn_history(runtime.context)`; `date_range, label = resolve_period(args, history)`; `content, display = render(fetch(history, date_range, args), label)`; `return content, display.model_dump()`; `def analytics_tools() -> list[BaseTool]` — the six declarations with today's names, titles and descriptions byte for byte.
- `tools/search.py`: `Amount`, `SearchArgs(ToolArgs)`, `Totals`, `SearchResult`, `search_rows`, `SAMPLE_SIZE`, `GROUP_LIMIT`, `WEEKDAYS`; `def search_tool() -> BaseTool` (name `search_transactions`, title `Transaction search`, description verbatim).
- `tools/display.py`: every renderer returns `tuple[str, ToolDisplay]` instead of `ToolOutcome`; `ToolDisplay` and friends imported from `app.modules.conversation.schemas`.
- `tools/__init__.py`: `def chat_tools() -> list[BaseTool]: return [*analytics_tools(), search_tool()]`; `chat_preamble = preamble`.
- Consumes: `TurnContext` from `app.agents.chatbot.context` (Task 6).

- [ ] **Step 1: Move the unit tests to `tools/` and adapt them**: `test_schemas.py` guards `tool.tool_call_schema.model_json_schema()` of every tool in `chat_tools()` for the absence of `"pattern"`, and that `runtime` is not among the properties; `test_analytics.py` keeps `resolve_period`/`preamble` cases, expecting `ToolException`, and `test_the_tools_hold_the_seven_names` (`[t.name for t in chat_tools()] == [...]`, `t.metadata["title"]` as today's titles); `test_display.py` unpacks `(content, display)`.
- [ ] **Step 2: Move the integration tests**: the `run(name, ctx, **args)` helper invokes the tool through a `ToolNode` in a two-node `StateGraph(MessagesState, context_schema=TurnContext)` compiled once in the conftest (the way the runtime gets injected); it sends one `AIMessage` carrying the call with `context=ctx` and returns the resulting `ToolMessage` (`content`, `artifact`). The seven assertions are unchanged.
- [ ] **Step 3: Run the moved tests to see them fail** (`ModuleNotFoundError: app.modules.conversation.tools`).
- [ ] **Step 4: Build `tools/` and the schemas additions**
- [ ] **Step 5: Run**

Run: `APP_ENV=test uv run pytest tests/unit/modules/conversation -v && APP_ENV=test uv run pytest tests/integration/modules/conversation/tools -v && uv run lint-imports`
Expected: PASS; `lint-imports` keeps R9 (nothing under `tools/` is a `domain` slot) and R10 (`finance` row still the one enforced).

- [ ] **Step 6: Commit**

```bash
git add -A server/app/modules/conversation server/tests
git commit -m "conversation: tools/ holds the seven chat tools as StructuredTools; display models in schemas"
```

---

### Task 13: Cutover — `build_chatbot`, `ChatbotAgent`, the wire in `conversation`, the routes, and the deletions

The largest task; every step is one checkable change and the integration suite is the gate. Order inside the task keeps the tree importable at each step, but only the final state must pass the suite.

**Files:**
- Create: `server/app/agents/chatbot/agent.py`, `server/app/modules/conversation/domain/__init__.py`, `domain/chat.py`, `server/tests/fakes/__init__.py`, `tests/fakes/chat_model.py`, `tests/unit/agents/chatbot/test_graph.py` (rewritten), `tests/unit/agents/chatbot/test_agent.py`, `tests/unit/modules/conversation/domain/__init__.py`, `domain/test_chat.py`
- Modify: `server/app/agents/chatbot/graph.py` (old content deleted; `build_chatbot`), `state.py` (`GraphState` deleted), `context.py` (trimming code deleted), `chatbot/__init__.py`, `agents/__init__.py`, `title.py` (`first_exchange` leaves), `app/modules/conversation/schemas.py`, `router/chatbot.py`, `service.py`, `dependencies.py`, `conversation/__init__.py`, `app/main.py`, `server/pyproject.toml` (R10 row), `tests/integration/conftest.py`, `tests/integration/modules/conversation/router/test_chatbot.py`, `tests/integration/modules/conversation/test_service.py` (title), `tests/unit/modules/conversation/test_schemas.py`, `tests/unit/agents/chatbot/test_title.py`
- Delete: `app/agents/base/`, `app/agents/factory.py`, `app/agents/graph.py`, `app/agents/messages.py`, `app/agents/chatbot/toolkit.py`, `app/agents/chatbot/events.py`, `app/modules/conversation/finance/`, `tests/unit/agents/test_base_agent.py`, `test_factory.py`, `test_graph.py` (agents), `test_messages.py`, `tests/unit/agents/chatbot/test_toolkit.py`, `test_context.py`, `tests/unit/modules/conversation/finance/`, `tests/integration/modules/conversation/finance/`

**Interfaces:**
- `tests/fakes/chat_model.py`: `class ScriptedChatModel(BaseChatModel)` with fields `responses: list[Any]` (each an `AIMessage`, an `Exception` to raise, or a zero-argument async callable returning an `AIMessage`, so a test can block a call until cancelled), `sent: list[list[BaseMessage]] = []`, `bound_tools: list = []`; `_llm_type = "scripted"`; `bind_tools(tools, **kw)` records and returns `self`; `_generate` raises `NotImplementedError("async only")`; `_agenerate` appends `messages` to `sent` and pops `responses[0]` (raising or awaiting as above), returning `ChatResult(generations=[ChatGeneration(message=…)])`.
- `graph.py`: `RECURSION_LIMIT_MARGIN = 3`; `turn_recursion_limit(max_steps: int) -> int`; `build_chatbot(checkpointer, tools: Sequence[BaseTool], preamble: Callable[[TurnContext], Awaitable[str]], *, model: BaseChatModel | None = None) -> CompiledStateGraph` — `ValueError("the chatbot needs at least one tool")` on an empty list; `model` defaults to `chat_model(max_tokens=settings.llm.CHAT_REPLY_MAX_TOKENS, reasoning_effort=settings.llm.CHAT_REASONING_EFFORT)`; `middleware = [MemoryMiddleware(), SummaryMiddleware(), TurnBoundMiddleware(), RequestShapingMiddleware(preamble), ModelTimingMiddleware(), *([ModelFallbackMiddleware(*fallbacks)] if (fallbacks := fallback_models(max_tokens=…, reasoning_effort=…)) else []), ToolEventsMiddleware()]` — in that order (first is outermost: the turn bound wraps shaping, which wraps timing, which wraps the fallback); `create_agent(model, list(tools), system_prompt=load_system_prompt(), middleware=middleware, state_schema=ChatState, context_schema=TurnContext, checkpointer=checkpointer, name=f"{PROJECT_NAME} Agent ({settings.ENVIRONMENT.value})")`; logs `graph_created` as today. When `model` is given (tests), no fallback middleware is added.
- `agent.py`: `class ChatbotAgent` with `__init__(self, graph: CompiledStateGraph, tools: Sequence[BaseTool])`; `tool_titles: dict[str, str]` (`{t.name: t.metadata["title"] for t in tools}`); `_turn_config(conversation_id, context) -> dict` = `create_graph_config(conversation_id, context.user_id)` plus `recursion_limit=turn_recursion_limit(settings.llm.CHAT_MAX_STEPS)`; `async def stream(self, message: str, conversation_id: uuid.UUID, context: TurnContext) -> AsyncIterator[tuple[str, Any]]` yields `graph.astream({"messages": [HumanMessage(message)]}, config=…, context=context, stream_mode=["messages", "custom"])`; `async def run(self, message, conversation_id, context) -> tuple[list[BaseMessage], dict[str, str]]` via `ainvoke`; `async def state(self, conversation_id) -> tuple[list[BaseMessage], dict[str, str]]` via `aget_state(config={"configurable": {"thread_id": str(conversation_id)}})`, `([], {})` when the thread has no values. Logs `chatbot_agent_initialized` with the model name from settings.
- `conversation/schemas.py` gains, verbatim from `agents/messages.py:35-84` and `agents/chatbot/events.py` (docstring included): `ReasoningPart`, `ToolPart`, `ActivityPart`, `Activity`, `ChatMessage`, `TextEvent`, `ReasoningEvent`, `ToolStartedEvent`, `ToolFinishedEvent`, `DoneEvent`, `ErrorEvent`, `StreamEvent`. The `ChatMessage` import from `agents.messages` goes.
- `conversation/domain/chat.py` (pure; imports `ToolCallStarted`/`ToolCallFinished` from `app.agents.chatbot.middleware.tool_events` and the schemas): `TURN_MESSAGE_SEPARATOR = "\n\n"`, `MODEL_NODE = "model"`; `content_text(content) -> str`, `summary_items(content) -> Iterator[tuple[tuple, str]]`, `reasoning_text(content) -> str` (today's three helpers from `base/agent.py:71-96`, adapted per Task 1's finding: if standard `reasoning` content blocks carry the item boundaries, `summary_items` reads `message.content_blocks`; otherwise it keeps today's raw parsing — either way this is the only place that parses reasoning); `history(messages: list[BaseMessage], stopped: dict[str, str], titles: Mapping[str, str]) -> list[ChatMessage]` (today's `_process_messages`/`_reply`/`_tool_part`, with `titles.get(name)` in place of `_tool_title`; a display that fails validation keeps the row without figures and logs `chat_history_tool_display_invalid`); `first_exchange(history: list[ChatMessage]) -> tuple[str, str] | None` (moved from `title.py`); `async def events(stream: AsyncIterator[tuple[str, Any]], titles: Mapping[str, str]) -> AsyncIterator[StreamEvent]` — today's `get_stream_response` loop over `(mode, payload)`: custom `ToolCallStarted` → `ToolStartedEvent(id, name, title=titles[name])` (a name not in `titles` yields nothing); `ToolCallFinished` → `ToolFinishedEvent(id, ok, display=ToolDisplay.model_validate(artifact) if ok and artifact is not None else None)`, a `ValidationError` logged (`chat_stream_tool_display_invalid`) and `display=None`; messages mode: only `AIMessage`/`AIMessageChunk` with `metadata.get("langgraph_node") == MODEL_NODE`; reasoning deltas keyed by `(message.id, *item_key)` with the separator rule; text deltas keyed by `message.id`; **the fix**: a text event sets `last_reasoning_key = "text"` (a sentinel, not `None`), so the next reasoning delta starts with `"\n\n"`; a tool event resets it to `None` as today. No `done` here. `done(messages: list[BaseMessage], stopped: dict[str, str]) -> DoneEvent` — `stopped=bool(messages) and messages[-1].id in stopped`.
- `router/chatbot.py`: `chat`: `messages, stopped = await agent.run(chat_request.message, conversation.id, turn_context)`; `ChatResponse(message=history(messages, stopped, agent.tool_titles)[-1])`. `chat_stream`: `with llm_stream_duration_seconds.labels(model=settings.llm.DEFAULT_LLM_MODEL).time(): async for event in events(agent.stream(...), agent.tool_titles): yield …; messages, stopped = await agent.state(conversation.id); yield done(messages, stopped)`; the `except` branches as today with `ErrorEvent` from the schemas. `get_conversation_messages`: `ConversationHistory(messages=history(*await agent.state(conversation.id), agent.tool_titles))`.
- `service.py::generate_title(session, conversation, agent)`: `messages, stopped = await agent.state(conversation.id)`; `exchange = first_exchange(history(messages, stopped, agent.tool_titles))`; `None` → return; `try: title = await generate_title(user_text, reply_text, conversation.id, conversation.user_id) except Exception: logger.exception("conversation_title_generation_failed", …); return conversation`; the rest as today.
- `dependencies.py` and `service.py` import `ChatbotAgent` from `app.agents.chatbot`; `conversation/__init__.py` exports `chat_tools` and `chat_preamble` instead of `finance_toolkit`.
- `main.py`: `from app.modules.conversation import chat_preamble, chat_tools`; in the lifespan: `tools = chat_tools(); graph = build_chatbot(checkpointer, tools, chat_preamble); app.state.agents = {"chatbot": ChatbotAgent(graph, tools)}`; `agent_toolkits` goes; the checkpointer imports come from `app.agents.core`.
- `pyproject.toml`: the R10 row for conversation is renamed `"R10: conversation's core never imports its tools sub-package"` with `forbidden_modules = ["app.modules.conversation.tools"]`.
- `tests/integration/conftest.py`: `scripted_model` fixture → `ScriptedChatModel(responses=[AIMessage(content="Hi there!")])`; `agent` fixture → `ChatbotAgent(build_chatbot(MemorySaver(), chat_tools(), chat_preamble, model=scripted_model), chat_tools())` with `app.agents.chatbot.middleware.memory.get_relevant_memory`/`update_memory` patched to `AsyncMock(return_value="")`/`AsyncMock()`; `authenticated_client_with_agent(authenticated_client, agent, db_session)` overrides `get_chatbot_agent` and sets `app.state.session_factory` to an `asynccontextmanager` yielding `db_session` (so the preamble and the tools read the seeded rows). `mock_agent` goes.

- [ ] **Step 1: Park the old loop**: `git mv app/agents/chatbot/graph.py app/agents/chatbot/legacy.py` and point `factory.py`, `conversation/service.py`, `conversation/dependencies.py`, `agents/__init__.py`, `tests/unit/agents/chatbot/test_graph.py` and `tests/integration/modules/conversation/router/test_chatbot.py` at `legacy`. Run `APP_ENV=test uv run pytest tests/unit -q -m unit` → PASS. (No commit: the next steps replace all of it.)
- [ ] **Step 2: Write `tests/fakes/chat_model.py`** and a smoke test in `tests/unit/agents/chatbot/test_graph.py`:

```python
async def test_a_text_turn_is_persisted_and_streams_from_the_model_node()   # build_chatbot(MemorySaver(), [a test tool], preamble, model=ScriptedChatModel(responses=[AIMessage("hi")])); astream yields ("messages", (AIMessage, {"langgraph_node": "model"})); aget_state holds Human+AI
```
Memory hooks patched as in the conftest above. The test tools are the test's own (`tests/unit/agents` does not import a module's tools): `StructuredTool.from_function(coroutine=…, args_schema=<a model shaped like Task 12's ToolArgs, defined in the test>, response_format="content_and_artifact", metadata={"title": "t title"})`.

- [ ] **Step 3: Run it** → FAIL (`build_chatbot` undefined). **Write `graph.py` (`build_chatbot`) and `agent.py`; delete `GraphState` and the trimming code; `chatbot/__init__.py` exports `build_chatbot`, `ChatbotAgent`, `TurnContext`.** Run → PASS.
- [ ] **Step 4: Port the loop tests into `tests/unit/agents/chatbot/test_graph.py`** on a `MemorySaver`, scripted model and test tools (each case from today's `TestTurnLimits`, `TestToolCallNode`, `TestStreamAndHistory`, `TestChat`):

```python
async def test_step_cap_ends_the_turn_with_a_wrap_up_answer_marked_stopped(monkeypatch)   # CHAT_MAX_STEPS=2: model scripts [call, call, text]; tool ran once; state messages end with the text; stopped[final.id] == "step_limit"; the second call's AIMessage is not in state
async def test_a_long_cap_is_what_ends_the_turn_not_langgraphs_recursion_limit(monkeypatch)  # CHAT_MAX_STEPS=12 with recursion_limit=turn_recursion_limit(12): 12 tool-calling replies then a wrap-up; no GraphRecursionError
async def test_repeated_identical_call_stops_the_loop()
async def test_a_failing_wrap_up_falls_back_to_the_fixed_text(monkeypatch)
async def test_the_next_turn_works_after_a_stopped_one(monkeypatch)
async def test_tool_calls_run_concurrently_and_one_crash_does_not_sink_the_other()   # two calls in one reply, one tool raising; both ToolMessages, in call order
async def test_the_custom_stream_carries_started_and_finished_for_each_call()
async def test_an_unknown_tool_gets_the_fixed_text_and_no_event()
async def test_the_request_carries_the_system_prompt_then_turn_context_then_the_question()   # scripted model's sent[0]: SystemMessage(system prompt) first, SystemMessage containing "Today's date" before the HumanMessage
async def test_a_tool_call_left_without_a_result_is_not_sent()                               # aupdate_state with a dangling call, then a turn: sent[0] has no tool call id
async def test_a_failed_preamble_still_answers_the_turn()
async def test_a_thread_checkpointed_before_this_step_still_answers()                       # Review Focus 1: aupdate_state(config, {"messages": [Human, AI]}) with no summary keys, then a turn → answered; sent[0] has no summary message
async def test_the_empty_reply_fails_the_turn_and_nothing_empty_is_checkpointed()
def test_an_empty_tools_list_fails_startup()                                                 # ValueError
def test_the_graph_is_named_for_the_project_and_environment()
```

- [ ] **Step 5: Write `tests/unit/agents/chatbot/test_agent.py`**: `stream` passes `context=` and the recursion limit and thread id in the config (a `MagicMock` graph records `astream`'s kwargs); `run` returns `(messages, stopped)`; `state` returns `([], {})` for an unknown thread; `tool_titles` maps names to metadata titles. Run → PASS.
- [ ] **Step 6: Write `tests/unit/modules/conversation/domain/test_chat.py`** — the history and stream cases of `tests/unit/agents/test_base_agent.py` (lines 121-262 and 350-490) over `history()`/`events()`/`done()` with hand-built `(mode, payload)` streams (`("messages", (AIMessageChunk, {"langgraph_node": "model"}))`, `("custom", ToolCallStarted(...))`), plus:

```python
async def test_a_reasoning_delta_after_a_text_event_starts_a_new_paragraph()     # the separator fix: text then reasoning → the reasoning event begins with "\n\n"
async def test_an_artifact_that_does_not_validate_streams_a_null_display()      # Review Focus 3: ToolCallFinished(ok=True, artifact={"bogus": 1}) → ToolFinishedEvent(ok=True, display=None), logged
async def test_a_started_event_for_a_name_without_a_title_yields_nothing()
def test_first_exchange_pairs_the_first_reply_with_the_question_it_answered()    # moved from test_title.py
def test_first_exchange_is_none_before_any_reply()
def test_done_is_stopped_only_when_the_last_message_is_in_stopped()
```
Run → FAIL on import. **Write `conversation/schemas.py` additions and `domain/chat.py`.** Run → PASS.

- [ ] **Step 7: Switch the routes, the service, the dependencies, the module root, `main.py` and `pyproject.toml`; delete the old files and their tests** (the list above). `tests/unit/modules/conversation/test_schemas.py` gains `test_stream_events_are_discriminated_by_type` (from `test_toolkit.py:53`) and the history models' required-defaults check; `tests/unit/agents/chatbot/test_title.py` drops the `first_exchange` cases.
- [ ] **Step 8: Rewrite the integration fixtures and tests**: `tests/integration/conftest.py` as in Interfaces; in `tests/integration/modules/conversation/router/test_chatbot.py` every `mock_agent` use becomes the scripted model (`scripted_model.responses[:] = [...]`), the two "gives the agent the user's turn context" tests assert through a lookup (`responses = [AIMessage(tool_calls=[spending_overview months=1]), AIMessage("…")]` and the `tool_finished` display is this user's figure, not `other_user`'s), the "releases the connection before the model call" tests keep their mechanism (the model response callable checks the session state), `test_stream_failure…` scripts an exception, `test_disconnect…` scripts a callable that waits on an `asyncio.Event` and records cancellation; `TestFinanceToolsThroughTheRoute` builds the agent with `build_chatbot(MemorySaver(), chat_tools(), chat_preamble, model=…)` and reads `scripted_model.sent[1]` for the `ToolMessage` assertion — its frame and content assertions are unchanged. `tests/integration/modules/conversation/test_service.py`'s title test scripts the model through `agent.state`.
- [ ] **Step 9: Reasoning parsing per Task 1**: if the finding says standard blocks carry the boundaries, `summary_items` in `domain/chat.py` reads `content_blocks`; the `test_chat.py` reasoning cases feed chunks in the shape Task 1 observed. Otherwise nothing changes here.
- [ ] **Step 10: Run everything**

Run: `cd server && APP_ENV=test uv run pytest tests -q && uv run lint-imports && cd .. && make check-server && make check-contract`
Expected: all pass; `check-contract` leaves `server/openapi.json` and the generated client unchanged (`git status` clean under `web-app/packages/api-client/src/generated/` and `server/openapi.json`).

- [ ] **Step 11: Commit**

```bash
git add -A server web-app/packages/api-client
git commit -m "chatbot: create_agent plus middleware; the wire belongs to conversation; old loop, toolkit and finance/ deleted"
```

---

### Task 14: Cleanup, settings, docs, roadmap

**Files:**
- Delete: `server/app/integrations/llm/service.py`, `tests/unit/integrations/llm/test_registry.py`, `test_service.py`; `.superpowers/specs/2026-10-21-agent-core-design.md`, `.superpowers/plans/2026-10-21-agent-core.md`
- Modify: `server/app/integrations/llm/__init__.py` (exports: `chat_model`, `fallback_models`, `with_fallbacks`, `translate_error`, `is_reasoning_model`, `PLACEHOLDER_KEY`, `REASONING_EFFORT_DEFAULTS`, the five exceptions), `server/app/core/config.py` (delete `DEFAULT_LLM_TEMPERATURE`), `server/.env.example`, `server/.env.test` (delete the temperature line), `server/pyproject.toml` (drop `tenacity` if `grep -rn tenacity server/app` is empty; `uv lock`), `tests/unit/integrations/llm/test_service_import.py` (keep: it imports `app.main` without a credential), `docs/architecture/server.md:27,46,54,65-81,158,224-225`, `server/CLAUDE.md:235-249`, `docs/product/features/chat.md:104-107,144-149`, `docs/TODO.md:92-99,210-216,227-246,271-277,284-287`, `docs/ROADMAP.md:39`

- [ ] **Step 1: Delete `service.py` and its tests; fix the `__init__`; delete the setting and the env lines; `uv lock` if tenacity leaves**

Run: `cd server && grep -rn "LLMService\|LLMRegistry\|DEFAULT_LLM_TEMPERATURE\|tenacity" app tests` → no output. `APP_ENV=test uv run pytest tests -q && uv run lint-imports` → PASS.

- [ ] **Step 2: Docs**
  - `server.md` §1: the Adapters row names `app/agents/` as "core/ (memory, checkpointing, observability, structured calls), the chatbot, the one-call agents"; the tree comment for `conversation/` reads `tools/ is its feature sub-package: the chat's tools over analytics and transaction`; the `agents/` line reads `core/, chatbot/ (create_agent + middleware), the one-call agents (csv_mapping/, transaction_labeler/, insights/)`; the "`llm` is an adapter" paragraph drops the `Message` sentence; the "Agents get module knowledge by injection" paragraph is rewritten: `conversation/tools/` builds `chat_tools()` (seven `StructuredTool`s) and `chat_preamble`; `main.py` compiles `build_chatbot(checkpointer, chat_tools(), chat_preamble)` and puts `ChatbotAgent(graph, tools)` on `app.state.agents`; the route builds a `TurnContext(user_id, session_factory)` per turn and passes it as the graph's `context=`; a tool declares `runtime: ToolRuntime[TurnContext]` and reads the user from `runtime.context`; the history and the stream events are `conversation`'s (`schemas.py`, `domain/chat.py`); the stream contract docstring lives on the event models in `conversation/schemas.py`. §2's feature sub-package paragraph and §3's R10 sentence name `conversation/tools/` and drop its `domain` slot.
  - `server/CLAUDE.md` **Agent Architecture**: a conversational agent is `create_agent` plus `AgentMiddleware` classes under its package, held by a thin object the lifespan builds; a one-shot call is a function over `ask()` (`app/agents/core/structured.py`); shared components under `app/agents/core/`; **Tools**: a `StructuredTool` built by `chat_tool()` in `conversation/tools/`, its arguments a `ToolArgs` subclass (the injected runtime slot), `ToolException` for bad arguments, no regex `pattern` (`test_schemas.py` guards `tool_call_schema`); the middleware list with one line each; retries are the client's `max_retries`, tenacity is gone.
  - `chat.md` §4: the bounded-context bullet becomes: the reply may use `CHAT_REPLY_MAX_TOKENS`; earlier turns are sent stubbed and, once they pass `CHAT_HISTORY_MAX_TOKENS`, are folded into a running summary (figure-free by prompt and by construction: the summariser reads the stubbed turns) sent in their place, while the saved transcript keeps every message, so a reopened conversation shows it all; if the summary call fails the oldest turns are dropped for that turn as before. The "Stopping a reply while a lookup runs" bullet names `app/agents/core/messages.py`. §5 drops summaries from "Not built".
  - `TODO.md`: delete *Server — the agent layer imports the chatbot's stream contract* and *Chat — conversation summaries*; delete the three absorbed bullets of *Chat — code review leftovers* (the `TurnContext.cache` one, the double lookup one, the two reasoning paragraphs one) and the `LLMRegistry.get` overrides bullet (its subject is gone); reword *every LLM call starts at the default model* to the fallback chain (every call starts at `DEFAULT_LLM_MODEL` and walks `LLM_FALLBACK_MODELS`; the client's `max_retries` is spent on the primary first).
  - `ROADMAP.md`: the 7b row's state to `complete`, its last column to the docs that now hold the facts (`architecture/server.md` §1, `chat.md` §4); the "No spec yet" goes.
- [ ] **Step 3: Delete the spec and this plan; run the full gate**

Run: `make check-server && make check-contract && cd server && APP_ENV=test uv run pytest tests -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "7b Agent core: LLMService and the registry go; docs, TODO and roadmap updated; spec and plan retired"
```

---

## Self-review notes

- **Spec coverage.** §3 layout → Tasks 3, 12, 13 (plus `tools/base.py`, justified); §4.1–4.5 → Tasks 7–11, 13; §5 → Task 12 (and the runtime-slot finding); §6 → Task 13; §7 → Tasks 8, 9; §8 → Task 7; §9 → Task 4 (+ Task 14 for the deletions); §10 → Task 5; §11 → Tasks 1, 2; §14 → each task's tests, the integration seam in Task 13; §15 → Task 14.
- **Names used across tasks.** `TurnContext(user_id, session_factory, history)` (6 → 8, 12, 13); `ChatState` (7 → 8–10, 13); `split_turns`, `shape_turn`, `turns_after`, `count_tokens` (8 → 9); `ToolCallStarted(id, name)`, `ToolCallFinished(id, ok, artifact)` (11 → 13); `chat_model`, `fallback_models`, `with_fallbacks`, `translate_error` (4 → 5, 9, 11, 13); `chat_tools()`, `chat_preamble` (12 → 13); `ChatbotAgent(graph, tools)` with `stream`/`run`/`state`/`tool_titles` (13); `history`, `events`, `done`, `first_exchange` (13).
- **Calls made here, for the user to check while reading**: the budget counts the shaped earlier turns alone (Task 8); the summary folds every pending turn at once (Task 9); `tools/base.py` exists (spike finding); the schema the model sees loses `additionalProperties: false` and per-property titles (spike finding); `events()` yields no `done`, the router composes `done()` after reading the state (Task 13); the unknown-tool log line no longer lists the known tools (Task 11); the stream-duration metric is labelled with `DEFAULT_LLM_MODEL` (spec §9).
