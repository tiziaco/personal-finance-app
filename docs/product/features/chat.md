# Chat

**Status:** shipped · **Owner:** Tiziano · **Last updated:** 13 Oct 2026
**Scope:** the assistant the user can talk to — conversations, messages, memory. Legacy
v1.0 shipped the **backend** only: it had no chat screen. The port rebuilt the backend
(the `conversation` module and its agent) and gave the assistant a screen (shipped in
roadmap step 3); finance tools are step 7.
**Data model:** [`../../data-model/conversation.md`](../../data-model/conversation.md)
(conversations only; the finance part is pending, step 7).
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
- **Send a message** over the API and get the reply in one piece, or **stream** it. The
  stream carries only the model's text; tool results such as web search are not streamed.
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
- **What the v1.0 assistant could not do.** It could search the web, but it could **not**
  see the user's transactions: a set of finance tools (spending summary, categories,
  recurring, trends, behaviour, anomalies, merchants, stability) exists in the legacy code,
  but was never given to the assistant. A user asking about their own spending got a
  generic answer.
- **A conversation is erased with the account**, with its history and the long-term memory;
  see [`account.md`](./account.md).
- **A reply that fails mid-stream** shows "The assistant couldn't reply. Try again."
  Server text is never shown.
- **Leaving a conversation mid-reply stops the model call.** The stream route returns
  sse-starlette's `EventSourceResponse`, which listens for the client disconnect at every
  ASGI spec version and cancels the generator, so the model call stops. (Starlette's own
  `StreamingResponse` stops listening at ASGI spec 2.4; uvicorn reports 2.3, so the earlier
  route was cancelled in practice too. A test pins the behaviour at 2.4.) The frames are
  unchanged, plus periodic `: ping` comments.
- **Every LLM call goes through OpenRouter** (`OPENROUTER_API_KEY`) — the agent, titles and
  memory. `LLM_BASE_URL` defaults to OpenRouter and model names are OpenRouter ids
  (`openai/gpt-5-mini`); `server/.env.example` is the reference.
- Chat endpoints are rate limited per user.

## 5. Not built

The assistant reading the user's transactions; file or image input; voice; sharing a
conversation; clearing history from the screen and suggested prompts (both deferred by
decision on 13 Oct 2026).

## 6. Open questions

- **Wire the finance tools?** Giving the assistant the analytics tools is what makes it
  useful. It is the main product decision here, and it belongs to step 7.
- **Scope of memory.** What may the assistant remember about someone's money, and where does
  the user see or delete it short of deleting the account?
- **Web search.** Should an assistant with access to financial data also search the web?
