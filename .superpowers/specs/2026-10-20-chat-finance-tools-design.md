# 7 Chat finance tools — design

**Roadmap row:** 7 Chat finance tools · **Branch:** `feat/chat-finance-tools` (from `template-base`)
**Brainstormed:** 20 Oct 2026 · **Feature doc:** [`docs/product/features/chat.md`](../../docs/product/features/chat.md)
· **Data model:** [`docs/data-model/conversation.md`](../../docs/data-model/conversation.md) (no schema change)
**Rides along (TODO.md):** *a model call holds the request's DB connection* · *the chatbot names the
default model after a fallback* · *Web — tests: a failed conversation create*

Decisions are marked **(user)** when Tiziano made them in the brainstorm, **(call)** when they were
made for him and he has not ruled on them. Everything unmarked follows from the codebase as it is.

---

## 1. Intent

Today the assistant cannot see the user's money; a question about spending gets a generic answer.
Step 7 makes it a finance assistant that answers from the user's own transactions:

- **Facts** — "where did my money go last month?", "where am I spending most?", what is growing,
  what recurs, the savings rate over time.
- **Advice tied to the data** — "how can I optimise my spending?", "how do I improve my savings
  and investment rate?" — pointing at specific things in the user's numbers ("Eating Out is up 40%
  over three months; you pay for two streaming services"), not tips that fit anyone. **(user)**

**The one rule that decides trust (user): the assistant never makes up a number that is not in the
user's data.** Most of this design is in service of it.

Investments are seen only through transactions: money moved into **Savings & Investments**, and the
savings rate. Holdings, portfolio value and returns are out of scope. **(user)**

**The savings rate is the analytics page's (user).** The assistant reports the same savings rate the
Trends and Income vs Expenses tabs show. Analytics decides income and expense by sign alone
(TODO *income and expense are decided by the sign of the amount alone*), so a transfer into Savings &
Investments counts as spending and *lowers* that rate. When the question is about saving or
investing, the assistant shows the Savings & Investments amount for the same period beside the rate
(from `category_breakdown`) and explains that investing lowers the rate. It never computes an
adjusted rate itself. A "saved + invested" rate, if wanted, is analytics work for a later step.

## 2. Goals, non-goals, anti-goals

**Goals**
1. The assistant answers fact and advice questions from tool results over the user's data.
2. The user sees what the assistant is doing while it works and afterwards: thinking (when the
   model provides it), each tool call, and what each returned — all collapsible. **(user)**
3. Long-term memory keeps who the user is (goals, circumstances, preferences), never figures.
4. The loop is bounded and recovers from its own bad tool calls.
5. The three ride-along TODOs are closed.

**Non-goals**
- **Evaluation** (an eval set, a grounding check over answers, LLM-as-judge) — its own ticket,
  to be done properly later. **(user)** This step must not add an eval harness; it should leave the
  traces (Langfuse) good enough that the eval ticket can build on them.
- **Writing anything.** The assistant is read-only; no recategorising from chat. **(user)**
- Web search — removed, see §6. **(user)**
- Conversation summaries / compaction beyond §5.4 — a TODO.
- A tool over stored insights (already a recorded follow-up; roadmap decision 16 Oct 2026).
- Free-form code execution in a sandbox (TODO *Chat — free-form questions*).
- Suggested prompts, clearing history from the screen (deferred 13 Oct 2026, unchanged).

**Anti-goals — failure even if it technically works**
- A figure in an answer that no tool returned in that turn, or a figure remembered from an
  earlier turn or conversation presented as current.
- An answer that disagrees with the dashboard or the analytics page for the same period.
- The user's figures leaving the app other than to the LLM provider (web search queries, memory
  extraction of amounts, remote images).

## 3. What the assistant can look up

Seven read-only tools, defined in the `conversation` module as thin async functions over what the
`analytics` and `transaction` package roots export. The first six wrap the analytics methods
one-to-one, so the assistant's numbers are the dashboard's and the analytics page's numbers. They
call the methods on **`AnalyticsHistory`**, not on `AnalyticsService`: each `AnalyticsService` method
reloads the whole history, and its own docstring says a caller needing several windows "takes one
`history()` and calls it". So a turn loads `analytics_service.history(session, user_id)` once
(short-lived session, §10) and every analytics tool in that turn calls `history.spending(range)`,
`history.categories(range, top_n)` and so on. Ranges follow the analytics rule:
whole finished months, the month in progress apart as month-to-date
([`analytics.md`](../../docs/product/features/analytics.md) §2).

