# 7b Agent core — design

**Roadmap row:** 7b Agent core · **Branch:** `refactor/agent-core` (from `template-base`)
**Brainstormed:** 21 Oct 2026 · **Architecture:** [`docs/architecture/server.md`](../../docs/architecture/server.md) §1
(the agent layer) · **Feature doc:** [`docs/product/features/chat.md`](../../docs/product/features/chat.md) §4
· **Data model:** [`docs/data-model/conversation.md`](../../docs/data-model/conversation.md) (no schema change)
**Closes (TODO.md):** *Server — the agent layer imports the chatbot's stream contract* · *Chat — conversation
summaries* · three bullets of *Chat — code review leftovers* (the untyped `TurnContext.cache`, the double tool
lookup, the two reasoning paragraphs running together)

Decisions are marked **(user)** when Tiziano made them in the brainstorm, **(call)** when they were made for
him and he has not ruled on them. Everything unmarked follows from the codebase or the library as it is.

---

## 1. Intent

Step 7 shipped a chat agent whose loop is written by hand: its own tool contract, its own tool node, its own
context trimming, its own fallback-and-retry service, and a base class whose one subclass is the chatbot.
Everything it hand-rolls, LangChain 1.3 and LangGraph 1.0 now ship: `create_agent`, `StructuredTool`,
`ToolRuntime`, `ToolNode`, middleware hooks for every point the loop customises, `with_fallbacks`,
`with_structured_output`, and the standard content-block API. The code was written against the pre-1.0
library, where none of that existed; the reasons for hand-rolling no longer hold.

The step rebuilds every LLM caller on the library **(user)**: the chat agent, the three one-call agents
(CSV mapping, the labeller, insights) and the LLM integration under them. It changes what the code is made
of, not what it does: the web app, the stream, the history endpoint, the tool results and the metrics are
the same before and after.

