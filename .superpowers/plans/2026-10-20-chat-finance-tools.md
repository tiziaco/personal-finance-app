# 7 Chat finance tools — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The chat assistant answers questions about the user's own money from read-only tools over the analytics library and a transaction search, shows its thinking and tool calls in a collapsible activity block, and closes the three ride-along TODOs.

**Architecture:** The generic loop stays in `app/agents/chatbot/` (a two-node LangGraph graph) and gains a small toolkit contract (`AgentTool`, `Toolkit`, `TurnContext`). The finance tools are a feature sub-package of the `conversation` module (`app/modules/conversation/finance/`) that builds a `Toolkit` over one per-turn `AnalyticsHistory`; `app/main.py` injects it at startup. The stream becomes typed events; the history returns each reply's activity parts; the web renders them in an `ActivityBlock` above the reply.

**Tech Stack:** FastAPI, LangGraph 1.x (`stream_mode=["messages","custom"]`, `get_stream_writer`), langchain-openai 1.x on OpenRouter (Responses API, already selected by the `reasoning` param), mem0 2.0, pytest + testcontainers; Next.js, assistant-ui 0.15, Vitest + Testing Library.

**Spec:** [`.superpowers/specs/2026-10-20-chat-finance-tools-design.md`](../specs/2026-10-20-chat-finance-tools-design.md) — read it first; section numbers below (§n) refer to it.

## Global Constraints

- Every figure the assistant states comes from a tool result in the same turn; the system prompt says so and old tool results are stubbed out of context (§1, §5.4).
- Read-only: no tool writes anything (§2).
- The user is never a tool argument; tools read `TurnContext.user_id` (§3).
- Web search is removed (§6).
- Memory receives only the current turn's user message; mem0 `custom_instructions` keep goals/circumstances/preferences, drop amounts (§6).
- Savings rate = the analytics one; with saving/investing questions, show the Savings & Investments amount beside it and explain investing lowers the rate; never compute an adjusted rate (§1).
- Chat reasoning effort is a setting, `CHAT_REASONING_EFFORT`, default `medium`; other `LLMRegistry` callers keep their effort (§9).
- Tool crashes return the fixed `TOOL_FAILED_MESSAGE`; exception text never enters a `ToolMessage` (§5.2).
- Import contracts R1, R2, R6, R9, R10 stay green; a new R10 contract covers `conversation/finance/`.
- `server/openapi.json` and the generated client are regenerated with `make gen-contract`, never hand-edited.
- Server conventions: `server/CLAUDE.md`, skills `server-patterns`, `server-testing`. Web: `web-app/CLAUDE.md`, skills `web-app-patterns`, `web-app-testing`, `finsight-design`.
- Commits end with `Claude-Session: https://claude.ai/code/session_014mkWV5RKcfnDTVGqQz9VcL`.

## Review Focus

1. **A user stops mid-tool, then sends again.** Expected: the next turn works (no provider 400) and the stopped turn reopens as a question with no answer and no activity. Test in Task 4 (graph) and Task 8 (history).
2. **Two tool calls in one model message, one crashes.** Expected: the other's result still arrives; the crashed one is `TOOL_FAILED_MESSAGE`; the stream emits two `tool_finished` events. Test in Task 3.
3. **A user with no transactions asks "where did my money go?".** Expected: the preamble says there is no data; tools return a no-data result, not zeros. Test in Task 6.
4. **A period outside the data ("in 2019") or an inverted range.** Expected: an actionable argument error naming the data span, not a crash and not an empty table read as €0. Test in Task 6.
5. **A long conversation whose earlier turns hold big tool results.** Expected: the current question and this turn's tool results always reach the model; earlier results are one-line stubs. Test in Task 5.

---

## File map

**Server — agent layer (`app/agents/`)**
- `chatbot/toolkit.py` (new) — `TurnContext`, `AgentTool`, `Toolkit`, `ToolArgumentError`, `ToolOutcome`, display models.
- `chatbot/events.py` (new) — stream event models.
- `chatbot/context.py` (new) — `build_model_context`.
- `chatbot/graph.py` — tool node, limits, wrap-up, stream events, answering-model name.
- `chatbot/state.py` — `turn_steps`, `stopped`.
- `chatbot/prompts/system.md`, `chatbot/prompts/__init__.py` — static prompt + turn-context renderer.
- `chatbot/tools/` — deleted (web search).
- `base/agent.py` — typed stream, history with activity, memory filter.
- `messages.py` — `ChatMessage`, `Activity`, part models.
- `graph.py` — `process_llm_response` keeps reasoning blocks; `prepare_messages` removed (replaced by `context.py`).
- `factory.py` — toolkit injection.
- `shared/memory/factory.py` — `custom_instructions`.

**Server — integrations / core / app**
- `integrations/llm/service.py` — `LLMRegistry.get_tuned`, `LLMService(max_tokens=, reasoning_effort=)`, `call(..., with_tools=)`.
- `core/config.py`, `server/.env.example` — chat settings.
- `main.py` — pass `finance_toolkit()` to `initialize_agents`.

**Server — conversation module**
- `modules/conversation/finance/` (new feature sub-package): `__init__.py`, `service.py` (toolkit + preamble + history cache), `schemas.py` (tool argument models), `domain/search.py`, `domain/display.py`, `domain/periods.py`.
- `modules/conversation/__init__.py` — re-export `finance_toolkit`.
- `modules/conversation/router/chatbot.py`, `router/conversation.py`, `service.py`, `schemas.py` — turn context, connection release, history schema.
- `server/pyproject.toml` — R10 contract for `app.modules.conversation.finance`.

