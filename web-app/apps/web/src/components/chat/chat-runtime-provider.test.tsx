import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest"

import { getListChatMessagesQueryKey } from "@app/api-client/endpoints/chatbot"
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
    return json(await handler(init))
  })
})

function renderChat({ staleTime = 0 } = {}) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime } },
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

describe("ChatRuntimeProvider — leaving and refusals", () => {
  // Review Focus 1
  it("switching conversation mid-stream aborts it and does not carry the reply over", async () => {
    mocks.params = { conversationId: "c1" }
    routes["GET /api/v1/chatbot/chat/c2/messages"] = () => ({
      messages: [{ role: "user", content: "older question" }],
    })
    let signal: AbortSignal | undefined
    mocks.stream.mockImplementation(async function* (opts: {
      signal: AbortSignal
    }) {
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
      expect(
        screen.getByRole("textbox", { name: CHAT_COPY.inputLabel }),
      ).toHaveValue("too fast"),
    )
  })
})

describe("ChatRuntimeProvider", () => {
  it("creates a conversation on the first send, replaces the URL and streams the reply", async () => {
    mocks.stream.mockImplementation(() => chunks("Hel", "lo"))
    renderChat()
    await send("hi")

    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/chat/c1"))
    expect(mocks.stream).toHaveBeenCalledWith(
      expect.objectContaining({
        conversationId: "c1",
        message: "hi",
        token: "tok",
      }),
    )
    expect(calls).toContain("POST /api/v1/conversation/conversation")
  })

  // The reply can finish before router.replace commits (a route compiling in
  // dev). The URL still says /chat then, and the thread must not go blank
  // between the exchange being cleared and the conversation's page mounting.
  it("a first send whose reply ends before the URL moves keeps showing the exchange", async () => {
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
    const { rerender, client } = renderChat({ staleTime: 60_000 })
    await send("hi")
    await waitFor(() =>
      expect(calls).toContain(
        "POST /api/v1/conversation/conversation/c1/title",
      ),
    )
    expect(screen.getByText("Hello")).toBeInTheDocument()
    expect(screen.getAllByText("hi")).toHaveLength(1)

    mocks.params = { conversationId: "c1" }
    rerender(
      <QueryClientProvider client={client}>
        <ChatRuntimeProvider>
          <Thread />
        </ChatRuntimeProvider>
      </QueryClientProvider>,
    )

    expect(screen.getByText("Hello")).toBeInTheDocument()
    expect(screen.getAllByText("hi")).toHaveLength(1)
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
      expect(calls).toContain(
        "POST /api/v1/conversation/conversation/c1/title",
      ),
    )
    expect(screen.getAllByText("hi")).toHaveLength(1)
    expect(screen.getAllByText("Hello")).toHaveLength(1)
  })

  it("writes the generated title into the conversation list", async () => {
    mocks.params = { conversationId: "c1" }
    mocks.stream.mockImplementation(() => chunks("Hello"))
    const { client } = renderChat()
    client.setQueryData(getListConversationsQueryKey(), [
      { conversation_id: "c1", name: "", created_at: "2026-10-13T10:00:00Z" },
    ])
    await send("hi")

    await waitFor(() =>
      expect(client.getQueryData(getListConversationsQueryKey())).toEqual([
        expect.objectContaining({ conversation_id: "c1", name: "Groceries" }),
      ]),
    )
  })

  it("does not ask for a title when the conversation already has a name", async () => {
    mocks.params = { conversationId: "c1" }
    mocks.stream.mockImplementation(() => chunks("Hello"))
    routes["GET /api/v1/conversation/conversations"] = () => [
      {
        conversation_id: "c1",
        name: "Named",
        created_at: "2026-10-13T10:00:00Z",
      },
    ]
    const { client } = renderChat()
    // The title check reads the list cache; the list is loaded by the
    // conversation column in the app, so load it here the same way.
    await client.fetchQuery({
      queryKey: getListConversationsQueryKey(),
      queryFn: async () =>
        (
          await fetch("http://localhost:8100/api/v1/conversation/conversations")
        ).json(),
    })
    await send("hi")
    await waitFor(() => expect(mocks.stream).toHaveBeenCalled())
    await new Promise((r) => setTimeout(r, 50))
    expect(calls).not.toContain(
      "POST /api/v1/conversation/conversation/c1/title",
    )
  })

  it("Stop aborts the stream and marks the partial reply as stopped", async () => {
    mocks.params = { conversationId: "c1" }
    let signal: AbortSignal | undefined
    mocks.stream.mockImplementation(async function* (opts: {
      signal: AbortSignal
    }) {
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

  it("opens the exchange before the conversation exists, so a second send is refused", async () => {
    let release: () => void = () => {}
    routes["POST /api/v1/conversation/conversation"] = () =>
      new Promise((resolve) => {
        release = () =>
          resolve({
            conversation_id: "c1",
            name: "",
            created_at: "2026-10-13T10:00:00Z",
          })
      })
    mocks.stream.mockImplementation(() => chunks("Hello"))
    renderChat()
    await send("hi")

    expect(await screen.findByText("hi")).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: CHAT_COPY.stop }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: CHAT_COPY.send }),
    ).not.toBeInTheDocument()

    await send("again")
    expect(
      calls.filter((c) => c === "POST /api/v1/conversation/conversation"),
    ).toHaveLength(1)

    release()
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/chat/c1"))
    // The send runs to its end (the title request) as the only one.
    await waitFor(() =>
      expect(calls).toContain(
        "POST /api/v1/conversation/conversation/c1/title",
      ),
    )
    expect(mocks.stream).toHaveBeenCalledTimes(1)
    expect(mocks.replace).toHaveBeenCalledTimes(1)
  })

  // At the first send the list's cache can be empty (its fetch failed or is
  // still in flight); seeding it then would leave a one-row list.
  it("a first send with no list loaded does not seed a one-row list, and refreshes the list", async () => {
    mocks.stream.mockImplementation(() => chunks("Hello"))
    const { client } = renderChat()
    const invalidate = vi.spyOn(client, "invalidateQueries")
    await send("hi")

    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/chat/c1"))
    expect(client.getQueryData(getListConversationsQueryKey())).toBeUndefined()
    expect(invalidate).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: getListConversationsQueryKey() }),
    )
  })

  it("Stop, then leaving while the conversation is created, does not pull the user back", async () => {
    let release: () => void = () => {}
    routes["POST /api/v1/conversation/conversation"] = () =>
      new Promise((resolve) => {
        release = () =>
          resolve({
            conversation_id: "c1",
            name: "",
            created_at: "2026-10-13T10:00:00Z",
          })
      })
    routes["GET /api/v1/chatbot/chat/c2/messages"] = () => ({ messages: [] })
    const { rerender, client } = renderChat()
    await send("hi")
    await userEvent.click(
      await screen.findByRole("button", { name: CHAT_COPY.stop }),
    )

    mocks.params = { conversationId: "c2" }
    rerender(
      <QueryClientProvider client={client}>
        <ChatRuntimeProvider>
          <Thread />
        </ChatRuntimeProvider>
      </QueryClientProvider>,
    )
    release()

    await waitFor(() => expect(client.isMutating()).toBe(0))
    await new Promise((r) => setTimeout(r, 50))
    expect(mocks.replace).not.toHaveBeenCalled()
    expect(mocks.stream).not.toHaveBeenCalled()
    expect(
      screen.getByRole("textbox", { name: CHAT_COPY.inputLabel }),
    ).toHaveValue("")
  })

  it("Stop before the stream starts ends the send as stopped without streaming", async () => {
    let release: () => void = () => {}
    routes["POST /api/v1/conversation/conversation"] = () =>
      new Promise((resolve) => {
        release = () =>
          resolve({
            conversation_id: "c1",
            name: "",
            created_at: "2026-10-13T10:00:00Z",
          })
      })
    renderChat()
    await send("hi")
    await userEvent.click(
      await screen.findByRole("button", { name: CHAT_COPY.stop }),
    )
    release()

    expect(await screen.findByText(CHAT_COPY.stopped)).toBeInTheDocument()
    expect(screen.getByText("hi")).toBeInTheDocument()
    expect(mocks.stream).not.toHaveBeenCalled()
  })

  it("keeps the user's message once when history refetches mid-stream", async () => {
    mocks.params = { conversationId: "c1" }
    let resume: () => void = () => {}
    mocks.stream.mockImplementation(async function* () {
      yield "Hel"
      await new Promise<void>((resolve) => {
        resume = resolve
      })
      yield "lo"
    })
    const { client } = renderChat()
    await send("hi")
    await screen.findByText("Hel")

    // The graph has started: the server's history now holds the user's message.
    routes["GET /api/v1/chatbot/chat/c1/messages"] = () => ({
      messages: [{ role: "user", content: "hi" }],
    })
    // TanStack notifies observers on a setTimeout(0) batch: let it render.
    await act(async () => {
      await client.refetchQueries({
        queryKey: getListChatMessagesQueryKey("c1"),
      })
      await new Promise((r) => setTimeout(r, 0))
    })
    expect(client.getQueryData(getListChatMessagesQueryKey("c1"))).toEqual({
      messages: [{ role: "user", content: "hi" }],
    })

    expect(screen.getAllByText("hi")).toHaveLength(1)
    resume()
  })
})