| Tool (working name) | Wraps | Answers |
|---|---|---|
| `spending_overview` | `AnalyticsHistory.spending` | income, expenses, net, savings rate, by month, for a period |
| `category_breakdown` | `.categories` | spend per category, share, change vs previous period; growing / declining categories |
| `top_merchants` | `.merchants` | top merchants by spend, concentration |
| `recurring_costs` | `.recurring` | recurring costs and subscriptions, possibly forgotten ones |
| `spending_behaviour` | `.behaviour` | by weekday, weekday vs weekend, seasonality, category stability |
| `unusual_spending` | `.anomalies` | outliers and category spikes |
| `search_transactions` | `transaction_service` (new read) | see below **(user: the tool; call: its shape)** |

**`search_transactions`** filters as the transactions page does — merchant text (substring,
case-insensitive), date range, categories, amount range, recurring only — plus **weekday**, which the
page lacks. It returns, computed by the server, never by the model:

- `count` and `total` of the matches;
- optionally the same figures **grouped by** one of month, merchant, category, weekday;
- a **capped sample** of matching rows (about 20; largest or most recent, the model chooses) with
  date, merchant, amount, category.

The model is never handed hundreds of rows to add up: summing is where invented numbers come from.
Money in and money out are reported apart (count and total for each), never netted into one
figure, by the same sign rule analytics uses. **(call)**

**Tool design rules (call)**
- Names and descriptions say what the tool is for, when *not* to use it, and what it returns.
- Arguments are typed and validated. **Category is an enum of the fixed list**
  ([`categorisation.md`](../../docs/product/features/categorisation.md)); dates are ISO; a period is
  expressed the way `DateRange` already is. A wrong value is hard to express.
- Outputs are bounded, structured summaries: totals, ranked items capped at a sensible length, no
  raw dumps. Each result carries the **period it covered**, named the way the dashboard names it,
  plus a one-line summary the UI shows (§7).
- **The user is never an argument.** Every tool reads the signed-in user from the run's config,
  which the route sets from `CurrentUser`. No wording of a question can reach another user's data.

## 4. How the assistant behaves

- **A real system prompt** replaces the generic one (`app/agents/chatbot/prompts/system.md`): a
  personal-finance assistant for this user; every figure comes from a tool call made in this turn;
  name the period in every answer; when the data cannot answer, say so plainly rather than
  estimate; advice must point at the user's own numbers; general financial knowledge (what an
  index fund is, rules of thumb) may be explained but is not a figure about the user; the savings
  rate is the analytics one, explained as in §1 when investing is involved.
- **Each turn the model is told:** today's date, the last finished month, and the span of months
  the user's data covers. "Last month" and "the last three months" then mean what they mean on the
  dashboard, and a question about a period with no data gets "you have no transactions before …".
- **No transactions at all:** it says so and points to CSV import instead of answering with zeros.
- **A question the tools do not cover** gets an honest "I can't work that out yet", not an
  approximation. With search, few should be left (the TODO sandbox covers the rest).

## 5. The agent loop

The loop stays the hand-rolled two-node graph in `app/agents/chatbot/graph.py` (`chat` ⇄
`tool_call`). Changes:

### 5.1 Limits (call)
- A **step cap per turn** (model calls with tool calls; a setting, on the order of 8). LangGraph's
  own recursion limit (25) stays above it as a backstop and must never be what the user meets.
- **Repeat detection:** the same tool with the same arguments twice in a turn stops the loop.
- Hitting either ends the turn with a **partial answer marked as stopped** — the model is asked for
  a final answer from what it has, with no further tools, or a fixed line if that is not possible —
  never the "couldn't reply" error.

### 5.2 Bad tool calls recover through the loop (user asked; call on the split)
The error goes back to the model as that call's result and the model corrects itself on the next
step. Three cases:
- **Invalid arguments** (schema/validation failure, a value outside what the data allows): an
  *actionable* message we write — "category must be one of …", "no data before March 2025". Today
  these fall into the generic failure; that changes.
- **Unknown tool name:** unchanged (`TOOL_UNKNOWN_MESSAGE`).
- **A crash inside a tool** (DB error, a bug): unchanged fixed `TOOL_FAILED_MESSAGE`. Exception text
  never enters a `ToolMessage`, because tool messages are checkpointed and re-enter context every
  turn (the reasoning in `graph.py` stands).