**Web (`web-app/apps/web/src/`)**
- `lib/chat/stream-chat.ts` — typed events.
- `lib/chat/exchange.ts` — activity in the exchange; history → thread messages with `metadata.custom.activity`.
- `lib/chat/activity.ts` (new) — activity types and the reducer for stream events.
- `components/chat/activity-block.tsx` (new), `components/chat/chat-message.tsx`, `components/chat/copy.ts`.
- `components/chat/chat-runtime-provider.tsx` (+ test) — dispatch new events; failed-create test.

---

### Task 1: Spike — readable reasoning through OpenRouter

Throwaway; no product code, no tests. Its result decides the shape of Task 2's tuned params and Task 4's reasoning handling.

**Files:**
- Create (scratch, not committed): `$SCRATCH/reasoning_spike.py`
- Modify: this plan — fill in **Spike result** below.

- [x] **Step 1: Write a script** that builds `ChatOpenAI(model="openai/gpt-5-mini", base_url=settings.llm.LLM_BASE_URL, api_key=..., reasoning={"effort": "medium", "summary": "auto"}, max_tokens=8000)` (the `reasoning` param already makes langchain-openai use the Responses API), binds one trivial tool, and streams `astream([...])` for a question that needs a tool call and then an answer after a `ToolMessage`.
- [x] **Step 2: Record**, for both the first call and the follow-up after the tool result: whether `AIMessageChunk.content` carries `{"type": "reasoning", "summary": [{"type": "summary_text", "text": ...}]}` blocks with non-empty text, how they arrive as deltas, whether the follow-up call succeeds when the reasoning block from the first call is sent back unchanged, and token usage at `low` vs `medium`.
- [x] **Step 3: Fill in Spike result** below and commit the plan.

**Spike result:** **A** - summaries stream through the current client (langchain-openai 1.6.0, langchain-core 1.6.1) with `reasoning={"effort": "medium", "summary": "auto"}` on a single `ChatOpenAI` instance (no `output_version`, `use_responses_api` or `extra_body` needed; `reasoning` already selects the Responses API). It is a per-instance constructor param, so it stays limited to the chat agent's own `LLMService`; the shared registry is untouched. Chunk shape: `AIMessageChunk.content` is a list; chunk 2 opens `{"type":"reasoning","id":"rs_...","summary":[],"status":"in_progress","index":0}`, then token-sized deltas `{"type":"reasoning","index":0,"summary":[{"index":0,"type":"summary_text","text":" need"}]}` (only the first chunk has `id`; `additional_kwargs` empty, no `reasoning_details`), then text blocks `{"type":"text","text":...,"index":0}` and tool-call chunks. Aggregated content merges into one reasoning block (joined summary text plus opaque `encrypted_content`); `full.content_blocks` gives `{"type":"reasoning","reasoning":<text>}`. Summaries are non-deterministic: at `medium` the first (tool-call) call yielded 75-92 summary deltas, the follow-up usually none (0 reasoning tokens); at `low` none at all (0 reasoning tokens). Round trip: the follow-up succeeds with the first call's reasoning block sent back unchanged and also with it stripped, so Task 4 may drop reasoning blocks from history. Tokens (call 1, medium): input 64, output 117-189, reasoning 64-128 (`usage_metadata.output_token_details.reasoning`); low: output 85, reasoning 0; follow-up: input 114-283, output 15. Do not use `output_version="v1"` (reshapes blocks) or Chat Completions (`use_responses_api=False`: no summaries). Full evidence: `.superpowers/sdd/2026-10-20-chat-finance-tools/task-1-report.md`.

---

### Task 2: Chat LLM settings and a tuned, chat-only `LLMService`

**Files:**
- Modify: `server/app/core/config.py` (`LLMSettings`), `server/.env.example`
- Modify: `server/app/integrations/llm/service.py`
- Test: `server/tests/unit/integrations/llm/test_service.py`

**Interfaces:**
- Produces:
  - `LLMSettings.CHAT_REASONING_EFFORT: Literal["minimal", "low", "medium", "high"] = "medium"`
  - `LLMSettings.CHAT_REPLY_MAX_TOKENS: int = 8000`, `CHAT_HISTORY_MAX_TOKENS: int = 24000`, `CHAT_MAX_STEPS: int = 8` (`MAX_TOKENS` stays for every other caller)
  - `LLMRegistry.get_tuned(model_name: str, *, max_tokens: int, reasoning_effort: str | None) -> BaseChatModel` — the entry's params with `max_tokens` replaced and, **only for entries whose params have `reasoning`**, `reasoning["effort"]` replaced (plus `summary` if Task 1 is A); cached per `(model_name, max_tokens, reasoning_effort)`, separate from `_instances`.
  - `LLMService.__init__(self, *, max_tokens: int | None = None, reasoning_effort: str | None = None)` — when either is set, `_resolve` uses `get_tuned`.
  - `LLMService.call(self, messages, model_name=None, config=None, *, with_tools: bool = True, **model_kwargs)` — `with_tools=False` resolves the client without the bound tools (used by the wrap-up call, Task 4).

- [x] **Step 1: Write the failing tests**

```python
def test_get_tuned_replaces_effort_only_on_reasoning_entries():
    tuned = LLMRegistry.get_tuned("openai/gpt-5-mini", max_tokens=8000, reasoning_effort="medium")
    assert tuned.reasoning["effort"] == "medium" and tuned.max_tokens == 8000
    plain = LLMRegistry.get_tuned("openai/gpt-4o", max_tokens=8000, reasoning_effort="medium")
    assert plain.reasoning is None and plain.max_tokens == 8000

def test_get_tuned_does_not_touch_the_default_instances():
    LLMRegistry.get_tuned("openai/gpt-5-mini", max_tokens=8000, reasoning_effort="high")
    assert LLMRegistry.get("openai/gpt-5-mini").reasoning["effort"] == "low"

def test_a_tuned_service_falls_back_with_the_tuning():  # every model in the chain is built by get_tuned
    ...

@pytest.mark.asyncio
async def test_call_without_tools_uses_an_unbound_client():
    # service.bind_tools([echo]); patch _call_llm_with_retry; call(with_tools=False)
    # assert the llm passed has no bound tools (not a RunnableBinding with "tools" kwargs)
    ...
```

