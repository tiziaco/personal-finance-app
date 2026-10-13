# Chat screen — design

**Roadmap row:** 3 Chat screen · **Branch:** `feat/chat-screen` → PR into `template-base`
**Date:** 13 Oct 2026 · **Reads:** [`chat.md`](../../docs/product/features/chat.md),
[`data-model/conversation.md`](../../docs/data-model/conversation.md), `TODO.md` **Server — the
chat stream ignores a client disconnect** (WS7)

## Intent

Give the existing assistant a screen. The user opens **Chat** in the sidebar, starts a
conversation, watches the reply stream in, stops it if they want, finds the conversation
again later under an LLM-written title, and renames or deletes it. Closing the tab mid-reply
stops the model call on the server (WS7). The assistant itself is unchanged in what it can
do — web search and memory, no finance tools (step 7).

In the same step, by the user's decision: **every LLM call moves to OpenRouter** — the agent,
titles, mem0's extraction model and mem0's embedder. The models stay the same OpenAI models,
addressed through OpenRouter. There are no existing memories to preserve.

**Out of scope:** clear history in the UI, suggested prompts, Settings content, "delete all
chats", edit / regenerate / branching, attachments, finance tools.

## Constraints (from the brief)

- No migration, no edit to `alembic/env.py`, `modules/account/`, `conversation/handlers.py`,
  `main.py`, `api/v1/api.py`, the import-linter contracts or `api/middlewares/`.
- The stream route keeps its path, `operation_id="streamChatMessage"`, `tags=["streaming"]`,
  event shape and middleware; no `response_class` that changes its OpenAPI entry.
- The shared inset container in `(dashboard)/layout.tsx` is unchanged.
- `pyproject.toml` gains only the `sse-starlette` dependency line; lockfiles and the generated
  contract change only through `uv lock`, `pnpm install`, `make gen-contract`.
- Existing test fixtures are not edited; new ones sit beside them.

Files touched outside the brief's ownership list, but on neither step's list:
`app/agents/` (messages, base agent, chatbot agent, memory factory), `app/integrations/llm/`,
`app/core/config.py`, `server/.env.example`, root and server
`CLAUDE.md`, `server/README.md`, and `@app/api-client` (one export). The orchestrator is told
before execution starts.

---

## Server

### S1 — WS7: stop the stream on a client disconnect

`modules/conversation/router/chatbot.py`:

- Add `sse-starlette` to `[project].dependencies`; `uv lock`.
- `chat_stream` returns `EventSourceResponse(event_generator(), sep="\n")`. The generator yields
  `{"data": json.dumps(response.model_dump())}`, so each event on the wire stays
  `data: {"content": ..., "done": ...}\n\n`.
- On disconnect sse-starlette cancels the generator; `CancelledError` propagates into
  `agent.get_stream_response`, the graph and the HTTP call to the model. The generator gains
  `except asyncio.CancelledError:` that logs `stream_chat_client_disconnected` and re-raises.
  The existing `except Exception` branch is untouched (it does not catch `CancelledError`).
- sse-starlette's periodic `: ping` comment lines are accepted; SSE clients ignore comments.
- Decorator, path, `operation_id`, tags and middleware unchanged; `make check-contract` proves
  the route's OpenAPI entry did not move.

### S2 — stream only the model's text

`agents/base/agent.py`, `get_stream_response`: `stream_mode="messages"` emits every message a
node produces, including `ToolMessage`s, so web-search results were streamed as reply text
(and vanished from history on reload). Yield `token.content` only when the token is an AI
message chunk. Proven by a failing test first.

### S3 — history cannot fail on its own content

`agents/messages.py`: `Message` keeps `role` and `content` (`min_length=1`) and loses
`max_length=3000` and the script-tag / null-byte validator. Those are rules about user input
and move onto `ChatRequest` in `conversation/schemas.py` (which already carries the 1–3,000
length). Effects: a reply over 3,000 characters, or one quoting `<script>` in a code block, no
longer turns `GET …/messages` into a 500; a bad input is a 422 instead of a 500.

### S4 — LLM-written titles

- **Route** (`router/conversation.py`): `POST /conversation/conversation/{conversation_id}/title`,
  `operation_id="generateConversationTitle"`, CHAT rate limit, `UserConversation` ownership,
  returns `ConversationResponse`.
- **Service:** `ConversationService.generate_title(session, conversation, agent)`:
  1. `conversation.name` non-empty → return it unchanged.
  2. Read history (`agent.get_chat_history`); no user message or no assistant reply → return
     unchanged.
  3. `title = await agent.generate_title(first_user_message, first_reply)`.
  4. Save through `update_conversation_name`; return the row.
- **Agent:** `ChatbotAgent.generate_title(user_text, reply_text) -> str` calls a **tool-free**
  client (`LLMRegistry.get(current model)`, not the tools-bound `llm_service`), with a short
  prompt asking for a title of at most 6 words, no quotes, no trailing punctuation. Inputs
  are truncated (≈1,000 characters each). The result is stripped of quotes and whitespace and
  capped at 100 characters (the rename limit); an empty result counts as a failure.