**What it buys.** Adding a tool is writing one function and adding it to one list **(user)**. Adding an
agent is a new folder under `agents/` with a graph and a prompt, importing a shared core that knows nothing
about any one agent. The generic layer no longer imports one agent's package, which is what blocked a
second agent (TODO *the agent layer imports the chatbot's stream contract*). The next agent in mind is a
financial analyst that writes and runs code in a sandbox over the user's rows; this step does not build it,
but leaves the shape it needs (§3).

## 2. Goals, non-goals, anti-goals

**Goals**
1. The chat loop is `create_agent` plus middleware; the tools are `StructuredTool`s; the per-turn context
   is the graph's typed context, injected into tools by the library.
2. `agents/` has a `core/` every agent shares and one package per agent; nothing in `core/` or in the
   agents layer imports a module (R2 stands **(user)**).
3. The chat's wire types (stream events, history shape, tool display) are owned by `conversation`.
4. `integrations/llm` is a model factory, fallbacks and the exception translation; the `LLMService`
   class and the model registry go. The model lineup is the gpt-5 family only **(user)**.
5. The one-call agents use `with_structured_output`.
6. A long conversation keeps its thread: older turns are summarised rather than forgotten **(user)**,
   and a reopened conversation still shows its whole transcript **(user)**.
7. The TODO entries listed in the header are closed by the change, not by a note.

**Non-goals**
- The analyst subagent, the sandbox, and any new tool. The step adds no capability the user can see.
- Replacing mem0. Long-term memory stays as it is: the library's store does not extract and consolidate
  facts, which is what mem0 is for. **(call)**
- Any web change. The generated client, the SSE frames and the activity block are untouched.
- Evaluation (step 9) and anything it needs beyond stable Langfuse spans.
- Renaming the `agents/` package. Its three one-call "agents" are single structured calls, which the
  package docstring says; the name stays.

**Anti-goals — failure even if it technically works**
- A visible change in the chat: a frame the web does not expect, a history that renders differently, a
  tool result with different figures or wording, a different error text reaching the model or the user.
- A figure reaching the model from anywhere but a tool call made this turn — in particular from a summary
  of earlier turns (§7).
- The agents layer importing a module, or a module importing deeper than another's package root.
- A model lineup that depends on which environment the server runs in.

## 3. Target layout

```
app/agents/
  __init__.py              # docstring only: the layer, its rule (R2), what each package is
  core/
    __init__.py            # re-exports the functions below
    checkpointing.py       # create_postgres_saver, the pool, delete_conversation(s)_checkpoints  (today shared/checkpointing/postgres.py)
    memory.py              # mem0: create_memory, get_relevant_memory, update_memory, delete_user_memory  (today shared/memory/factory.py)
    observability.py       # create_graph_config, create_trace_config  (today shared/observability/langfuse.py)
    structured.py          # ask(): a structured one-shot call over the model factory (§10)
    messages.py            # drop_unanswered_tool_calls, and nothing else that survives
  chatbot/
    __init__.py            # build_chatbot, ChatbotAgent, TurnContext
    agent.py               # ChatbotAgent: holds the compiled graph; run, stream, state, title_for (§4.5)
    graph.py               # build_chatbot(): create_agent with the middleware stack (§4)
    context.py             # TurnContext, the context_schema (§5.2)
    state.py               # ChatState(AgentState): long_term_memory, stopped, summary, summary_through
    middleware/
      turn_bound.py        # step cap, repeat detection, wrap-up (§4.3)
      request_shaping.py   # drop unanswered calls, strip earlier reasoning, stub earlier tool results, append the turn context (§4.3)
      summary.py           # the own summariser (§7)
      memory.py            # before_agent fetch, after_agent write (§8)
      tool_events.py       # ToolCallStarted/Finished on the custom stream, metrics, error texts (§4.4)
    prompts/               # system.md, summary.md
    title.py               # unchanged in substance; uses the model factory
  csv_mapping/ transaction_labeler/ insights/   # unchanged layout; call core.structured.ask (§10)

app/modules/conversation/
  tools/                   # today finance/: the chat's tools, one place (§5)
    __init__.py            # chat_tools(): list[BaseTool], and preamble
    analytics.py           # PeriodArgs, TopMerchantsArgs, and the six analytics tools, declared in one list
    search.py              # SearchArgs, the pure filter (today domain/search.py) and the search tool
    display.py             # the renderers and their shared helpers: today's file, unchanged
    periods.py             # period naming (today domain/periods.py), resolve_period, the preamble, the per-turn history cache
  schemas.py               # + ChatMessage, Activity, parts; ToolDisplay family; the stream events (§6)
  domain/chat.py           # pure: history from checkpoint messages; stream events from the graph's stream (§6)
  router/chatbot.py        # builds TurnContext, runs the agent, translates through domain/chat.py

app/integrations/llm/
  __init__.py              # chat_model, with_fallbacks, the exceptions
  models.py                # the factory and the fallback chain (§9)
  exceptions.py            # unchanged
```

What goes: `agents/base/`, `agents/shared/`, `agents/factory.py`, `agents/graph.py` (its surviving
function moves to `core/messages.py`), `agents/messages.py`, `agents/chatbot/toolkit.py`,
`agents/chatbot/events.py`, `agents/chatbot/context.py`'s trimming code, `integrations/llm/service.py`.
`account/service.py` and `conversation/handlers.py` re-point their `core` imports.

A second agent gets its own folder beside `chatbot/`, importing `core/` and the library. Its tools, if it
has any, live in the module that owns the data they read, as the chat's do. The analyst's sandbox client
would be an integration. **(user: the shape; call: the sandbox as an integration)**

## 4. The chat agent

### 4.1 The graph

`build_chatbot(checkpointer, tools, preamble, *, model=None)` returns `create_agent(model, tools,
system_prompt=…, middleware=[…], state_schema=ChatState, context_schema=TurnContext,
checkpointer=checkpointer, name=…)`. The static system prompt is `prompts/system.md`, unchanged. The
model defaults to the chat's client from the factory (§9): the primary with the chat's token budget and
reasoning effort, with its fallbacks. The `model` parameter is the test seam: the integration suite drives
a scripted fake chat model through the real graph and middleware (§14). **(call)**

`create_agent` names its nodes `model` and `tools`. Everything that keyed on `chat` and `tool_call`
(the stream filter, tests) keys on those. Langfuse traces show the new node names; the graph name and the
tool span names are unchanged. **(call)**

### 4.2 State

`ChatState` extends the library's `AgentState`:

| Key | Holds | Today |
|---|---|---|
| `messages` | the library's | same |
| `long_term_memory: str` | this turn's memory text, set by the memory middleware | same key |
| `stopped: dict[str, str]` | final message id → `step_limit` or `repeated_call` | same |
| `summary: str` | the running summary of turns before `summary_through` (§7) | new |
| `summary_through: str \| None` | id of the last message the summary covers | new |

`turn_steps` goes: the step count is the number of tool-calling AI messages after the last human message,
derived when needed. **(call)** A checkpoint from before this step lacks the two summary keys, which
default; no migration. The dev database may be reset anyway if anything else shifts. **(user)**

### 4.3 Middleware

Each row is one class in `chatbot/middleware/`. The behaviours in the right column are the contract; the
hook split is a **(call)** the builder may restructure as long as the behaviours hold and each middleware
stays independently testable.

| Middleware | Hooks | Replaces | Behaviour it must keep |
|---|---|---|---|
| **memory** | `before_agent`, `after_agent` | the duplicated fetch and write in `get_response` and `get_stream_response` | Fetch relevant memory for the turn's user message into `long_term_memory` ("No relevant memory found." when empty). After the turn, write the user's message only, backgrounded, with the identity keys stripped from metadata. Both best effort: a mem0 failure is logged, never fails the turn. |
| **summary** | `before_model` | the drop-oldest trim in `context.py` | §7. |
| **request shaping** | `wrap_model_call` | `build_model_context`, `render_turn_context`, `drop_unanswered_tool_calls` at call time | The model request is `[system, summary (if any), *earlier turns after the cutoff, turn context, *current turn]`. Earlier turns lose their reasoning blocks and each tool result becomes the one-line stub (title and period from the artifact; "Tool" when neither). The current turn (from the last human message) is never changed. Unanswered tool calls are dropped from the request with the text beside them kept. The turn context message is today's date, the preamble (empty on failure, logged), and the memory text, worded as today. Request only: state is untouched. |
| **turn bound** | `wrap_model_call`, `after_model` | the step cap, `repeated_call`, `_wrap_up` | Exactly today's semantics (`test_graph.py` pins them). Every model call up to the `CHAT_MAX_STEPS`-th is made with tools. When a response asks for tools and either it is the `CHAT_MAX_STEPS`-th call of the turn or it repeats a (tool, arguments) pair already called this turn, that response is dropped (never persisted, never executed) and, inside the same hook, a second call is made with no tools and the wrap-up instruction appended; its text answer is the turn's final message and its id goes in `stopped` with the reason (`step_limit` or `repeated_call`). A call that answers in text, the last allowed one included, ends the turn normally with `stopped` unset. If the wrap-up call fails or returns no text, the fixed fallback text is the answer. An empty text reply at any other point fails the turn. The recursion limit follows the setting as today. |
| **tool events** | `wrap_tool_call` | `_tool_call`, `_invoke_tool`, the metrics, the error texts | Before a tool runs, `ToolCallStarted(id, name)` on the custom stream; after, `ToolCallFinished(id, ok, artifact)`. Prometheus: `tool_calls_total{tool, outcome}` with the same outcomes (`success`, `invalid_args`, `error`, `unknown_tool`) and `tool_call_duration_seconds{tool}` on every outcome. Error texts to the model are the current three, verbatim: the validation wording ("Invalid arguments: …"), a `ToolException`'s own message, and the fixed crash text; an invented tool name gets the fixed unknown-tool text, never the library's list of valid tools. Tool arguments are logged truncated as today. |
| **model timing** | `wrap_model_call` | `_call_model` | `llm_inference_duration_seconds{model}` labelled with the model that answered (from the response metadata, falling back to the requested name), and the `llm_response_generated` log line. |

Parallel tool calls are the library's `ToolNode`: every call of one response runs concurrently, results in
call order. Each tool is traced as its own run, so Langfuse keeps one span per call named for the tool
without the `RunnableLambda` wrapper.

Fallback across models is `ModelFallbackMiddleware` or the factory's `with_fallbacks` (§9); the builder
picks one and uses it for the wrap-up and title calls too. **(call)** Retries are the client's (§9).

### 4.4 Streaming and the custom stream

The agent streams with `stream_mode=["messages", "custom"]`. Reasoning and text deltas come from the
`model` node's AI message chunks; `ToolCallStarted` and `ToolCallFinished` are plain dataclasses in
`agents/chatbot` carrying no display type. The translation to the wire events, the separators between a
turn's messages and between reasoning paragraphs, and the `done`/`error` frames are `conversation`'s (§6).

Reasoning: the builder uses the standard content-block API (`message.content_blocks`, `message.text`)
where the spike (§11) shows OpenRouter delivers reasoning as standard blocks; otherwise the current raw
block parsing moves into one function in `conversation/domain/chat.py` and nowhere else.

### 4.5 `ChatbotAgent`

A thin object over the compiled graph, built once at startup in `main.py` and put on `app.state.agents`:

- `stream(message: str, conversation_id, context: TurnContext)` — async iterator of the graph's native
  stream tuples, with the turn config (thread id, Langfuse callbacks, metadata, recursion limit) and
  `context=` passed.
- `run(message, conversation_id, context)` — the non-streaming turn; returns the state's messages and
  `stopped`.
- `state(conversation_id)` — messages and `stopped` from the checkpoint, for the history endpoint.

No `BaseAgent`, no `is_ready`, no registry, and no `title_for`: `ConversationService.generate_title`
already holds the agent, so it reads the state, folds it with `conversation/domain/chat.py`'s `history`
and `first_exchange` (moved there from `title.py`), and calls `agents/chatbot/title.py`'s
`generate_title(user_text, reply_text, …)`, which is already a function over two strings. **(call)** The
input is a string; the route builds no `Message` object. `get_chat_history` and `_process_messages` move to
`conversation/domain/chat.py` as a pure function over messages (§6).

## 5. Tools

### 5.1 One tool, one place

A tool is a `StructuredTool.from_function(coroutine=…, name=…, description=…, args_schema=…,
response_format="content_and_artifact", metadata={"title": …})`. Its function returns
`(content, display.model_dump())`: `content` for the model, the artifact for the UI, exactly the pair
`ToolOutcome` carries today. The seven tools keep their names, descriptions, argument schemas, content
wording and display shapes byte for byte; the integration tests over seeded data pin that.

`conversation/tools/__init__.py` exposes `chat_tools() -> list[BaseTool]` and `preamble`. Adding an
analytics tool is one more entry in `analytics.py`'s list and its renderer in `display.py`; a tool of
another kind is a new file and one entry in `chat_tools()`. **(user)** `analytics.py` holds the two
argument models and the six declarations through the shared `_analytics_tool` factory, as `service.py`
does today; `search.py` holds the search tool with its argument model and the pure filter that was
`domain/search.py`. The `domain/` folder goes: it existed to put two pure files under the R9 contract, and
nothing in `tools/` imports the ORM or the framework anyway. **(user)**

Bad arguments raise `ToolException` with the message for the model (today `ToolArgumentError`); the
tool-events middleware turns it into the error `ToolMessage` as today. The argument schemas carry no regex
`pattern` (money is a JSON number) and `test_schemas.py` keeps guarding it.

### 5.2 The turn context

`TurnContext` is a dataclass in `agents/chatbot/context.py` and the graph's `context_schema`:
`user_id`, `session_factory`, and a typed per-turn slot for the analytics history load (a
`Future[AnalyticsHistory]`-shaped attribute rather than an untyped cache dict; the type is opaque to
`agents`, so the slot is `Any` there and typed in `conversation/tools/periods.py`). **(call)** The route
builds one per turn and passes it as `context=`; a tool declares `runtime: ToolRuntime[TurnContext]` and
reads the user from `runtime.context`. The user is never a tool argument, as today.

The tool reads the user's history through `runtime.context` exactly as `turn_history` does today: one load
per turn, shared by concurrent calls, from a short-lived session off the context's factory.

### 5.3 The preamble

`preamble(context) -> str` keeps its wording and its three cases. The request-shaping middleware calls it;
a failure leaves it out and logs, and the turn is still answered.

## 6. The wire belongs to `conversation`

`conversation/schemas.py` gains what `agents/messages.py`, `agents/chatbot/events.py` and the display half
of `toolkit.py` hold today: `ChatMessage`, `Activity`, `ReasoningPart`, `ToolPart`, `ConversationHistory`;
`ToolDisplay`, `ToolTable`, `TableColumn`, `SummaryItem` and their kinds; the six stream events. Field
names, JSON shapes and the OpenAPI output are unchanged: `make check-contract` passes with no diff in the
generated client. The events docstring, which is the SSE contract the web mirrors by hand, moves with them.

`conversation/domain/chat.py` holds two pure functions:

- `history(messages, stopped, titles) -> list[ChatMessage]` — today's `_process_messages`/`_reply`:
  one reply per turn, texts joined with a blank line, reasoning and tool parts in order, `stopped` marked,
  a turn with no final answer adds nothing, a display that no longer validates leaves the row without
  figures (logged). `titles` maps a tool name to its display title from the tools' metadata; a name not in
  it (one the model invented) adds no part. The router gets the map from `ChatbotAgent.tool_titles`,
  built from the tools the graph was compiled with, so `conversation`'s core never imports `tools/`
  (R10 holds; its contract row is renamed from `finance` to `tools`). **(call)**
- `events(stream) -> AsyncIterator[StreamEvent]` — today's `get_stream_response` body: the reasoning
  and text deltas with their separators, `ToolCallStarted` → `tool_started` with the title,
  `ToolCallFinished` → `tool_finished` with the artifact validated into `ToolDisplay` (null when not ok),
  then `done` with `stopped`. The separator bug the review found (a wrap-up's first reasoning delta after a
  text event arrives without its `"\n\n"`) is fixed here: a text event ends a reasoning paragraph, and the
  next reasoning delta starts a new one.

`agents` imports nothing from `conversation`: the artifact is a dict to it, and the custom-stream payloads
are its own dataclasses. The one type both sides share is `TurnContext`, which lives in `agents` and
`conversation` imports downward.

## 7. Summaries: the thread survives, the transcript stays

A conversation whose earlier turns pass `CHAT_HISTORY_MAX_TOKENS` is summarised rather than forgotten
**(user)**. The library's `SummarizationMiddleware` deletes the summarised messages from the checkpoint
and the history endpoint reads the checkpoint, so a reopened conversation would lose its early turns.
Instead, an own middleware on the same hook keeps every message in state and summarises only what the
model is sent **(user)**:

- `before_model`: count the tokens of the earlier turns after `summary_through` (the library's
  approximate counter, or the model's where it can count; the current turn is never counted or
  summarised). Over the budget, ask the summary model to fold those turns into the existing `summary`,
  and set `summary_through` to the last message folded. Turns are folded whole. The two keys are the only
  state update; `messages` is never rewritten.
- **The summariser reads the stubbed form of the turns, never the raw one**: the same reasoning-stripped,
  tool-result-stubbed messages the request-shaping middleware sends the chat model (shared code). A
  figure from a tool result then cannot reach the summary by construction; the prompt below is the second
  line. The assistant's own earlier text, which carries the substance of each answer, is what gets
  summarised, as it is what the chat model sees of earlier turns today. **(call)**
- The request-shaping middleware sends `summary`, when set, as one message after the system prompt and
  before the turns that follow the cutoff, worded as "Earlier in this conversation: …".
- The summary prompt is `prompts/summary.md`, the app's own: keep what was asked, what was answered in
  substance, decisions and anything the user said about themselves; **never amounts, counts,
  percentages, rates or figures about a period**, and never a figure from a tool result. Same policy as
  the memory extraction instructions. The system prompt's rule that figures come only from this turn's
  tools already covers what a summary says.
- The summary model is `CHAT_SUMMARY_MODEL`, default `openai/gpt-5-nano`, through the factory with
  fallbacks. **(call)** A failed summary call is logged and the turn proceeds with the request trimmed
  to the budget by dropping the oldest unfolded turns, as today: forgetting is the fallback, never a
  failed turn. **(call)**

`chat.md` §4 flips its rule: "a very long conversation forgets its beginning — there is no summary"
becomes the above, and the TODO entry is deleted.

## 8. Memory

mem0 is unchanged in substance **(call)**: the memory middleware is the two hooks in §4.3, the extraction
instructions stay, erasure still calls `delete_user_memory`. `core/memory.py` is today's factory moved.

## 9. The LLM integration

`integrations/llm/models.py` replaces `service.py`:

- `chat_model(name=None, *, max_tokens=None, reasoning_effort=None) -> BaseChatModel` builds a
  `ChatOpenAI` against OpenRouter: the one site that reads the credential and the base URL, sets the
  token-counting name, `max_retries=settings.llm.MAX_LLM_CALL_RETRIES` (the SDK's own exponential
  backoff on rate limits, timeouts and server errors; tenacity goes), and for a model that reasons, the
  effort and `summary: "auto"`. Cached by its arguments.
  - **Which models reason, and at what effort by default.** A model reasons when its bare name (after
    the provider prefix) starts with `gpt-5`, the rule mem0's config already uses. The factory keeps the
    registry's per-model default efforts as a small table: `gpt-5-mini` `low`, `gpt-5` `medium`,
    `gpt-5-nano` `minimal`; a name outside the table gets no reasoning parameters at all (the provider's
    default), so a non-reasoning name such as `.env.test`'s `gpt-4o-mini` still builds. Only the chat
    passes `reasoning_effort`; the title, the summary and the one-call agents keep the table's defaults
    and `settings.llm.MAX_TOKENS`, so their cost and latency are unchanged. **(call)**
  - **Startup without a key.** The graph compiles in the lifespan and `ChatOpenAI` refuses an empty
    key at construction, so with `OPENROUTER_API_KEY` unset the factory passes a placeholder key, as
    `core/memory.py` already does for mem0; the first model call then fails with a 401 that is logged, and
    the server starts, as the root `CLAUDE.md` promises. **(call)**
- `with_fallbacks(model, **tuning)` wraps the primary with `settings.llm.LLM_FALLBACK_MODELS` built with the
  same tuning, in order. The chat agent uses it (or `ModelFallbackMiddleware`, §4.3); the one-call agents,
  the title and the summary calls use it.
- The exceptions file stays. The fallback chain raises the provider's last error; a thin wrapper at the
  call boundary (`core/structured.py` and the chat's model-timing middleware) translates `OpenAIError`
  into `LLMRateLimitError`, `LLMTimeoutError` or `LLMAPIError` as `_call_with_fallback` does today, so the
  insights service's `except` and the 503 handler keep working.

Settings: `DEFAULT_LLM_MODEL` keeps its name (the primary); `LLM_FALLBACK_MODELS: list[OpenRouterModel]`
is new, default `["openai/gpt-5", "openai/gpt-5-nano"]`; `DEFAULT_LLM_TEMPERATURE` goes with the
gpt-4o entries (the gpt-5 family rejects it) **(user: the lineup; call: the setting)**; `CHAT_SUMMARY_MODEL`
is new (§7). `.env.example` follows. No model parameter depends on the environment any more.

The model that answered is read from the response metadata where a label needs it; the requested model is
the setting. `current_model_name()` has no replacement: the route's stream-duration label uses the primary
from settings. **(call)**

## 10. The one-call agents

`core/structured.py` becomes `ask(shape, system, user, config, *, model=None) -> shape`:
`with_fallbacks(chat_model()).with_structured_output(shape, method=…)` with one retry on an invalid answer
(`with_retry` on the parse error, two attempts, as `ask_json` does), raising `InvalidModelAnswer` after it
and the translated `LLMServiceError` for a model failure. The `method` is what the spike (§11) finds works
on OpenRouter for the lineup; if JSON-schema mode is unreliable there, the fence-tolerant JSON parse stays
behind the same `ask` signature and the spec's claim is only that the callers no longer know which.

The three callers change only their import and call: the CSV mapper's `None` on any failure, the
labeller's batches, semaphore and per-batch fallback, and the insights writer's lenient list validation
(drop an invalid item, keep the answer, log the count) are unchanged. Their prompts and prompt versions
are unchanged. The `_Insights` wrap validator must survive the structured-output path; if the chosen
method validates strictly on the provider side, the builder loosens the wire schema and keeps the lenient
validation in code.

## 11. Spikes first

Two throwaway checks go at the head of the plan; their findings are recorded in the plan, not here.

1. **Reasoning through OpenRouter on the library's standard blocks.** With `chat_model()` for
   gpt-5-mini at effort `medium`: do streamed chunks and the persisted message expose reasoning summaries
   through `content_blocks`, with the item boundaries the stream needs for paragraph breaks? Does a
   reasoning-bearing history round-trip through `create_agent` unchanged (the provider accepts its own
   blocks back)? If not, §4.4's fallback applies.
2. **Structured output through OpenRouter.** For gpt-5-mini and gpt-5-nano: which
   `with_structured_output` method returns valid answers for the three shapes (a dict root model, a list
   root model, the insights list with nested optionals), and does a schema with `max_length` on the root
   pass the provider's validation? Decides §10's `method`.

## 12. Constraints

- **Behaviour frozen.** The SSE frames, the history endpoint's JSON, the tool results' `content` and
  `display`, the preamble wording, the error texts, the metric names and labels, the Langfuse span names
  for tools and the graph name are identical. The web app is not touched. `make check-contract` shows no
  client diff.
- **Layering.** R2 stands: `app.agents` imports no module. R1, R6, R9 and R10 unchanged. The import
  contracts in `pyproject.toml` need no new rows; `test_module_contracts` passes.
- **No new dependency.** `langchain`, `langchain-core`, `langgraph` and `langchain-openai` are already
  pinned; the pins may move within their majors if a middleware needs it, with the lock updated. `tenacity`
  stays for the labeller only if it still uses it; otherwise it may leave `pyproject.toml`.
- **Settings.** The chat's limits (`CHAT_MAX_STEPS`, `CHAT_REPLY_MAX_TOKENS`, `CHAT_HISTORY_MAX_TOKENS`,
  `CHAT_REASONING_EFFORT`) keep their names and meanings.
- **Startup.** The graph compiles in the lifespan as today; a missing tools list fails startup.
- **Erasure** still deletes checkpoints by thread id and memories by user; the `core` paths are the only
  change there.

## 13. Left to the builder

- The exact hook split in §4.3. Fallback inside the agent is `ModelFallbackMiddleware`, since the
  runnable wrapper is not a `BaseChatModel` and `create_agent` wants one; the one-call agents use the
  runnable wrapper.
- Where tool arguments are validated so the "Invalid arguments: …" wording survives: pre-validating in
  `wrap_tool_call` against `tool.args_schema` is the obvious way.
- How `TurnContext` carries the typed history slot without `agents` naming the analytics type.
- The token counter the summary and request-shaping middleware share, and the fallback to the estimate.
- Whether `tool_events` emits from `wrap_tool_call` or from `ToolNode`'s own wrapper; either satisfies §4.3.
- File-by-file order of the move, as long as every commit passes `make check-server` and the suite.
- Whether the translated LLM exception carries `models_tried` and `starting_model` as today's does; the
  handler and the insights service use neither.

## 14. Testing expectations

- **The guard is the integration suite**: `tests/integration/modules/conversation/router/test_chatbot.py`
  and `tests/integration/modules/conversation/finance/test_service.py` (moved to `tools/`) pin the
  stream frames, the history JSON and the seven tools' outputs against the seeded user. Their
  *assertions* do not change; their *fixtures* do: today's `mock_agent` stubs methods that go. The
  replacement is a scripted fake `BaseChatModel` (a queue of responses: reasoning blocks, text, tool
  calls) handed to `build_chatbot(model=…)`, so the route tests run the real graph, middleware, tools and
  translation end to end, including the seeded-lookup test. A fixture that stubs `ChatbotAgent`'s
  methods instead guards only the route and is not enough. **(call)** Any assertion that has to change is
  a behaviour change to justify in the PR.
- Each middleware has unit tests in `tests/unit/agents/chatbot/middleware/`, driving its hook with a
  fake handler: the step cap and repeat cases from `test_graph.py`, the request shaping cases from
  `test_context.py`, the summary trigger and the figure-free prompt, the tool-event outcomes and metrics.
- `tests/unit/modules/conversation/domain/test_chat.py` takes over `test_base_agent.py`'s history and
  stream cases, the separator fix included.
- `tests/unit/integrations/llm/` covers the factory's parameters per model (reasoning vs not, retries) and
  the fallback order; the registry tests go.
- `tests/unit/agents/test_structured.py` follows `ask`; the three one-call agents' tests mock the model
  as they do now.
- Deleted with their code: `test_factory.py`, `test_toolkit.py`, `test_messages.py`, `test_graph.py`'s
  loop tests once the middleware tests cover them.

## 15. Docs in the PR that completes it

- [`architecture/server.md`](../../docs/architecture/server.md): §1's tree and the "agents get module
  knowledge by injection" paragraph rewritten for `create_agent`, `ToolRuntime`, the context, the
  `conversation`-owned wire, and `core/`; §2's feature sub-package paragraph and §3's R10 sentence
  name `conversation/tools/` instead of `finance/` and drop its `domain` slot.
- `server/pyproject.toml`: the R10 row for `conversation` forbids `app.modules.conversation.tools`.
- `server/CLAUDE.md` **Agent Architecture**: `BaseAgent` and `Toolkit` out; the tool recipe (a
  `StructuredTool` in `conversation/tools/`, `ToolException`, no regex pattern, `ToolRuntime`) and the
  middleware list in.
- [`chat.md`](../../docs/product/features/chat.md) §4: the bounded-context rule gains the summary; "there
  is no summary" goes; §5 drops summaries from "Not built".
- [`TODO.md`](../../docs/TODO.md): delete *the agent layer imports the chatbot's stream contract* and
  *conversation summaries*; delete the three absorbed bullets of *code review leftovers*; the *every LLM
  call starts at the default model* entry is reworded for the fallback chain (it still starts at the
  primary).
- `server/.env.example`: the settings in §9.
- `ROADMAP.md`: the 7b row to `complete`; this spec and its plan deleted.

## 16. Risks

- **OpenRouter and the standard content blocks.** If the spike finds reasoning does not arrive as
  standard blocks, the raw parsing survives in one place (§4.4); the step still lands.
- **Structured output on OpenRouter.** If JSON-schema mode is flaky for a shape, the parse path stays
  behind `ask` (§10); the step still lands.
- **Library drift.** The middleware API is 1.x-stable but young; the plan pins the exact `langchain` version
  it was built against in the lock, and the middleware tests drive hooks directly so an upstream change
  fails loudly.
- **Behavioural drift in the move.** Mitigated by the integration suite being the gate (§14) and by
  moving tool by tool, middleware by middleware, with the suite green at each commit.
- **Summary quality.** A summary that drops something the user later refers to is a worse experience
  than today only if today's forgetting would have kept it, which it would not. A summary that carries a
  figure is the real risk; the prompt forbids it, the system prompt refuses to use it, and step 9's
  grounding check is where it gets measured.

## 17. Appendix — verified against the installed library

Checked by introspection on 21 Oct 2026 against langchain 1.3.18, langchain-core 1.2.7, langgraph 1.0.5,
langchain-openai 1.6.0, openai 3.7.0 (the lock). The plan cites these rather than re-checking them; a pin
that moves re-checks the row it touches.

| Claim | What was found |
|---|---|
| `create_agent` | `(model, tools, *, system_prompt, middleware, response_format, state_schema, context_schema, checkpointer, store, interrupt_before, interrupt_after, debug, name, cache, transformers)`. Its nodes are `model` and `tools`. `model` is a `BaseChatModel` or a string; a string is built at once through `init_chat_model`. |
| Middleware hooks | `AgentMiddleware` has `before_agent`, `before_model`, `wrap_model_call`, `after_model`, `wrap_tool_call`, `after_agent`, each with an `a…` async variant, plus a per-middleware `state_schema`. Decorators of the same names and `dynamic_prompt` exist. `after_model` may return state updates and `jump_to` in `{"tools", "model", "end"}`. |
| `ModelRequest` / `ModelResponse` | Request fields: `model, messages, system_message, tool_choice, tools, response_format, state, runtime, model_settings` — tools and messages are separate, so a hook can strip tools or append a message without touching the other. Response fields: `result, structured_response`. A hook may call the handler more than once (the wrap-up call inside the step-cap hook). |
| `ToolCallRequest` | Fields `tool_call, tool, state, runtime`; `tool is None` when the model named a tool that does not exist, so the fixed unknown-tool text is reachable from `wrap_tool_call`. `runtime.stream_writer` writes the custom stream. |
| `ToolRuntime` | Fields `state, context, config, stream_writer, tool_call_id, store, tools, execution_info, server_info`; a tool declares a `ToolRuntime[TurnContext]` parameter and the node injects it; it is not in the schema sent to the model. |
| `Runtime` | Fields `context, store, stream_writer, heartbeat, previous, execution_info, server_info, control`. `StateGraph(state_schema, context_schema, *, input_schema, output_schema)`; `ainvoke`/`astream` take `context=`. |
| `ToolNode` | `(tools, *, name, tags, handle_tool_errors, messages_key, wrap_tool_call, awrap_tool_call)`. Its default texts, which the spec does not use: `"Error: {requested_tool} is not a valid tool, try one of [{available_tools}]."` and `"Error: {error}\n Please fix your mistakes."`. Runs one response's calls concurrently, results in call order. |
| `StructuredTool.from_function` | `(func, coroutine, name, description, return_direct, args_schema, infer_schema, *, response_format in {"content", "content_and_artifact"}, parse_docstring, error_on_invalid_docstring, **kwargs)`. `BaseTool` fields include `handle_tool_error`, `handle_validation_error`, `response_format`, `metadata`, `tags`. |
| `SummarizationMiddleware` | `(model, *, trigger, keep, token_counter, summary_prompt, trim_tokens_to_summarize)`; runs in `before_model` and returns `{"messages": [RemoveMessage(REMOVE_ALL_MESSAGES), HumanMessage(summary, additional_kwargs={"lc_source": "summarization"}), *preserved]}`, i.e. it rewrites the checkpoint. This is why §7 is an own middleware. |
| `ContextEditingMiddleware` | `(*, edits, token_count_method in {"approximate", "model"}, token_counter)`; runs in `wrap_model_call`, request only. `ClearToolUsesEdit(trigger, clear_at_least, keep, clear_tool_inputs, exclude_tools, placeholder)` keeps the last `keep` tool results by count, not by turn, which is why §4.3's request shaping is an own edit. |
| Other prebuilt middleware | `ModelCallLimitMiddleware(*, thread_limit, run_limit, exit_behavior in {"end", "error"})` ends with a fixed message, not a wrap-up call. `ToolCallLimitMiddleware(*, tool_name, thread_limit, run_limit, exit_behavior)`. `ModelFallbackMiddleware(first_model, *additional_models)`. `ModelRetryMiddleware`, `ToolRetryMiddleware`, `ToolErrorMiddleware(on_error, *, aon_error, tools)`. |
| Fallback wrapper | `model.with_fallbacks([...])` returns a `RunnableWithFallbacks`, which is not a `BaseChatModel`: `create_agent` cannot take it, so inside the agent the middleware is the way; the one-call agents may use the wrapper. |
| Content blocks | `AIMessage.content_blocks` and `.text` exist. Whether OpenRouter's reasoning summaries surface as standard `reasoning` blocks is spike 1 (§11). |
| Messages utils | `langchain_core.messages.trim_messages` and `ChatMessage` exist; LangGraph's `add_messages` reducer accepts `HumanMessage` or `{"role", "content"}` dicts, so the input `Message` type has no job. |
| `ChatOpenAI` without a key | Raises `OpenAIError: Missing credentials` at construction on openai 3.7.0; hence §9's placeholder key at startup. |