- [x] **Step 2: Run** `cd server && APP_ENV=test uv run pytest tests/unit/integrations/llm/test_service.py -v` — expect the new tests to FAIL.
- [x] **Step 3: Implement** the settings (with `.env.example` comments: effort applies to the chat only; lowering it cuts cost and delay), `get_tuned`, the constructor args and `with_tools`. `with_tools` threads through `_call_with_fallback` to `_resolve`.
- [x] **Step 4: Run** the file again — PASS; then `make test-unit` — PASS.
- [x] **Step 5: Commit** `feat(llm): chat reasoning effort and reply/history budgets as settings`.

---

### Task 3: Toolkit contract and the tool node

**Files:**
- Create: `server/app/agents/chatbot/toolkit.py`, `server/app/agents/chatbot/events.py`
- Modify: `server/app/agents/chatbot/graph.py`
- Delete: `server/app/agents/chatbot/tools/` (and `langchain_community`'s DuckDuckGo use; drop the dependency if nothing else imports it)
- Modify: `server/app/agents/factory.py`
- Test: `server/tests/unit/agents/chatbot/test_graph.py`, `server/tests/unit/agents/chatbot/test_toolkit.py` (new)

**Interfaces:**
- Produces (`toolkit.py`):
  - `@dataclass class TurnContext: user_id: uuid.UUID; session_factory: async_sessionmaker; cache: dict[str, Any] = field(default_factory=dict)` — one per turn; `cache` is scratch for toolkits.
  - `class ToolArgumentError(Exception)` — raised by a tool with a message written **for the model** ("category must be one of …").
  - Display models (Pydantic, `extra="forbid"`): `SummaryItem(kind: Literal["count","money","percent","text"], value: float | int | str, label: str | None = None)`; `TableColumn(key: str, label: str, kind: Literal["text","money","percent","count","date"])`; `ToolTable(columns: list[TableColumn], rows: list[dict[str, str | float | int | None]])`; `ToolDisplay(title: str, period: str | None, summary: list[SummaryItem], table: ToolTable | None)`.
  - `@dataclass class ToolOutcome: content: str; display: ToolDisplay` — `content` goes to the model, `display` to the UI.
  - `@dataclass class AgentTool: name: str; title: str; description: str; args_schema: type[BaseModel]; run: Callable[[BaseModel, TurnContext], Awaitable[ToolOutcome]]` and `def as_schema(self) -> dict` (OpenAI tool schema from `args_schema`, for `bind_tools`).
  - `@dataclass class Toolkit: tools: list[AgentTool]; preamble: Callable[[TurnContext], Awaitable[str]]` and `@classmethod def empty(cls) -> "Toolkit"` (no tools, preamble returns `""`).
- Produces (`events.py`): `TextEvent(type="text", text)`, `ReasoningEvent(type="reasoning", text)`, `ToolStartedEvent(type="tool_started", id, name, title)`, `ToolFinishedEvent(type="tool_finished", id, ok: bool, display: ToolDisplay | None)`, `DoneEvent(type="done", stopped: bool)`, `ErrorEvent(type="error")`; `StreamEvent = Annotated[Union[...], Field(discriminator="type")]`.
- Produces (`graph.py`): `ChatbotAgent.__init__(self, toolkit: Toolkit | None = None)`; the turn context is read from `config["configurable"]["turn_context"]`; `ToolMessage.artifact` holds `ToolDisplay.model_dump()` on success.
- Produces (`factory.py`): `initialize_agents(checkpointer, toolkits: Mapping[str, Toolkit] | None = None)` — passes `toolkit=toolkits[name]` when present.

- [x] **Step 1: Write the failing tests** (replace the web-search-specific tests; keep the unknown-tool and crash tests)

```python
async def test_invalid_arguments_return_the_validation_message(agent_with(tool_taking_int)):
    msg = await agent._invoke_tool({"name": "t", "args": {"n": "x"}, "id": "c1"}, ctx)
    assert msg.status == "error" and "n" in msg.content and msg.content != TOOL_FAILED_MESSAGE

async def test_tool_argument_error_text_reaches_the_model():
    # tool raises ToolArgumentError("no data before 2025-03-01")
    assert msg.content == "no data before 2025-03-01" and msg.status == "error"

async def test_crash_still_returns_the_fixed_message():  # RuntimeError("db down")
    assert msg.content == TOOL_FAILED_MESSAGE and "db down" not in msg.content

async def test_success_carries_the_display_as_artifact():
    assert msg.content == outcome.content and msg.artifact == outcome.display.model_dump()

async def test_tool_calls_run_concurrently_and_one_crash_does_not_sink_the_other():
    # two tools awaiting an asyncio.Event set only when both have started → completes, no deadlock
    # one raises: results ordered as the calls, one TOOL_FAILED_MESSAGE, one success

async def test_tool_node_emits_started_and_finished_events():
    # patch get_stream_writer; assert ToolStartedEvent(id, name, title) then ToolFinishedEvent(id, ok, display)

def test_no_web_search_tool_is_bound():
    assert "duckduckgo" not in str(ChatbotAgent().llm_service._tools)
```

- [x] **Step 2: Run** `APP_ENV=test uv run pytest tests/unit/agents/chatbot -v` — FAIL.
- [x] **Step 3: Implement.** `ChatbotAgent` owns its own `LLMService(max_tokens=settings.llm.CHAT_REPLY_MAX_TOKENS, reasoning_effort=settings.llm.CHAT_REASONING_EFFORT)` (no longer the shared `llm_service` singleton) and binds `[t.as_schema() for t in toolkit.tools]`. `_invoke_tool(tool_call, ctx)` validates with `args_schema.model_validate` (a `ValidationError` → its errors rendered compactly, status `error`, outcome label `invalid_args`), then `run`; `ToolArgumentError` → its message; any other exception → `TOOL_FAILED_MESSAGE` as today. `_tool_call(state, config)` runs all calls with `asyncio.gather` and emits events through `langgraph.config.get_stream_writer()`. Keep metrics/logging per call. Run each `run` through `RunnableLambda(...).ainvoke(args, config={**config, "run_name": tool.name})` so the graph's Langfuse callback records a span per tool call with its arguments and result (§10; the eval ticket's raw material). Update `test_graph.py`'s fixture to `ChatbotAgent(Toolkit.empty())`, and `title.py`'s docstring that mentions `llm_service`.
- [x] **Step 4: Run** the chatbot tests and `make test-unit` — PASS.
- [x] **Step 5: Commit** `feat(agents): toolkit contract, validated and parallel tool calls; remove web search`.

