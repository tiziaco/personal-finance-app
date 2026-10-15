import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"
import { withNuqsTestingAdapter } from "@app/data-table/url-state/testing"
import {
  getListTransactionsQueryKey,
  useListTransactions,
  useListTransactionCategories,
  useUpdateTransaction,
} from "@app/api-client/endpoints/transactions"
import { TransactionsTable } from "./transactions-table"

const updateMutate = vi.hoisted(() => vi.fn())
const batchDeleteMutate = vi.hoisted(() => vi.fn())
const batchCategoryMutate = vi.hoisted(() => vi.fn())
const mutationMocks = vi.hoisted(() => {
  const mutation = () => ({ mutate: () => {}, isPending: false })
  return {
    useCreateTransaction: mutation,
    useUpdateTransaction: vi.fn(() => ({
      mutate: updateMutate,
      isPending: false,
    })),
    useBatchDeleteTransactions: () => ({
      mutate: batchDeleteMutate,
      isPending: false,
    }),
    useBatchUpdateTransactionCategory: () => ({
      mutate: batchCategoryMutate,
      isPending: false,
    }),
  }
})

vi.mock("@app/api-client/endpoints/transaction-imports", () => ({
  useUploadTransactionsCsv: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
  })),
  useConfirmTransactionsImport: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
  })),
}))

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

let queryClient = new QueryClient()

const renderAt = (qs = "", onUrlUpdate?: OnUrlUpdate) => {
  const Nuqs = withNuqsTestingAdapter({ searchParams: qs, onUrlUpdate })
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
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
  description: null,
  is_recurring: false,
}

// useIsMobile reads window.innerWidth inside an effect: below 768px the
// table renders cards.
function setWidth(px: number) {
  Object.defineProperty(window, "innerWidth", { configurable: true, value: px })
}

// Base UI's Select: open the combobox, then pick from the listbox it portals.
async function pickOption(combobox: string, option: string) {
  await userEvent.click(screen.getByRole("combobox", { name: combobox }))
  await userEvent.click(
    within(await screen.findByRole("listbox")).getByRole("option", {
      name: option,
    }),
  )
}

