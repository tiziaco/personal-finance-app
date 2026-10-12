# Chat

**Status:** shipped · **Owner:** Tiziano · **Last updated:** 12 Oct 2026
**Scope:** the assistant the user can talk to — conversations, messages, memory. Legacy
v1.0 shipped the **backend** only: it had no chat screen. The port rebuilds the backend
(already present in this repo as the `conversation` module and its agent) and gives the
assistant a screen and finance tools in sub-projects 2 and 3.
**Data model:** [`../../data-model/conversation.md`](../../data-model/conversation.md)
(conversations only; the finance part is pending, sub-project 2).
**Related:** [`account.md`](./account.md) (erasure) · [`insights.md`](./insights.md) ·
PRD [§8](../prd-mvp.md#8-chat).

---

## 1. Who and why

Anyone who would rather ask than browse: "how much did I spend on food last month?" The
assistant is meant to answer from the user's own transactions and to remember what the user
has told it.

## 2. What the user can do (v1.0 API)

- **Start a conversation**, **rename** it, **delete** it, and **list** their conversations.
- **Send a message** and get the reply in one piece, or **stream** it as it is written.
- **Read the history** of a conversation, or **clear** it.
- **Be remembered.** The assistant keeps long-term memory of facts the user has told it
  and reads it back in later conversations.

A message is 1 to 3,000 characters and may not contain script tags.

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
- **No screen.** The legacy settings dialog had a "Delete all chats" button that did
  nothing, and a "Memory usage" figure that was always 0 MB.
- **A conversation is erased with the account**, with its history and the long-term memory;
  see [`account.md`](./account.md).
- **A client that leaves mid-stream** does not stop the model call
  ([`../../TODO.md`](../../TODO.md), **Server — the chat stream ignores a client
  disconnect**).
- Chat endpoints are rate limited per user.

## 5. Not built

A chat page; the assistant reading the user's transactions; file or image input; voice;
sharing a conversation.

## 6. Open questions

- **Wire the finance tools?** Giving the assistant the analytics tools is what makes it
  useful. It is the main product decision here, and it belongs to sub-project 2's agent
  work.
- **Is the assistant in the first release's UI**, or does it stay an API until the
  finance pages are done?
- **Scope of memory.** What may the assistant remember about someone's money, and where does
  the user see or delete it short of deleting the account?
- **Web search.** Should an assistant with access to financial data also search the web?