---

### Task 4: Turn limits, wrap-up, stopped flag, reasoning kept

**Files:**
- Modify: `server/app/agents/chatbot/state.py`, `server/app/agents/chatbot/graph.py`, `server/app/agents/graph.py` (`process_llm_response`)
- Test: `server/tests/unit/agents/chatbot/test_graph.py`, `server/tests/unit/agents/test_graph_process_response.py` (new or existing file for it)

**Interfaces:**
- Consumes: `LLMService.call(..., with_tools=False)` (Task 2); `CHAT_MAX_STEPS`.
- Produces:
  - `GraphState.turn_steps: int = 0` (the turn's input sets it to `0`), `GraphState.stopped: dict[str, str] = {}` — final AIMessage id → `"step_limit" | "repeated_call"`; checkpointed.
  - `def repeated_call(messages: list[BaseMessage]) -> bool` in `graph.py` — true when the last AIMessage repeats a `(name, args)` pair already called since the last `HumanMessage`.
  - `WRAP_UP_INSTRUCTION: str` — appended as a system message for the tool-less final call ("Tools are no longer available this turn; answer from the results above and say the answer may be incomplete").
  - `STOPPED_FALLBACK_TEXT: str` — used if the wrap-up call itself fails.
  - `process_llm_response` keeps `reasoning` blocks in `content` (Spike A/B); `.text` remains the answer text. Spike C: unchanged.

- [ ] **Step 1: Write the failing tests**

```python
async def test_step_cap_ends_the_turn_with_a_wrap_up_answer_marked_stopped():
    # model mock always returns a tool call; CHAT_MAX_STEPS=2 (monkeypatch)
    # run graph (MemorySaver); assert last AIMessage has no tool_calls,
    # state.stopped[last.id] == "step_limit", and the last call used with_tools=False

async def test_repeated_identical_call_stops_the_loop():
    # model returns the same (name, args) twice → stopped == "repeated_call", tool ran once

async def test_a_failing_wrap_up_falls_back_to_the_fixed_text():
    assert last.content == STOPPED_FALLBACK_TEXT

async def test_turn_steps_reset_on_each_turn():
    # two turns in one thread; the second is not stopped early by the first's count

def test_reasoning_blocks_survive_processing():  # Spike A/B only
    msg = AIMessage(content=[{"type": "reasoning", "summary": [{"type": "summary_text", "text": "t"}]},
                             {"type": "text", "text": "answer"}])
    out = process_llm_response(msg)
    assert out.text == "answer" and any(b["type"] == "reasoning" for b in out.content)
```

Keep `test_chat_does_not_send_a_tool_call_left_without_a_result` green (Review Focus 1).

- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement.** Route in `_chat`: after a model response with tool calls, if `turn_steps + 1 >= CHAT_MAX_STEPS` or `repeated_call(...)`, do not go to `tool_call`; drop that response's tool calls and make the wrap-up call (`with_tools=False`), record `stopped[id]`. The answering model is read from `response.response_metadata.get("model_name")` for the `llm_inference_duration_seconds` label and the `llm_response_generated` log (closes TODO *names the default model*); time with `time.perf_counter()` and `.observe()` since the label is known only after.
- [ ] **Step 4: Run** — PASS; `make test-unit` — PASS.
- [ ] **Step 5: Commit** `feat(agents): per-turn step cap and repeat detection end in a stopped answer`.

---

### Task 5: Model context — current turn intact, old tool results stubbed, static prompt prefix

**Files:**
- Create: `server/app/agents/chatbot/context.py`
- Modify: `server/app/agents/chatbot/prompts/system.md`, `server/app/agents/chatbot/prompts/__init__.py`, `server/app/agents/chatbot/graph.py`, `server/app/agents/graph.py` (remove `prepare_messages`)
- Test: `server/tests/unit/agents/chatbot/test_context.py` (new); remove/replace `tests/unit/agents/test_graph_prepare_messages.py`

**Interfaces:**
- Consumes: `CHAT_HISTORY_MAX_TOKENS`; `Toolkit.preamble` (Task 3).
- Produces:
  - `STUB_TEMPLATE = "{title}{period}: result omitted from an earlier turn; call the tool again for figures."`
  - `def build_model_context(messages: list[BaseMessage], *, system_prompt: str, turn_context_text: str, budget_tokens: int, count_tokens: Callable[[list[BaseMessage]], int]) -> list[BaseMessage]` — returns `[SystemMessage(system_prompt), *earlier_turns_trimmed_and_stubbed, SystemMessage(turn_context_text), *current_turn]`; applies `drop_unanswered_tool_calls` first; never trims the current turn (last `HumanMessage` onward); stubs every earlier `ToolMessage` using its `artifact` title/period; drops whole earlier turns oldest-first until under budget.
  - `def estimate_tokens(messages: list[BaseMessage]) -> int` — chars/4 over text and reasoning text; used when the model's counter raises (today's "skip trimming" fallback is removed).
  - `load_system_prompt() -> str` — the static prompt, no date or memory.
  - `render_turn_context(*, today: dt.date, memory: str, preamble: str) -> str` — date, the toolkit's preamble (last finished month, data span), memory.