Model calls keep their existing retries and fallback in `LLMService`. No retry wrapper is added
around tool crashes.

### 5.3 Parallel calls and one history load (call)
- Independent tool calls on one model message run **concurrently**, not one after another.
- The user's `AnalyticsHistory` is **loaded once per turn** and shared by that turn's tool calls,
  rather than reloaded per call.

### 5.4 Context management (user: approach; call: numbers)
Today `settings.llm.MAX_TOKENS = 2000` is both the reply cap (`LLMService`) and the history budget
(`prepare_messages`). One tool result can approach 2,000 tokens, so the oldest-first trim can drop
the very question being answered; and for a reasoning model the reply cap includes the thinking.
- **Split the setting:** a reply cap with room for reasoning, and a separate, much larger history
  budget.
- **Never trim inside the current turn.** The latest user message and everything after it always
  go to the model; only earlier turns are trimmed, oldest first.
- **Stub old tool results** in what is sent to the model: a tool result from an earlier turn
  becomes one line ("Spending by category, Sep 2026 — result omitted; call the tool again for
  figures"). This also enforces the §1 rule. The checkpoint keeps the full result, so the
  activity block in the history still shows it.
- The current fallback (skip trimming when the token counter cannot measure reasoning blocks) must
  not silently send an unbounded history once reasoning is kept; count or estimate instead.
- **Very long conversations:** the oldest turns are dropped; no summary. **(user)** Summaries are a
  TODO.

### 5.5 Prompt layout (call)
The stable part of the system prompt and the tool definitions come first; the date, data span and
memory come after, so the provider can cache the prefix. Today the date and memory sit inside the
prompt template.

## 6. Web search and memory

- **Web search is removed** (`duckduckgo_search` tool unbound). **(user)** Reasons: advice must come
  from the user's data, general know-how is in the model, web results introduce outside numbers, and
  the model writes the queries itself, so the user's figures would go to DuckDuckGo. Easy to add back
  later as a narrow tool (e.g. current interest rates) if missed.
- **Memory is fed only the user's own messages.** **(user)** `update_memory` currently receives the
  whole conversation, tool results and replies included; it receives **this turn's** user message
  only (earlier turns were already offered to it). This is a code filter and holds every time.
- **mem0's `custom_instructions`** (mem0 2.0's single steering key — see the note in
  `app/agents/shared/memory/factory.py`) tells extraction to keep goals, circumstances and
  preferences ("saving for a flat", "paid monthly", "rent fixed until March") and to drop amounts
  and anything describing a period's activity. **(user)** Best-effort: a model following
  instructions.
- Memory read stays as is. Memory is never a source of figures (system prompt).

## 7. What the user sees

Mocked and agreed in the brainstorm (option C, refined). **(user)** Mockups:
`.superpowers/brainstorm/24640-1792489429/content/agent-activity-v2.html` (gitignored; local only).

One **activity block** sits above each assistant reply:

- **While working:** open. Header = a live label for the current step plus an **elapsed timer**:
  "Thinking… 0:02", then "Looking up spending by category… 0:03" (shimmer text). Below it, a
  timeline: thinking as muted italic text, each **tool call as a distinct row** — a "tool" tag, the
  tool's display name, the period ("· Sep 2026") — with a spinner until its result lands, then its
  one-line summary ("14 categories · €2,184").
- **When the answer starts:** the block collapses itself to "▸ Worked for 4s · 2 lookups".
- **Every level collapses:** the block; each tool row opens to show **what it returned as a small
  table** (not JSON).
- **Stopped:** header reads "Stopped after 3s"; the steps that ran stay.
- **Without thinking** (the model gives none): the block holds only the tool rows.
- **Reopened later:** the same block from history, minus timing — "▸ 2 lookups". **(call)**
- **Stopped turns when reopened (call).** Two kinds:
  - *Stopped by the server* (§5.1): the turn ends with a partial answer, so it is persisted with a
    **stopped flag** (on the final assistant message in the checkpoint) and the history carries it;
    reopened, the header reads "▸ Stopped · 2 lookups".
  - *Stopped by the user:* the existing rule in `chat.md` §2 holds — reopening shows the question
    with no answer. The history rebuild **omits the activity of a turn with no final answer**, so no
    orphaned tool rows or spinners appear, even though the checkpoint holds the tool-call message
    and any earlier results.
