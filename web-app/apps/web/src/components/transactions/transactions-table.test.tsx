import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import { withNuqsTestingAdapter } from "@app/data-table/url-state/testing"
import {
  useListTransactions,
  useListTransactionCategories,
} from "@app/api-client/endpoints/transactions"
import { TransactionsTable } from "./transactions-table"

vi.mock("@app/api-client/endpoints/transactions", async (orig) => ({
  ...(await orig<typeof import("@app/api-client/endpoints/transactions")>()),
  useListTransactions: vi.fn(),
  useListTransactionCategories: vi.fn(),
}))

const list = vi.mocked(useListTransactions)
const cats = vi.mocked(useListTransactionCategories)

const result = (items: unknown[]) =>
  list.mockReturnValue({
    data: { items, total: items.length },
    isPending: false,
    isPlaceholderData: false,
    isError: false,
  } as unknown as ReturnType<typeof useListTransactions>)

const renderAt = (qs = "") => {
  const Wrapper = withNuqsTestingAdapter({ searchParams: qs })
  return render(<TransactionsTable />, { wrapper: Wrapper })
}

describe("TransactionsTable", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    cats.mockReturnValue({
      data: [{ value: "salary", label: "Salary" }],
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
    result([
      {
        id: "1",
        date: "2026-03-03",
        merchant: "Späti",
        amount: "-4.50",
        category: "salary",
        confidence: 0.5,
      },
    ])
    renderAt()
    expect(screen.getByText("50%").className).toMatch(/warning|amber/)
    expect(screen.getByText("Salary")).toBeInTheDocument()
  })
})