describe("TransactionsTable", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    queryClient = new QueryClient()
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
      screen.getByRole("button", { name: "add a transaction" }),
    )
    expect(
      await screen.findByRole("heading", { name: "Add a transaction" }),
    ).toBeInTheDocument()
  })

  it("offers Upload a CSV first in the first-run empty state", async () => {
    result([])
    renderAt()
    await userEvent.click(screen.getByRole("button", { name: "Upload a CSV" }))
    expect(
      await screen.findByRole("heading", { name: "Import a CSV" }),
    ).toBeInTheDocument()
  })

  it("opens the import dialog from the header", async () => {
    result([row])
    renderAt()
    await userEvent.click(screen.getByRole("button", { name: "Import CSV" }))
    expect(
      await screen.findByRole("heading", { name: "Import a CSV" }),
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
    // Radio items keep a menu open by default; a pick must close it.
    await waitFor(() => expect(screen.queryByRole("menu")).toBeNull())
    expect(updateMutate).toHaveBeenCalledTimes(1)
  })

  it("refreshes the list from the recategorise hook, so a closed menu still refreshes", async () => {
    result([row])
    renderAt()
    const invalidate = vi.spyOn(queryClient, "invalidateQueries")
    const onSuccess = vi.mocked(useUpdateTransaction).mock.calls[0][0]?.mutation
      ?.onSuccess as () => Promise<void>
    await onSuccess()
    expect(invalidate).toHaveBeenCalledWith({
      queryKey: getListTransactionsQueryKey(),
    })
  })

  describe("on a phone", () => {
    beforeEach(() => setWidth(400))
    afterEach(() => setWidth(1024))

    it("opens the edit dialog with the tapped card's transaction", async () => {
      result([row, { ...row, id: "2", merchant: "Rewe" }])
      renderAt()
      await userEvent.click(
        await screen.findByRole("button", { name: "Edit Rewe" }),
      )
      expect(
        await screen.findByRole("heading", { name: "Edit transaction" }),
      ).toBeInTheDocument()
      expect(screen.getByLabelText("Merchant")).toHaveValue("Rewe")
    })

    it("keeps the sort control on a phone", async () => {
      result([row])
      renderAt()
      expect(
        await screen.findByRole("combobox", { name: "Sort by" }),
      ).toBeInTheDocument()
    })
  })

  it("sorts by field from the toolbar, keeping the direction and resetting the page", async () => {
    result([row], 60)
    const events: UrlUpdateEvent[] = []
    renderAt("?page=3", (e) => events.push(e))
    const field = await screen.findByRole("combobox", { name: "Sort by" })
    expect(field).toHaveTextContent("Date")
    expect(
      screen.getByRole("button", { name: "Switch to ascending" }),
    ).toBeInTheDocument()

    await userEvent.click(field)
    const fields = await screen.findByRole("listbox")
    expect(
      within(fields)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["Date", "Amount", "Merchant"])
    await userEvent.click(
      within(fields).getByRole("option", { name: "Amount" }),
    )
    await waitFor(() =>
      expect(events.at(-1)?.searchParams.get("ordering")).toBe("-amount"),
    )
    expect(events.at(-1)?.searchParams.get("page")).toBeNull()
  })

  it("flips the direction from the arrow button", async () => {
    result([row])
    const events: UrlUpdateEvent[] = []
    renderAt("?ordering=-amount", (e) => events.push(e))
    await userEvent.click(
      await screen.findByRole("button", { name: "Switch to ascending" }),
    )
    await waitFor(() =>
      expect(events.at(-1)?.searchParams.get("ordering")).toBe("amount"),
    )
  })

  it("shows what a header click chose", async () => {
    result([row])
    renderAt("?ordering=amount")
    expect(
      await screen.findByRole("combobox", { name: "Sort by" }),
    ).toHaveTextContent("Amount")
    expect(
      screen.getByRole("button", { name: "Switch to descending" }),
    ).toBeInTheDocument()
  })

  it("puts the title and Add transaction in one header row", async () => {
    result([row])
    renderAt()
    expect(
      screen.getByRole("heading", { level: 1, name: "Transactions" }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Add transaction" }),
    ).toBeInTheDocument()
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

  describe("bulk actions", () => {
    const rows = [row, { ...row, id: "2", merchant: "Rewe" }]
    const selectBoth = async () => {
      result(rows)
      renderAt()
      for (const box of screen.getAllByRole("checkbox", {
        name: "Select row",
      }))
        await userEvent.click(box)
      expect(screen.getByText("2 selected")).toBeInTheDocument()
    }

    it("deletes the selected rows in one batch", async () => {
      await selectBoth()
      await userEvent.click(screen.getByRole("button", { name: "Delete" }))
      expect(
        await screen.findByText("Delete 2 transactions?"),
      ).toBeInTheDocument()
      await userEvent.click(screen.getByRole("button", { name: "Delete" }))
      expect(batchDeleteMutate.mock.calls[0][0]).toEqual({
        data: { ids: ["1", "2"] },
      })
    })

    it("recategorises the selected rows in one batch", async () => {
      await selectBoth()
      await userEvent.click(
        screen.getByRole("button", { name: "Recategorise" }),
      )
      expect(
        await screen.findByRole("heading", {
          name: "Recategorise 2 transactions",
        }),
      ).toBeInTheDocument()
      await pickOption("Category", "Food & Groceries")
      await userEvent.click(screen.getByRole("button", { name: "Apply" }))
      expect(batchCategoryMutate.mock.calls[0][0]).toEqual({
        data: { ids: ["1", "2"], category: "food_groceries" },
      })
    })
  })
})