- **Money formatting (call).** Amounts in summary lines and tables are sent as numbers and formatted
  by the web with `formatAmount`, so they follow the browser's currency-symbol preference
  ([`transactions.md`](../../docs/product/features/transactions.md) §4). The model's prose writes €,
  since the data is EUR; a user who chose another symbol sees € in prose only. That preference is
  itself an open question in `transactions.md` §6 and in TODO *Web — the currency symbol*.

Built on the Finsight tokens and the chat's existing components (assistant-ui 0.15: tool-call and
reasoning message parts). The `finsight-design` and `web-app-patterns` skills apply.

## 8. Wire contract

- **The stream** (`POST /chatbot/chat/{id}/stream`, `StreamResponse`) carries only text today. It
  gains typed events for: reasoning text, tool started (call id, tool, display label incl. period),
  tool finished (call id, summary parts and the figures for the table as numbers, ok/error), and
  text — then done, with the stopped flag when the server ended the turn (§5.1).
  The exact event schema is the builder's; it is a breaking change for
  `web-app/apps/web/src/lib/chat/stream-chat.ts`, which changes with it. The stream route is
  `tags=["streaming"]` (not in the generated client), so the event schema should still be defined
  as Pydantic models and documented.
- **History** (`GET /chatbot/chat/{id}/messages`, `ConversationHistory`) returns, per assistant
  reply, the same parts (reasoning, tool calls with summary and figures, text), so the client
  rebuilds the block, plus the stopped flag; a turn with no final answer contributes no parts (§7).
  Today `_process_messages` drops everything but text and joins a turn's assistant messages. This
  changes the OpenAPI contract → `make gen-contract`.
- **`POST /chatbot/chat/{id}`** (non-streamed) keeps returning the final text; tools still run.
- The figures for a tool row's table are a **display copy** of the result, sized for the UI;
  the model's `ToolMessage` content is what §3 describes. Whether these are one structure or two is
  the builder's call, as long as both are bounded.

## 9. Thinking

**Reasoning effort is a setting (user).** The chat agent's reasoning effort comes from the LLM
settings (`app/core/config.py`, the `llm` group; e.g. `CHAT_REASONING_EFFORT`, values as OpenRouter
accepts them), **default `medium`**, in `server/.env.example` with a comment. Today the effort is
hard-coded per model in the `LLMRegistry` (`gpt-5-mini` at `low`). The setting applies to the chat
agent's calls; the other callers of the registry (insights writer, labeler, CSV mapper, titles,
memory) keep their current effort. How the setting meets the registry entry, and what a fallback
model does with it, is the builder's call, as long as a fallback never fails because of it.

`process_llm_response` currently discards reasoning blocks, and LangChain's OpenAI client may not
pass OpenRouter's `reasoning_details` through at all. **First task: a spike** — at the configured
effort, does `openai/gpt-5-mini` via OpenRouter stream readable reasoning (summaries)?
- **If yes through the current client:** stream and checkpoint it.
- **If only through a client change** (e.g. `extra_body`, the Responses API, a thin adapter): in
  scope **(call)**, provided it is limited to the chat agent's path or proven harmless to the other
  registry callers by their existing tests.
- **If not at all:** the activity block shows tool rows only and nothing else in this design changes;
  add TODO *chat — show the model's thinking*.

The spike's result is written into the plan before the reasoning work is planned in detail; it does
not need to come back to the user unless the only route is changing the shared client for every
caller. Either way the outcome and the setting go in `chat.md`. If reasoning blocks are kept in
history they must round-trip to the provider as it expects (OpenRouter asks for `reasoning_details`
to be sent back unmodified around tool calls), and §5.4's trim must cope with them.

## 10. Plumbing and the ride-along TODOs

- **Where the tools live (call).** `app.agents` may not import a module (contract R2). The tools are
  built in the **`conversation` module** — R6 already places `analytics` and `transaction` below it
  ("step 7's chat tools call it", `server/pyproject.toml`) — and injected into the chatbot agent at
  startup (`initialize_agents` / `AGENT_REGISTRY` path). The agent package keeps the loop, the
  prompt and generic tool handling; it knows nothing finance-specific beyond what is injected.
  `search_transactions` needs a new public read on `transaction_service`; R1 means it is reached
  through the `transaction` package root.
