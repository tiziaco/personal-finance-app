import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ConversationList } from "./conversation-list"
import { CHAT_COPY } from "./copy"

const mocks = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
  usePathname: () => "/chat",
}))
vi.mock("@app/auth", () => ({
  useAppAuth: () => ({ getToken: async () => "tok" }),
}))

const rows = [
  { conversation_id: "c2", name: "", created_at: "2026-10-13T11:00:00Z" },
  {
    conversation_id: "c1",
    name: "Groceries",
    created_at: "2026-10-13T10:00:00Z",
  },
]
const calls: { method: string; path: string; body?: string }[] = []

beforeEach(() => {
  vi.clearAllMocks()
  calls.length = 0
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const path = new URL(String(input)).pathname
    const method = init?.method ?? "GET"
    calls.push({
      method,
      path,
      body: init?.body ? String(init.body) : undefined,
    })
    if (method === "GET") {
      return new Response(JSON.stringify(rows), {
        headers: { "content-type": "application/json" },
      })
    }
    if (method === "PATCH") {
      const name = new URLSearchParams(String(init?.body)).get("name")
      return new Response(JSON.stringify({ ...rows[1], name }), {
        headers: { "content-type": "application/json" },
      })
    }
    return new Response(null, { status: 204 })
  })
})

function renderList(activeId: string | null = null) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  render(
    <QueryClientProvider client={client}>
      <ConversationList activeId={activeId} />
    </QueryClientProvider>,
  )
}

async function openMenu(rowName: string) {
  const row = (await screen.findByText(rowName)).closest(
    "[data-slot=conversation-row]",
  ) as HTMLElement
  await userEvent.click(within(row).getByRole("button", { name: /options/i }))
}

describe("ConversationList", () => {
  it("lists conversations in server order and labels an untitled one", async () => {
    renderList()
    await screen.findByText("Groceries")
    const links = screen.getAllByRole("link")
    expect(links.map((l) => l.textContent?.trim())).toEqual([
      CHAT_COPY.newChat,
      CHAT_COPY.untitled,
      "Groceries",
    ])
  })

  it("marks the active conversation", async () => {
    renderList("c1")
    expect(
      await screen.findByRole("link", { name: "Groceries" }),
    ).toHaveAttribute("aria-current", "page")
  })

  it("renames with Enter", async () => {
    renderList()
    await openMenu("Groceries")
    await userEvent.click(
      await screen.findByRole("menuitem", { name: CHAT_COPY.rename }),
    )
    const input = screen.getByRole("textbox", { name: CHAT_COPY.rename })
    await userEvent.clear(input)
    await userEvent.type(input, "Food{Enter}")

    await waitFor(() =>
      expect(calls.some((c) => c.method === "PATCH")).toBe(true),
    )
    expect(
      await screen.findByRole("link", { name: "Food" }),
    ).toBeInTheDocument()
  })

  // A mutate call's own callbacks run only for the latest call: the cache
  // update lives in the hook's options, so an earlier rename still lands.
  it("two renames in a row both land, the first resolving last", async () => {
    let releaseFirst: () => void = () => {}
    vi.mocked(globalThis.fetch).mockImplementation(async (input, init) => {
      const path = new URL(String(input)).pathname
      const method = init?.method ?? "GET"
      if (method === "GET") {
        return new Response(JSON.stringify(rows), {
          headers: { "content-type": "application/json" },
        })
      }
      const id = path.split("/").at(-2)
      const name = new URLSearchParams(String(init?.body)).get("name")
      const body = JSON.stringify({
        ...rows.find((r) => r.conversation_id === id),
        name,
      })
      const respond = () =>
        new Response(body, { headers: { "content-type": "application/json" } })
      if (id === "c1")
        return new Promise<Response>((resolve) => {
          releaseFirst = () => resolve(respond())
        })
      return respond()
    })
    renderList()

    await openMenu("Groceries")
    await userEvent.click(
      await screen.findByRole("menuitem", { name: CHAT_COPY.rename }),
    )
    const first = screen.getByRole("textbox", { name: CHAT_COPY.rename })
    await userEvent.clear(first)
    await userEvent.type(first, "Food{Enter}")

    // "New chat" is also the new-chat link's label: find the row's copy.
    const untitled = (await screen.findAllByText(CHAT_COPY.untitled))
      .map((el) => el.closest("[data-slot=conversation-row]"))
      .find((row) => row !== null) as HTMLElement
    await userEvent.click(
      within(untitled).getByRole("button", { name: /options/i }),
    )
    await userEvent.click(
      await screen.findByRole("menuitem", { name: CHAT_COPY.rename }),
    )
    await userEvent.type(
      screen.getByRole("textbox", { name: CHAT_COPY.rename }),
      "Trip{Enter}",
    )
    expect(
      await screen.findByRole("link", { name: "Trip" }),
    ).toBeInTheDocument()

    releaseFirst()
    expect(
      await screen.findByRole("link", { name: "Food" }),
    ).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Trip" })).toBeInTheDocument()
  })

  // Review Focus 4
  it("an empty or whitespace name sends nothing and keeps the old name", async () => {
    renderList()
    await openMenu("Groceries")
    await userEvent.click(
      await screen.findByRole("menuitem", { name: CHAT_COPY.rename }),
    )
    const input = screen.getByRole("textbox", { name: CHAT_COPY.rename })
    expect(input).toHaveAttribute("maxLength", "100")
    await userEvent.clear(input)
    await userEvent.type(input, "   {Enter}")

    expect(calls.some((c) => c.method === "PATCH")).toBe(false)
    expect(
      await screen.findByRole("link", { name: "Groceries" }),
    ).toBeInTheDocument()
  })

  it("Escape cancels a rename", async () => {
    renderList()
    await openMenu("Groceries")
    await userEvent.click(
      await screen.findByRole("menuitem", { name: CHAT_COPY.rename }),
    )
    await userEvent.type(
      screen.getByRole("textbox", { name: CHAT_COPY.rename }),
      "xyz{Escape}",
    )
    expect(
      await screen.findByRole("link", { name: "Groceries" }),
    ).toBeInTheDocument()
    expect(calls.some((c) => c.method === "PATCH")).toBe(false)
  })

  it("deletes after confirmation, and leaves the conversation if it was open", async () => {
    renderList("c1")
    await openMenu("Groceries")
    await userEvent.click(
      await screen.findByRole("menuitem", { name: CHAT_COPY.delete }),
    )
    const dialog = await screen.findByRole("dialog")
    expect(within(dialog).getByText(CHAT_COPY.deleteTitle)).toBeInTheDocument()
    await userEvent.click(
      within(dialog).getByRole("button", { name: CHAT_COPY.delete }),
    )

    await waitFor(() =>
      expect(calls).toContainEqual(
        expect.objectContaining({
          method: "DELETE",
          path: "/api/v1/conversation/conversation/c1",
        }),
      ),
    )
    await waitFor(() => expect(mocks.push).toHaveBeenCalledWith("/chat"))
    await waitFor(() =>
      expect(screen.queryByRole("link", { name: "Groceries" })).toBeNull(),
    )
  })
})
