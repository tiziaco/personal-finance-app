# Chat

**Status:** shipped · **Owner:** Tiziano · **Last updated:** 20 Oct 2026
**Scope:** the assistant the user can talk to — conversations, messages, memory. Legacy
v1.0 shipped the **backend** only: it had no chat screen. The port rebuilt the backend
(the `conversation` module and its agent) and gave the assistant a screen (shipped in
roadmap step 3); step 7 gave it tools over the user's own transactions.
**Data model:** [`../../data-model/conversation.md`](../../data-model/conversation.md)
(conversations only; the tools add no table — their results live with the agent's checkpoints).
**Related:** [`account.md`](./account.md) (erasure) · [`insights.md`](./insights.md) ·
PRD [§8](../prd-mvp.md#8-chat).

---

## 1. Who and why

Anyone who would rather ask than browse: "how much did I spend on food last month?" The
assistant is meant to answer from the user's own transactions and to remember what the user
has told it.

## 2. What the user can do

- **Start a conversation** from Chat in the sidebar. The reply streams in as it is
  written, and Markdown is rendered.
- **Stop** a reply. A stopped reply stays on screen, marked "Stopped", until the next send
  or until the user leaves, and is not saved: reopening the conversation shows the
  question with no answer.
- **Find a conversation again.** Conversations are listed newest first, under a title the
  assistant writes after the first reply. **Rename** and **delete** one at a time.
- **Read the history** of a conversation, or **clear** it (API only).
- **Ask about their money** — "where did my money go last month?", "how much at Lidl on
  Tuesdays?", "how can I improve my savings rate?" — and get an answer from their own
  transactions, with advice that points at their own numbers.
- **See what the assistant did.** Above each reply an activity block shows, while the
  assistant works, a live step label with an elapsed timer, its thinking when the model
  provides it (rendered as Markdown, muted), and each lookup as a row that opens to a
  small table of what it returned. When the answer starts the block collapses to "Worked
  for 4s · 2 lookups", and keeps that header, and whatever the user opened, when the saved
  history replaces the streamed reply; reopened later it reads "2 lookups", without the
  timing. A reply the server cut short reads "Stopped".
- **Send a message** over the API and get the reply in one piece, or **stream** it. The
  stream carries typed events: the model's text, its reasoning, and each lookup starting
  and finishing.
- **Be remembered.** The assistant keeps long-term memory of facts the user has told it
  and reads it back in later conversations.

A message is 1 to 3,000 characters and may not contain script tags or null bytes. These
rules sit on the request, so a bad input is a 422; reading the history never fails on the
length or content of a reply.

## 3. The fields

A conversation has a name and an owner; its messages live with the agent, not in the
conversation table. A user's memory is stored by the memory service, keyed by the user.

## 4. Rules and edge cases

- **Private by construction.** Another user's conversation answers "not found", the same as a
  missing one.
- **Figures come from tools, never from the model.** The assistant has seven read-only
  lookups: spending overview, spending by category, top merchants, recurring costs,
  spending behaviour, unusual spending (each the analytics library's own method, so its
  numbers are the dashboard's and the analytics page's) and a transaction search (merchant
  text, dates, categories, amounts, recurring only, weekday; it returns the count and total
  of the matches, optionally grouped by month (in date order), merchant, category or weekday, and a capped
  sample of rows). It filters the same rows the analytics tools see, so it agrees with them;
  money in and money out are reported apart, and a zero amount counts as neither. A figure
  must come from a lookup made in the same turn: the lookups of an earlier turn are
  replaced by a one-line note in what the model is sent, and memory is never a source of
  figures. With no transactions it says so and points to CSV import.
- **Every answer names its period** the way the dashboard does, and ranges are whole
  finished months, the month in progress apart as month-to-date
  ([`analytics.md`](./analytics.md) §2). Each turn the model is told today's date, the last
  finished month and the span the data covers, so a question about a period with no data is
  answered "you have no transactions before …". When the last finished month has no
  transactions, it is also told the latest finished month that has some, which "the last N
  months" count back from as on the dashboard, so it says the empty month has none rather
  than calling the earlier one "last month".
- **The savings rate is the analytics page's.** Analytics decides income and expense by
  sign alone, so money moved into Savings & Investments counts as spending and lowers the
  rate. When the question is about saving or investing, the assistant shows that category's
  amount beside the rate and says so; it never computes an adjusted rate. Holdings and
  returns are out of scope: investments are seen only through transactions.
- **It only reads.** It cannot recategorise or change anything from chat. It knows the
  data comes only from CSV import and transactions added by hand, and offers no bank
  connection.
- **A bad lookup corrects itself.** A call with invalid arguments ("category must be one
  of …", "no data before March 2025") goes back to the model as that call's result and it
  tries again. A crash inside a lookup reaches the model as a fixed message, never the
  exception text. When the user's history cannot be loaded, the turn is still answered
  without what the model is told each turn about the data's span; a lookup then fails as a
  crash does. Independent lookups in one step run together.
- **A turn is bounded.** After `CHAT_MAX_STEPS` (default 8) model calls with lookups, or
  the same lookup with the same arguments twice, the turn ends with an answer written from
  what it has and marked stopped. The run's LangGraph recursion limit follows the setting
  (twice the steps, plus three), so the cap, never the recursion limit, is what ends a turn.
- **Thinking is a setting.** `CHAT_REASONING_EFFORT` (default `medium`; the other model
  callers keep their own effort) sets how hard the model reasons. At any effort above `low`
  the model streams a readable summary of its reasoning (the chat's own model client asks for summaries); the
  summaries vary from turn to turn and are absent at `low`, and the block shows only the
  lookups then. Reasoning of earlier turns is not sent back; within a turn it is.
- **What the model is sent is bounded.** The reply may use `CHAT_REPLY_MAX_TOKENS` (8000,
  thinking included); the history is trimmed to `CHAT_HISTORY_MAX_TOKENS` (24000). The
  current turn is never trimmed; earlier turns are dropped oldest first, so a very long
  conversation forgets its beginning — there is no summary.
- **An empty model reply fails the turn**, as any other failure does.
- **Memory holds who the user is, not figures.** Long-term memory is fed only the user's own
  messages, this turn's, never replies or tool results, and extraction is told to keep
  goals, circumstances and preferences ("saving for a flat", "rent fixed until March") and
  to drop amounts and anything describing a period's activity. The second half is a model
  following instructions, best effort.
- **No web search.** The assistant has no way to search the web: advice comes from the
  user's data, general know-how is in the model, and the user's figures never leave the
  app for a search engine. Only the LLM provider sees them.
- **A conversation is erased with the account**, with its history and the long-term memory;
  see [`account.md`](./account.md).
- **A reply that fails mid-stream** shows "The assistant couldn't reply. Try again."
  Server text is never shown. Its activity block keeps the plain "Worked for" header:
  "Stopped" is for a reply the user or the server stopped.
- **Leaving a conversation mid-reply stops the model call.** The stream route returns
  sse-starlette's `EventSourceResponse`, which listens for the client disconnect at every
  ASGI spec version and cancels the generator, so the model call stops. (Starlette's own
  `StreamingResponse` stops listening at ASGI spec 2.4; uvicorn reports 2.3, so the earlier
  route was cancelled in practice too. A test pins the behaviour at 2.4.) The frames are
  unchanged, plus periodic `: ping` comments.
- **Stopping a reply while a lookup runs leaves the conversation usable.** The
  model's tool-call message is checkpointed before the tool runs, so a stop there leaves
  a call with no result, which providers reject with a 400 on every later turn.
  `drop_unanswered_tool_calls` (`app/agents/graph.py`) removes such a call, keeping any
  text written beside it, before every model call. Reopening a stopped turn shows the
  question alone: the history leaves out the activity of a turn with no final answer.
- **Every LLM call goes through OpenRouter** (`OPENROUTER_API_KEY`) — the agent, titles and
  memory. `LLM_BASE_URL` defaults to OpenRouter and model names are OpenRouter ids
  (`openai/gpt-5-mini`); `server/.env.example` is the reference. An id without its
  provider prefix (`gpt-5-mini`) fails at startup, so an env file written for the OpenAI
  API cannot run on a silent fallback model. With the key unset, mem0 is given a
  placeholder rather than an empty key, which it would replace with `OPENAI_API_KEY` from
  the environment and send to OpenRouter: memory search and writes then fail and are
  logged, and erasure, which makes no model call, still deletes the user's memories.
- Chat endpoints are rate limited per user.

## 5. Not built

Summaries of long conversations (see [`TODO.md`](../../TODO.md)); a lookup over stored
insights; free-form questions beyond the seven lookups; web search; file or image input;
voice; sharing a conversation; clearing history from the screen and suggested prompts
(both deferred by decision on 13 Oct 2026).

## 6. Open questions

- **Where does the user see or delete what the assistant remembers** short of deleting
  the account? Memory is now limited to goals, circumstances and preferences, but there
  is still no screen for it.