- **DB connection (TODO).** `UserConversation` opens the request's `DbSession`; the route then awaits
  the model with the connection idle in transaction. Fix as the TODO says: read what the call needs
  (ownership), release the request session before the model call, and give the turn's tools a
  short-lived session from `request.app.state.session_factory` (the stream body must not use the
  request session anyway — `server/CLAUDE.md`). Precedent: `_release_connection` in
  `insights/service.py` and `transaction/imports/service.py`. Applies to the chat, stream and title
  routes. Close the TODO entry.
- **Model name after a fallback (TODO).** Metrics labels and the `llm_response_generated` log use
  the model that answered (`response_metadata`), not `current_model_name()`. Close the TODO entry;
  *every LLM call starts at the default model* stays open.
- **Failed conversation create (TODO).** Add the `ChatRuntimeProvider` test the TODO describes
  (create answers 500 → exchange cleared, text back in the composer). Remove that bullet.
- Langfuse tracing covers tool calls as spans with arguments and results (they are the eval
  ticket's raw material). Tool arguments stay truncated in logs (`TOOL_ARGS_LOG_LIMIT`).

## 11. Constraints

- Server conventions in `server/CLAUDE.md` and the `server-patterns` / `server-testing` skills;
  web conventions in `web-app/CLAUDE.md` and `web-app-patterns` / `web-app-testing`.
- Import contracts R1/R2/R6 and the module tests stay green.
- Ownership: no tool takes a user id; a test proves a tool run under user A cannot return user B's
  rows.
- `server/openapi.json` and the generated client are regenerated, never hand-edited.
- Stop / disconnect keeps working: a stop mid-tool still leaves a usable conversation
  (`drop_unanswered_tool_calls`), and parallel tool execution must not break that.
- Erasure is unaffected: tool results live in checkpoints, which erasure already deletes; memory is
  deleted by `delete_user_memory`.
- The pre-push hook is the only gate for `web-app/` (no web CI).

## 12. Left to the builder

Exact tool names and argument schemas; the step-cap and token-budget numbers; the stream event
schema; how the per-turn history cache and short-lived session are threaded (config, context var,
a per-turn object); the system prompt wording; the custom-instructions wording; display names and
summary wording per tool; component structure of the activity block; how the elapsed timer is kept
client-side; how the "stopped" partial answer is produced.

## 13. Testing expectations

- Unit: each tool's wrapping (period → `DateRange`, bounded output, summary line), argument
  validation messages, `search_transactions` aggregation and grouping, the context builder (current
  turn never trimmed, old tool results stubbed), repeat detection and step cap, memory receives user
  messages only, history parts reconstruction.
- Integration: a turn with a mocked model that calls tools against a seeded user, through the route,
  ownership across two users, connection released before the model call.
- Web: the stream parser for the new events, the activity block's states (working, collapsed,
  expanded, stopped, no-thinking, from history), the failed-create test.
- Evaluation of answer quality is **not** here (§2).

## 14. Docs in the PR that completes it

- `chat.md`: §2 (what the user can do: finance questions, the activity block), §4 rules (figures only
  from tools, period naming, memory scope, web search removed, limits), §5/§6 (close "wire the
  finance tools?", "web search?", update "scope of memory").
- `conversation.md` stays (no schema change), unless the history parts deserve a decision line.
- `docs/architecture/` where the agent/module injection pattern is described (server.md or the
  agents section), and `server/CLAUDE.md` **Agent Architecture** if the injection changes it.
- `TODO.md`: close the three ride-along entries; add **chat — conversation summaries** and, if the
  spike says no, **chat — show the model's thinking**.
- `ROADMAP.md`: the row moves with the work; the evaluation ticket gets its own row via the
  `roadmap-planner` skill.
- This spec and its plan are deleted in that PR.

## 15. Risks

- **Thinking may not be available** in readable form → designed to degrade (§9).
- **Medium effort costs more and is slower** per model call, and a turn may make several; the step
  cap (§5.1) bounds it, and the setting can be lowered without a deploy of code.
- **gpt-5-mini tool-calling quality** with seven tools is unmeasured; tool descriptions may need
  iteration, and without evals that is judged by hand on a seeded account.
- **Contract churn:** the history response changes shape; anything else reading it breaks loudly
  (good), but the web chat must land in the same PR.