- **Failure:** any exception from the model → log `conversation_title_generation_failed`,
  return the conversation unchanged with 200. A title is cosmetic; the client retries after
  the next completed reply.
- `app.agents` does not import the module (contract R2); the module calls the agent it already
  receives through `ChatbotAgentDep`.

### S5 — list order

`GET /conversations` returns newest first (`ORDER BY created_at DESC`); the repository and
service docstrings say so.

### S6 — OpenRouter for every LLM call

- **Config** (`core/config.py`, `LLMSettings`): `OPENAI_API_KEY` → `OPENROUTER_API_KEY`; new
  `LLM_BASE_URL: str = "https://openrouter.ai/api/v1"`; `DEFAULT_LLM_MODEL` default
  `openai/gpt-5-mini`. `MemorySettings` defaults: `MODEL = "openai/gpt-5-nano"`,
  `EMBEDDER_MODEL = "openai/text-embedding-3-small"`. `EvaluationSettings`: `LLM` default
  `openai/gpt-5`, `BASE_URL` default OpenRouter, the empty-key fallback reads
  `OPENROUTER_API_KEY`.
- **Registry** (`integrations/llm/service.py`): entries renamed `openai/gpt-5-mini`,
  `openai/gpt-5`, `openai/gpt-5-nano`, `openai/gpt-4o`, `openai/gpt-4o-mini`, params unchanged.
  `_build` passes `base_url=settings.llm.LLM_BASE_URL` and the OpenRouter key; it stays the
  one site that reads the credential, and it still constructs no client at import.
- **mem0** (`agents/shared/memory/factory.py`): the `openai` LLM and embedder configs get the
  OpenRouter base URL and key explicitly, instead of mem0 reading `OPENAI_API_KEY` from the
  environment. The exact mem0 2.x config keys are checked against the installed version.
  `_memory_llm_config`'s gpt-5 detection already strips a `provider/` prefix.
- **Env and docs:** `server/.env.example` renames the variable (compose and CI do not name it);
  `test_service_import.py` empties `OPENROUTER_API_KEY`. The user edits their own
  `server/.env.development` (delete `OPENAI_API_KEY`; `DEFAULT_LLM_MODEL=openai/gpt-4o-mini`).

---

## Web

### W1 — routes and layout

All under `apps/web/src/app/(dashboard)/chat/`:

| File | Role |
|---|---|
| `layout.tsx` | Two-pane shell (conversation column + thread) and `ChatSessionProvider`. A layout persists across its pages, so a stream begun on `/chat` survives `router.replace` to `/chat/[id]`. |
| `page.tsx` | New chat: welcome state over the composer. No row exists until the first send. |
| `[conversationId]/page.tsx` | One thread. A 404 shows "This conversation doesn't exist" with a link to a new chat. |
| `loading.tsx` | Skeleton of both panes. |

The chat route sizes itself to the viewport inside the existing wrapper so the thread scrolls
in assistant-ui's `ThreadPrimitive.Viewport` with the composer pinned beneath it. All of it
lives under `chat/`; Home is checked visually to be unchanged.

`lib/hub-nav.ts`: `{ title: "Chat", url: "/chat", icon: MessageSquareIcon }` after Home.

### W2 — components (`apps/web/src/components/chat/`)

assistant-ui is used through **`ExternalStoreRuntime`** and its **headless primitives**, styled
with `@app/ui`. The registry's styled `thread` is not installed (it pulls attachments, voice,
reasoning, tool UIs, suggestions and feedback).

- `conversation-list.tsx` — ours. "New chat", conversations newest first, active highlighted,
  empty name shown as "New chat". Row `⋯` menu: **Rename** (inline input; Enter saves, Esc
  cancels) and **Delete** (confirm dialog; deleting the open one navigates to `/chat`). On
  mobile (`useIsMobile`) the column lives in the existing `Sheet` behind a header button.
- `thread.tsx` — `ThreadPrimitive.Root` / `Viewport` / `Messages` / `Empty`, scroll-to-bottom.
- `chat-message.tsx` — `MessagePrimitive`. User: right-aligned plain text bubble. Assistant:
  left, `markdown-text.tsx`, Copy (`ActionBarPrimitive.Copy`); a "Stopped" or error marker
  when the session says so. No edit, regenerate or branch picker.
- `markdown-text.tsx` — `MarkdownTextPrimitive` + `remark-gfm`, an element → Tailwind class
  map, no raw HTML, links in a new tab.
- `composer.tsx` — `ComposerPrimitive.Input` (auto-grow, `maxLength` 3000, counter near the
  limit), Send ↔ **Stop** (`ComposerPrimitive.Cancel`) while running.

Dependencies in `apps/web`, pinned exactly: `@assistant-ui/react`,
`@assistant-ui/react-markdown`, `remark-gfm`. No new `@app/ui` primitive.

### W3 — the SSE client (`apps/web/src/lib/chat/stream-chat.ts`)

`streamChat({ conversationId, message, token, signal })` — an async generator:

