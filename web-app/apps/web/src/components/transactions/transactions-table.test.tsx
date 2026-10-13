import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"
import { withNuqsTestingAdapter } from "@app/data-table/url-state/testing"
import {
  useListTransactions,
  useListTransactionCategories,
} from "@app/api-client/endpoints/transactions"
import { TransactionsTable } from "./transactions-table"

const updateMutate = vi.hoisted(() => vi.fn())
const mutationMocks = vi.hoisted(() => {
  const mutation = () => ({ mutate: () => {}, isPending: false })
  return {
    useCreateTransaction: mutation,
    useUpdateTransaction: () => ({ mutate: updateMutate, isPending: false }),
    useDeleteTransaction: mutation,
    useBatchDeleteTransactions: mutation,
  }
})

vi.mock("@app/api-client/endpoints/transactions", async (orig) => ({
  ...(await orig<typeof import("@app/api-client/endpoints/transactions")>()),
  useListTransactions: vi.fn(),
  useListTransactionCategories: vi.fn(),
  ...mutationMocks,
}))

type OnUrlUpdate = NonNullable<
  NonNullable<Parameters<typeof withNuqsTestingAdapter>[0]>["onUrlUpdate"]
>
type UrlUpdateEvent = Parameters<OnUrlUpdate>[0]

const list = vi.mocked(useListTransactions)
const cats = vi.mocked(useListTransactionCategories)

const result = (items: unknown[], total = items.length) =>
  list.mockReturnValue({
    data: { items, total },
    isPending: false,
    isPlaceholderData: false,
    isError: false,
  } as unknown as ReturnType<typeof useListTransactions>)

const renderAt = (qs = "", onUrlUpdate?: OnUrlUpdate) => {
  const Nuqs = withNuqsTestingAdapter({ searchParams: qs, onUrlUpdate })
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={new QueryClient()}>
      <Nuqs>{children}</Nuqs>
    </QueryClientProvider>
  )
  return render(<TransactionsTable />, { wrapper: Wrapper })
}

const row = {
  id: "1",
  date: "2026-03-03",
  merchant: "Späti",
  amount: "-4.50",
  category: "salary",
  confidence: 0.5,
}

describe("TransactionsTable", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    cats.mockReturnValue({
      data: [
        { value: "salary", label: "Salary" },
        { value: "food_groceries", label: "Food & Groceries" },
      ],
    } as unknown as ReturnType<typeof useListTransactionCategories>)
  })

  it("queries the first page for an empty URL", () => {
    result([])
    renderAt()
    expect(list.mock.calls[0][0]).toEqual({ offset: 0, limit: 20 })
  })

  it("forwards the category filter from the URL", () => {
    result([])
    renderAt("?category=salary")
    expect(list.mock.calls[0][0]).toMatchObject({ category: ["salary"] })
  })

  it("shows the first-run empty state", () => {
    result([])
    renderAt()
    expect(screen.getByText("No transactions yet.")).toBeInTheDocument()
  })

  it("shows the no-match state with a clear button", () => {
    result([])
    renderAt("?search=x")
    expect(
      screen.getByText("No transactions match your filters."),
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Clear filters" }),
    ).toBeInTheDocument()
  })

  it("flags low confidence", () => {
    result([row])
    renderAt()
    expect(screen.getByText("50%").className).toMatch(/warning|amber/)
    expect(screen.getByText("Salary")).toBeInTheDocument()
  })

  it("opens the add dialog from the header", async () => {
    result([row])
    renderAt()
    await userEvent.click(
      screen.getByRole("button", { name: "Add transaction" }),
    )
    expect(
      await screen.findByRole("heading", { name: "Add a transaction" }),
    ).toBeInTheDocument()
  })

  it("opens the add dialog from the first-run empty state", async () => {
    result([])
    renderAt()
    await userEvent.click(
      screen.getByRole("button", { name: "Add a transaction" }),
    )
    expect(
      await screen.findByRole("heading", { name: "Add a transaction" }),
    ).toBeInTheDocument()
  })

  it("confirms a delete from the row menu", async () => {
    result([row])
    renderAt()
    await userEvent.click(screen.getByRole("button", { name: "Row actions" }))
    await userEvent.click(
      await screen.findByRole("menuitem", { name: "Delete" }),
    )
    expect(
      await screen.findByText("Delete this transaction?"),
    ).toBeInTheDocument()
  })

  it("recategorises one from the chip", async () => {
    result([row])
    renderAt()
    await userEvent.click(screen.getByRole("button", { name: "Salary" }))
    await userEvent.click(
      await screen.findByRole("menuitemradio", { name: "Food & Groceries" }),
    )
    expect(updateMutate.mock.calls[0][0]).toEqual({
      transactionId: "1",
      data: { category: "food_groceries" },
    })
  })

  it("moves a page past the end back to the last page, with no empty state", async () => {
    // 25 rows, and page 3 (offset 40) is empty: e.g. its only row was deleted.
    list.mockImplementation(
      (params) =>
        ({
          data: { items: params?.offset === 40 ? [] : [row], total: 25 },
          isPending: false,
          isPlaceholderData: false,
          isError: false,
        }) as unknown as ReturnType<typeof useListTransactions>,
    )
    const events: UrlUpdateEvent[] = []
    renderAt("?page=3", (e) => events.push(e))

    await waitFor(() =>
      expect(events.at(-1)?.searchParams.get("page")).toBe("2"),
    )
    // Back must not land on the empty page again.
    expect(events.at(-1)?.options.history).toBe("replace")
    expect(screen.queryByText("No transactions yet.")).not.toBeInTheDocument()
    expect(
      screen.queryByText("No transactions match your filters."),
    ).not.toBeInTheDocument()
  })

  it("shows neither empty state for an empty page while rows exist", () => {
    // page 2 is the last by total, so it does not move; the rows are elsewhere
    result([], 25)
    const { container } = renderAt("?page=2")
    expect(screen.queryByText("No transactions yet.")).not.toBeInTheDocument()
    expect(
      screen.queryByText("No transactions match your filters."),
    ).not.toBeInTheDocument()
    expect(
      container.querySelectorAll('[data-slot="skeleton"]').length,
    ).toBeGreaterThan(0)
  })

  it("shows neither empty state while the clamped page loads over the empty one", () => {
    // keepPreviousData: the empty page stays on screen as placeholder data
    list.mockReturnValue({
      data: { items: [], total: 25 },
      isPending: false,
      isPlaceholderData: true,
      isError: false,
    } as unknown as ReturnType<typeof useListTransactions>)
    const { container } = renderAt("?page=2")
    expect(screen.queryByText("No transactions yet.")).not.toBeInTheDocument()
    expect(
      screen.queryByText("No transactions match your filters."),
    ).not.toBeInTheDocument()
    expect(
      container.querySelectorAll('[data-slot="skeleton"]').length,
    ).toBeGreaterThan(0)
  })
})