- [ ] **Step 1: Write the failing tests**

```python
def test_current_turn_is_never_trimmed_even_over_budget():
    out = build_model_context(history_with_huge_current_tool_result, budget_tokens=10, ...)
    assert out[-len(current_turn):] == current_turn

def test_earlier_tool_results_become_stubs():
    stub = next(m for m in out if isinstance(m, ToolMessage))
    assert stub.content == "Spending by category · Sep 2026: result omitted from an earlier turn; call the tool again for figures."
    assert stub.tool_call_id == original.tool_call_id

def test_oldest_turns_drop_first_and_tool_pairs_stay_whole():
    # no ToolMessage without its AIMessage tool call in the output

def test_static_prompt_comes_first_and_turn_context_after_history():
    assert out[0].content == load_system_prompt() and isinstance(out[-len(current_turn)-1], SystemMessage)

def test_system_prompt_has_no_date_or_memory_placeholders():
    assert "{" not in load_system_prompt()
```

- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Write `system.md`** as a personal-finance assistant per §4 and §1: figures only from this turn's tools; name the period; say plainly when data cannot answer; advice must cite the user's numbers; general knowledge is not a figure about the user; savings rate is the analytics one, show Savings & Investments beside it when investing comes up and explain why it lowers the rate; no transactions → point to CSV import; never compute an adjusted rate or add up rows. Then implement `context.py` and switch `_chat` to it (`count_tokens` = the client's `get_num_tokens_from_messages`, falling back to `estimate_tokens` on error).
- [ ] **Step 4: Run** — PASS; `make test-unit` — PASS.
- [ ] **Step 5: Commit** `feat(agents): model context keeps the current turn and stubs old tool results`.

---

### Task 6: Finance toolkit — history cache, preamble, the six analytics tools

**Files:**
- Create: `server/app/modules/conversation/finance/__init__.py`, `service.py`, `schemas.py`, `domain/__init__.py`, `domain/periods.py`, `domain/display.py`
- Modify: `server/app/modules/conversation/__init__.py` (re-export `finance_toolkit`), `server/pyproject.toml` (R10 contract: sources = conversation core slots, forbidden = `app.modules.conversation.finance`)
- Test: `server/tests/unit/modules/conversation/finance/test_periods.py`, `test_display.py`, `server/tests/integration/modules/conversation/finance/test_service.py`

**Interfaces:**
- Consumes: `Toolkit`, `AgentTool`, `TurnContext`, `ToolOutcome`, `ToolDisplay`, `ToolArgumentError` (Task 3); `analytics_service.history(session, user_id) -> AnalyticsHistory`, `AnalyticsHistory.spending/categories/merchants/recurring/behaviour/anomalies/period`, `DateRange` (from `app.modules.analytics`); `CATEGORIES`, `MIN_DATE`, `MAX_DATE` (from `app.modules.transaction`).
- Produces:
  - `async def turn_history(ctx: TurnContext) -> AnalyticsHistory` — loads once per turn into `ctx.cache["history"]` with `async with ctx.session_factory() as session`.
  - `class PeriodArgs(BaseModel)`: `months: int | None = Field(None, ge=1, le=120)`, `date_from: dt.date | None`, `date_to: dt.date | None` — exactly one of `months` or a date bound; base of every analytics tool's args.
  - `def to_date_range(args: PeriodArgs, history: AnalyticsHistory) -> DateRange` — raises `ToolArgumentError` naming the data span when the range is invalid or holds no data (Review Focus 4).
  - `def period_label(history: AnalyticsHistory, date_range: DateRange) -> str` — named as the analytics page names it ("September 2026", "Jul – Sep 2026"; "so far" for the month in progress).
  - Tool names, titles, args, wraps (top-N caps are constants in `service.py`):

    | name | title | args (beyond `PeriodArgs`) | wraps |
    |---|---|---|---|
    | `spending_overview` | Spending overview | — | `history.spending(range)` |
    | `category_breakdown` | Spending by category | — (`top_n=CATEGORY_TOP_N`) | `history.categories(range, top_n)` |
    | `top_merchants` | Top merchants | `top_n: int = Field(10, ge=1, le=15)` | `history.merchants(range, top_n)` |
    | `recurring_costs` | Recurring costs | — | `history.recurring(range)` |
    | `spending_behaviour` | Spending patterns | — | `history.behaviour(range)` |
    | `unusual_spending` | Unusual spending | — (analytics router defaults) | `history.anomalies(range, std, days)` |

  - `domain/display.py`: one pure `def <tool>_outcome(response, label: str) -> ToolOutcome` per tool — `content` is compact text for the model (period first, then the figures, money as plain decimals with "EUR"), `display` carries `title`, `period=label`, `summary` items and a `ToolTable` (money as numbers).
  - `async def preamble(ctx: TurnContext) -> str` — "Last finished month: …; data covers … to …" or "The user has no transactions yet." (Review Focus 3).
  - `def finance_toolkit() -> Toolkit`.

- [ ] **Step 1: Write the failing tests**

```python
def test_months_and_dates_together_are_rejected():  # pydantic ValidationError
def test_range_before_the_data_names_the_span():
    with pytest.raises(ToolArgumentError, match="data covers"): to_date_range(PeriodArgs(date_from=..2019..), history)
def test_period_label_matches_the_analytics_naming():
    assert period_label(history, DateRange(months=1)) == "September 2026"
def test_category_outcome_is_bounded_and_names_the_period():
    out = category_breakdown_outcome(response_with_14_categories, "Sep 2026")
    assert out.content.startswith("Sep 2026") and out.display.summary[0] == SummaryItem(kind="count", value=14, label="categories")
    assert all(isinstance(r["total"], float) for r in out.display.table.rows)
# integration, seeded user (reuse seed helpers from tests/integration/modules/analytics):
async def test_history_loads_once_per_turn():  # patch analytics_service.history, call two tools, assert one call
async def test_tools_read_only_the_context_user():  # rows for users A and B; ctx A → no B merchant appears
async def test_figures_match_the_analytics_route():  # spending_overview total == GET /analytics/spending total
async def test_preamble_without_transactions_says_so():
```

- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement.** Tool descriptions say when to use and when not (e.g. category_breakdown: "not for a single merchant — use search_transactions"). Add the R10 contract and run `cd server && uv run lint-imports`.
- [ ] **Step 4: Run** the new tests, `make test-unit`, `make test-integration`, `lint-imports` — PASS.
- [ ] **Step 5: Commit** `feat(conversation): finance toolkit over the analytics history`.

---

### Task 7: `search_transactions`

Deviation from spec §10, decided while planning: the search filters **`history.rows`** (the same usable `AnalysisRow`s the turn already loaded) in memory instead of a new `transaction_service` read. Same rows analytics uses, no second query, no new repository method.

**Files:**
- Create: `server/app/modules/conversation/finance/domain/search.py`
- Modify: `finance/schemas.py`, `finance/service.py`, `finance/domain/display.py`
- Test: `server/tests/unit/modules/conversation/finance/test_search.py`

**Interfaces:**
- Consumes: `AnalysisRow` (`date, merchant, amount, category, is_recurring`) and `Category` from `app.modules.transaction`; `turn_history` (Task 6).
- Produces:
  - `class SearchArgs(BaseModel)`: `merchant: str | None` (substring, case-insensitive), `date_from/date_to: dt.date | None`, `categories: list[Category] | None` (the enum), `amount_min/amount_max: Decimal | None` (signed), `recurring_only: bool = False`, `weekdays: list[Literal["mon","tue","wed","thu","fri","sat","sun"]] | None`, `group_by: Literal["month","merchant","category","weekday"] | None`, `sample: Literal["largest","recent"] = "largest"`.
  - `SAMPLE_SIZE = 20`, `GROUP_LIMIT = 24`.
  - `@dataclass class Totals: count: int; total: Decimal` ; `@dataclass class SearchResult: money_out: Totals; money_in: Totals; groups: list[tuple[str, Totals, Totals]]; sample: list[AnalysisRow]; matched: int`.
  - `def search_rows(rows: Sequence[AnalysisRow], args: SearchArgs) -> SearchResult` — pure; `money_out` = negative amounts, `money_in` = positive, never netted; groups sorted by money-out total; `sample` largest by absolute amount or most recent.
  - `def search_outcome(result: SearchResult, args: SearchArgs) -> ToolOutcome` in `display.py`.

- [ ] **Step 1: Write the failing tests**

```python
def test_merchant_match_is_case_insensitive_substring(): assert search_rows(rows, SearchArgs(merchant="lidl")).matched == 3
def test_weekday_filter(): # only Tuesday rows counted
def test_money_in_and_out_are_never_netted():
    r = search_rows([row(-50), row(+20)], SearchArgs()); assert (r.money_out.total, r.money_in.total) == (Decimal("-50"), Decimal("20"))
def test_sample_is_capped(): assert len(search_rows(rows_100, SearchArgs()).sample) == 20
def test_group_by_month_sums_per_month():
def test_unknown_category_is_a_validation_error(): with pytest.raises(ValidationError): SearchArgs(categories=["Snacks"])
def test_no_match_says_so_in_content(): assert "no transactions match" in search_outcome(empty, args).content
```

- [ ] **Step 2: Run** — FAIL. **Step 3: Implement** and register the tool (title "Transaction search"). **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** `feat(conversation): search_transactions with server-side totals`.

---

### Task 8: Wire contract — typed stream and history with activity

**Files:**
- Modify: `server/app/agents/messages.py`, `server/app/agents/base/agent.py`, `server/app/modules/conversation/schemas.py`, `server/app/modules/conversation/router/chatbot.py`
- Regenerate: `server/openapi.json`, `web-app/packages/api-client/src/generated/` (`make gen-contract`)
- Test: `server/tests/unit/agents/test_base_agent.py`, `server/tests/integration/modules/conversation/router/test_chatbot.py`

**Interfaces:**
- Consumes: events (Task 3), `GraphState.stopped` (Task 4), `ToolMessage.artifact` (Task 3).
- Produces (`messages.py`): `ReasoningPart(type="reasoning", text)`, `ToolPart(type="tool", id, name, ok: bool, display: ToolDisplay | None)`, `Activity(parts: list[ReasoningPart | ToolPart], stopped: bool = False)`, `ChatMessage(role: Literal["user","assistant"], content: str, activity: Activity | None = None)`.
- Produces (`base/agent.py`):
  - `get_stream_response(messages, conversation_id, turn_context: TurnContext) -> AsyncGenerator[StreamEvent, None]` — `stream_mode=["messages","custom"]`; AIMessage text → `TextEvent`; reasoning summary deltas → `ReasoningEvent` (Spike A/B); custom chunks are already events; ends with `DoneEvent(stopped=...)`. The turn context goes in `config["configurable"]["turn_context"]`; `user_id` comes from it.
  - `get_response(messages, conversation_id, turn_context) -> list[ChatMessage]`.
  - `get_chat_history(conversation_id) -> list[ChatMessage]` — a turn's AIMessages and ToolMessages fold into one assistant `ChatMessage` whose `activity` lists reasoning and tool parts in order and `stopped` from `state.stopped`; **a turn with no final assistant text yields no assistant message and no activity** (§7, user stop).
  - `conversation/schemas.py`: `ConversationHistory.messages: list[ChatMessage]`; `ChatResponse.message: ChatMessage`; `StreamResponse` removed.

- [ ] **Step 1: Write the failing tests**

```python
def test_history_folds_a_turn_into_one_message_with_activity():
    # Human, AI(tool_calls=[c1]), Tool(c1, artifact=display), AI("answer")
    [user, reply] = agent._process_messages(msgs, stopped={})
    assert reply.content == "answer" and reply.activity.parts[0].display.title == "Spending by category"

def test_history_drops_the_activity_of_an_unanswered_turn():  # Review Focus 1
    # Human, AI(tool_calls=[c1]), Tool(c1)  — no final text
    assert [m.role for m in agent._process_messages(msgs, stopped={})] == ["user"]

def test_history_marks_server_stopped_turns(): assert reply.activity.stopped is True

# integration (router):
async def test_stream_emits_typed_events_ending_in_done():
    # mock agent yields ToolStartedEvent, ToolFinishedEvent, TextEvent, DoneEvent
    assert [e["type"] for e in events] == ["tool_started", "tool_finished", "text", "done"]
async def test_stream_failure_is_an_error_event_without_server_text():
async def test_history_response_carries_activity():
```

Replace `test_events_are_byte_identical` and `test_failure_is_a_final_event_with_content` (the old shape is gone on purpose); keep `test_disconnect_cancels_the_agent_stream`.

- [ ] **Step 2: Run** — FAIL. **Step 3: Implement**; run `make gen-contract` from the repo root. **Step 4: Run** server tests, `make check-contract` — PASS.
- [ ] **Step 5: Commit** (route, schemas, `openapi.json`, generated client together) `feat(chat): typed stream events and history with activity`.

---

### Task 9: Routes — turn context, connection release, injection at startup, memory

**Files:**
- Modify: `server/app/modules/conversation/router/chatbot.py`, `router/conversation.py`, `service.py`
- Modify: `server/app/main.py`
- Modify: `server/app/agents/base/agent.py` (memory call), `server/app/agents/shared/memory/factory.py`
- Test: `server/tests/integration/modules/conversation/router/test_chatbot.py`, `test_conversation.py`; `server/tests/unit/agents/test_base_agent.py`; `server/tests/unit/agents/memory/` (existing dir)

**Interfaces:**
- Consumes: `TurnContext` (Task 3), `finance_toolkit()` (Task 6), `initialize_agents(checkpointer, toolkits)` (Task 3).
- Produces:
  - `async def release_connection(session: AsyncSession) -> None` in `conversation/service.py` (same body and docstring reasoning as `insights/service.py::_release_connection`).
  - Chat and stream routes: after `UserConversation` resolves, `await release_connection(db_session)`, then `TurnContext(user_id=user.id, session_factory=request.app.state.session_factory)`. Title route: release before `agent.title_for`, write after (the session opens a new transaction; `DbSession` commits it).
  - `main.py`: `initialize_agents(checkpointer, {"chatbot": finance_toolkit()})`.
  - `MEMORY_INSTRUCTIONS: str` in `memory/factory.py`, passed as mem0 `custom_instructions` — keep goals, circumstances, preferences; drop amounts, balances, dates of activity, anything describing a period's spending.
  - `BaseAgent` calls `update_memory(user_id, [{"role": "user", "content": messages[-1].content}], metadata)` — this turn's user message only.

- [ ] **Step 1: Write the failing tests**

```python
async def test_chat_releases_the_connection_before_the_model_call():
    # mock agent's get_stream_response asserts db_session.in_transaction() is False when first awaited
async def test_title_releases_before_the_model_and_still_saves():
async def test_the_turn_context_carries_the_signed_in_user():
    assert mock_agent.get_stream_response.call_args.kwargs["turn_context"].user_id == test_user.id
async def test_memory_receives_only_this_turns_user_message():
    # patch update_memory; run get_response with tool messages in state
    assert sent == [{"role": "user", "content": "how much on food?"}]
def test_memory_config_carries_the_instructions():
    assert config["custom_instructions"] == MEMORY_INSTRUCTIONS
```

- [ ] **Step 2: Run** — FAIL. **Step 3: Implement.** Update the `mock_agent` fixture (`tests/integration/conftest.py`) to the new signatures. **Step 4: Run** `make test` — PASS.
- [ ] **Step 5: Commit** `feat(chat): release the request connection before model calls; inject the finance toolkit; memory from user messages only`.

---

### Task 10: Web — stream events and the exchange's activity

**Files:**
- Create: `web-app/apps/web/src/lib/chat/activity.ts`, `activity.test.ts`
- Modify: `web-app/apps/web/src/lib/chat/stream-chat.ts` (+ test), `exchange.ts` (+ test), `components/chat/chat-runtime-provider.tsx`

**Interfaces:**
- Consumes: the server's event shapes (Task 8) and generated `ChatMessage`/`Activity` types (`@app/api-client/types`).
- Produces:
  - `stream-chat.ts`: a zod discriminated union mirroring `app/agents/chatbot/events.py` (still hand-written: streaming routes are not generated); `streamChat(...)` now `AsyncGenerator<StreamEvent>`; `type: "error"` → throw `StreamFailedError`; a stream ending without `done` → throw as today.
  - `activity.ts`: `type ActivityState = { parts: ActivityPart[]; startedAt: number; endedAt: number | null; stopped: boolean; answerStarted: boolean }`, `ActivityPart = { kind: "reasoning"; text: string } | { kind: "tool"; id: string; name: string; title: string; status: "running" | "ok" | "error"; display: ToolDisplay | null }`; `function activityReducer(state: ActivityState, event: StreamEvent, now: number): ActivityState` (consecutive reasoning deltas append to the last reasoning part); `function fromHistory(activity: Activity): ActivityState` (`startedAt`/`endedAt` null-safe: no timing); `function currentLabel(state): string` ("Thinking…" or "Looking up <title lowercased>…").
  - `exchange.ts`: `Exchange.activity: ActivityState`; actions `{ type: "event"; send; event: StreamEvent; now: number }` replacing `chunk`; `toThreadMessages` sets `metadata: { custom: { activity } }` on assistant messages, from history (`fromHistory`) and in flight.

- [ ] **Step 1: Write the failing tests**

```ts
it("appends reasoning deltas into one part", ...)
it("marks a tool ok with its display on tool_finished", ...)
it("sets answerStarted on the first text event", ...)          // drives the auto-collapse
it("keeps stopped from done", ...)
it("throws StreamFailedError on an error event", ...)
it("puts history activity in metadata.custom.activity", ...)
```

- [ ] **Step 2: Run** `make test-web` — FAIL. **Step 3: Implement.** **Step 4: Run** `make test-web` and `make check-web` — PASS.
- [ ] **Step 5: Commit** `feat(web): typed chat stream and activity state`.

---

### Task 11: Web — the activity block

**Files:**
- Create: `web-app/apps/web/src/components/chat/activity-block.tsx`, `activity-block.test.tsx`
- Modify: `components/chat/chat-message.tsx` (render `<ActivityBlock />` above `MessagePrimitive.Parts` when `metadata.custom.activity` exists), `components/chat/copy.ts`

**Interfaces:**
- Consumes: `ActivityState`, `currentLabel` (Task 10); `formatAmount` for `money`; Finsight tokens and existing primitives (Collapsible from `packages/ui` if present, else add via the `web-app-patterns` route); `useAuiState((s) => s.message.metadata.custom.activity)`.
- Produces: `ActivityBlock({ activity }: { activity: ActivityState })`. Copy constants in `copy.ts`: `thinking: "Thinking…"`, `lookingUp: (title) => \`Looking up ${title}…\``, `workedFor: (s, n) => \`Worked for ${s}s · ${n} lookup${n === 1 ? "" : "s"}\``, `lookups: (n) => …` (history, no timing), `stoppedAfter: (s) => \`Stopped after ${s}s\``, `stoppedLookups: (n) => \`Stopped · ${n} lookups\``, `toolTag: "tool"`.

Behaviour (§7, mockup `.superpowers/brainstorm/24640-1792489429/content/agent-activity-v2.html`): open while running with a shimmer label and a `m:ss` timer ticking once a second; collapses itself when `answerStarted`; header toggles; each tool row toggles a table (money via `formatAmount`, percent with `%`); reasoning rows muted italic; no block when there are no parts.

- [ ] **Step 1: Write the failing tests**

```tsx
it("shows the current step and a running timer while working", ...)   // vi.useFakeTimers; "0:03"
it("collapses to 'Worked for 4s · 2 lookups' once the answer starts", ...)
it("opens a tool row to a table with formatted money", ...)
it("reads 'Stopped after 3s' for a stopped exchange", ...)
it("from history reads '2 lookups' with no timer", ...)
it("renders tool rows only when there is no reasoning", ...)
it("renders nothing without parts", ...)
```

- [ ] **Step 2: Run** — FAIL. **Step 3: Implement.** **Step 4: Run** `make test-web`, `make check-web` — PASS.
- [ ] **Step 5: Commit** `feat(web): activity block for the assistant's thinking and tool calls`.

---

### Task 12: Web — failed conversation create test (TODO)

**Files:**
- Test: `web-app/apps/web/src/components/chat/chat-runtime-provider.test.tsx`

- [ ] **Step 1: Write the test** `it("clears the exchange and returns the text to the composer when create answers 500")` — mock `useCreateConversation` to reject with `new ApiError(500, …)`; send "hello" from `/chat`; assert no in-flight messages render and the composer's value is `"hello"`.
- [ ] **Step 2: Run** `make test-web` — it should PASS against the existing `ensureConversation` behaviour; if it fails, the behaviour regressed: fix `ensureConversation`, not the test.
- [ ] **Step 3: Commit** `test(web): a failed conversation create returns the text to the composer`.

---

### Task 13: Docs, TODOs, manual check

**Files:**
- Modify: `docs/product/features/chat.md`, `docs/architecture/server.md` (toolkit injection; the finance feature sub-package and its R10 contract), `server/CLAUDE.md` (**Agent Architecture**: toolkits, `TurnContext`), `docs/TODO.md`, `docs/ROADMAP.md`
- Delete (in the PR that completes the step): this plan and the spec

- [ ] **Step 1: Manual check** on a seeded account (memory *browser-sign-in-clerk-impersonate*; `seed-transactions`): ask "where did my money go last month?", "how much at Lidl on Tuesdays?", "how can I improve my savings rate?", a 2019 question, then stop mid-reply and resend. Confirm figures match the dashboard/analytics page, the block behaves per §7, and the stopped turn reopens bare.
- [ ] **Step 2: Update `chat.md`** per spec §14 (what the user can do; rules: figures from tools, period naming, savings rate, memory scope, web search removed, limits, reasoning-effort setting and the spike outcome; close the open questions "wire the finance tools?" and "web search?", update "scope of memory").
- [ ] **Step 3: Update `TODO.md`**: delete *a model call holds the request's DB connection*, *the chatbot names the default model after a fallback*, and the *failed conversation create* bullet; add *Chat — conversation summaries* and, if Spike C, *Chat — show the model's thinking*.
- [ ] **Step 4: `ROADMAP.md`**: row 7 → `complete — PR #…`; add the evaluation step with the `roadmap-planner` skill.
- [ ] **Step 5: Run** `make check` and `make test` — PASS. **Commit** `docs: chat finance tools`; delete spec and plan in the final commit of the PR.
