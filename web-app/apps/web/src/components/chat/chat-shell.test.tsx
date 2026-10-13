import { QueryProvider } from "@app/api-client/query-provider"
import { messages } from "@app/core/constants/messages"
import { Toaster } from "@app/ui/sonner"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest"

import { ChatRuntimeProvider } from "./chat-runtime-provider"
import { ConversationPage } from "./chat-shell"
import { CHAT_COPY } from "./copy"

const mocks = vi.hoisted(() => ({ params: { conversationId: "missing" } }))
vi.mock("next/navigation", () => ({
  useParams: () => mocks.params,
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/chat/missing",
}))
vi.mock("@app/auth", () => ({
  useAppAuth: () => ({ getToken: async () => "tok" }),
}))

beforeAll(() => {
  Element.prototype.scrollTo ??= () => {}
  Element.prototype.scrollIntoView ??= () => {}
})

beforeEach(() => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ detail: "Conversation not found" }), {
      status: 404,
      headers: { "content-type": "application/json" },
    }),
  )
})

describe("ConversationPage", () => {
  it("an unknown or foreign id shows not-found with a way out, and no composer", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    render(
      <QueryClientProvider client={client}>
        <ChatRuntimeProvider>
          <ConversationPage />
        </ChatRuntimeProvider>
      </QueryClientProvider>,
    )
    expect(await screen.findByText(CHAT_COPY.notFoundTitle)).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: CHAT_COPY.notFoundAction }),
    ).toHaveAttribute("href", "/chat")
    expect(
      screen.queryByRole("textbox", { name: CHAT_COPY.inputLabel }),
    ).toBeNull()
  })

  it("the 404 is not also toasted over the not-found screen", async () => {
    // The app's real QueryProvider (its query-cache onError is what toasts)
    // and a real Toaster, so a toast would land in the DOM.
    render(
      <QueryProvider>
        <Toaster />
        <ChatRuntimeProvider>
          <ConversationPage />
        </ChatRuntimeProvider>
      </QueryProvider>,
    )
    expect(await screen.findByText(CHAT_COPY.notFoundTitle)).toBeInTheDocument()
    // onError runs before the observers re-render with the error, and sonner
    // renders a toast on its next update: give it a few frames to show up.
    await new Promise((resolve) => setTimeout(resolve, 100))
    expect(screen.queryByText(messages.toasts.notFound)).toBeNull()
  })

  it("a malformed id (422) shows not-found too, with no composer and no toast", async () => {
    vi.mocked(globalThis.fetch).mockImplementation(
      async () =>
        new Response(JSON.stringify({ detail: [] }), {
          status: 422,
          headers: { "content-type": "application/json" },
        }),
    )
    render(
      <QueryProvider>
        <Toaster />
        <ChatRuntimeProvider>
          <ConversationPage />
        </ChatRuntimeProvider>
      </QueryProvider>,
    )
    expect(await screen.findByText(CHAT_COPY.notFoundTitle)).toBeInTheDocument()
    expect(
      screen.queryByRole("textbox", { name: CHAT_COPY.inputLabel }),
    ).toBeNull()
    await new Promise((resolve) => setTimeout(resolve, 100))
    expect(screen.queryByText(messages.toasts.validationError)).toBeNull()
  })

  it("any other history error toasts its status copy and keeps the thread", async () => {
    // A fresh Response per call: QueryProvider retries a 5xx once.
    vi.mocked(globalThis.fetch).mockImplementation(
      async () =>
        new Response(JSON.stringify({ detail: "boom" }), {
          status: 500,
          headers: { "content-type": "application/json" },
        }),
    )
    render(
      <QueryProvider>
        <Toaster />
        <ChatRuntimeProvider>
          <ConversationPage />
        </ChatRuntimeProvider>
      </QueryProvider>,
    )
    // The one retry waits about a second before the query settles as an error.
    expect(
      await screen.findByText(
        messages.toasts.genericError,
        {},
        { timeout: 4000 },
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText(CHAT_COPY.notFoundTitle)).toBeNull()
    expect(
      screen.getByRole("textbox", { name: CHAT_COPY.inputLabel }),
    ).toBeInTheDocument()
  })
})