- `POST {base}/api/v1/chatbot/chat/{id}/stream`, `Authorization: Bearer`, JSON body
  `{ message }`, `signal`. Base URL from `resolveBaseUrl`, newly exported by `@app/api-client`.
- Non-2xx → throws `ApiError(status, body, requestId)`, as the generated mutator does.
- Parses SSE from the body stream: frames split on a blank line, `:` comment lines ignored,
  `data:` lines joined and `JSON.parse`d, validated by a two-field Zod schema
  `{ content: string, done: boolean }` and yielded. This is the one hand-written API payload
  type: streaming routes are excluded from generation and WS7 forbids changing the route's
  OpenAPI entry. A comment points at `StreamResponse` in `server/app/modules/conversation/schemas.py`.

### W4 — the session (`ChatSessionProvider`)

Holds the in-flight exchange `{ conversationId, userText, replyText, status }` (`status`:
`running | stopped | error`) and its `AbortController`, and builds `useExternalStoreRuntime`:

- **`messages`** = history from `useListChatMessages(activeId)` (mapped by `convertMessage`)
  followed by the in-flight exchange when it belongs to the active conversation.
- **`isRunning`** = status is `running`.
- **`onNew(text)`** — on `/chat`: `createConversation`, prepend the row to the list cache,
  `router.replace('/chat/{id}')`. Then stream, appending each chunk to `replyText`.
- **`onCancel`** — abort.
- **On completion** — refetch history, then drop the in-flight exchange (no duplicate flash).
  If the conversation's name is empty, call `generateConversationTitle` and write the result
  into the list cache; this repeats after each completed reply until a name exists.
- **Leaving** — switching conversation, starting a new chat, or unmounting `/chat` aborts.

Product behaviour, agreed:

- **Stopped by the user:** the partial reply stays visible, marked "Stopped", until the next
  send or leaving. It is not saved — LangGraph checkpoints only a finished reply — so on
  reopening, the user's message shows with no answer.
- **Failed mid-stream:** the server signals failure as a final event with `done: true` and
  non-empty `content`. The client treats that as an error and shows its own copy, "The
  assistant couldn't reply. Try again." Server text is never rendered.
- **HTTP error** (429, 404, 5xx): the same status → copy toast `QueryProvider` uses; the
  composer re-enables and the typed message is kept.
- Rename and delete use the generated mutation hooks and update the list cache.

---

## Testing

**Server** (pytest, `server-testing` conventions):

- WS7: drive the ASGI app with a `receive` that returns `http.disconnect` after the first
  chunk and a fake agent that records cancellation → cancelled promptly. A second test pins
  the normal wire format, including the final `done: true` event.
- S2: a fake graph emitting AI chunk, `ToolMessage`, AI chunk → only AI text.
- S3: history with a >3,000-character reply → 200; `ChatRequest` with `<script>` or a null
  byte → 422.
- S4: empty name → generated and saved (agent mocked); named → unchanged, agent not called;
  no history → unchanged; model raises → 200 unchanged; another user's conversation → 404;
  quotes stripped, length capped.
- S5: newest first.
- S6: `_build` passes base URL and OpenRouter key; mem0 config carries both for LLM and
  embedder; existing tests naming `OPENAI_API_KEY` move to the new setting.
- `make check-contract` clean; the stream route's entry unchanged; `Message`, `ChatRequest`
  and the new title route are the only contract changes.

**Web** (Vitest, co-located):

- `stream-chat.test.ts`: frame split across chunks; several frames per chunk; pings ignored;
  non-2xx → `ApiError`; abort stops reading; `done` with content → error.
- Session: first send on `/chat` creates, replaces the URL and streams; cancel aborts; title
  requested only while the name is empty; history replaces the in-flight exchange after done.
- `conversation-list.test.tsx`: "New chat" fallback, rename, delete with confirm, deleting the
  active conversation navigates to `/chat`.

**Manual**, on slot 2 (web 3020, API 8120): stream a reply; stop mid-reply and see
`stream_chat_client_disconnected` in the server log; a web-search question shows no raw
results; the title appears; rename; delete; mobile width; Home's layout unchanged.

## Docs (in the PR; spec and plan deleted)

- `chat.md`: the screen ships — what the user can do, titles, Stop and what a stopped reply
  leaves; drop the mid-stream-disconnect edge case and the "no screen" note; OpenRouter.
- `data-model/conversation.md`: D3 titles (empty name = untitled, generated on the client's
  request after a completed reply); list order; `Last updated`.
- `TODO.md`: delete the WS7 entry.
- OpenRouter: root `CLAUDE.md`, `server/CLAUDE.md` (settings example), `server/README.md`,
  `.env.example` (no doc under `docs/` names the key today).
- `architecture/web-app.md`: chat uses assistant-ui's `ExternalStoreRuntime` over the
  generated hooks; its SSE client is the sanctioned hand-written fetch.
- `ROADMAP.md`: row 3 → `complete` with the PR link; its description adds "moves the LLM
  provider to OpenRouter".
