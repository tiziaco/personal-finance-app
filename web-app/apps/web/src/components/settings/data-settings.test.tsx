import { describe, it, expect, vi, beforeEach } from "vitest"
import { act, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"
import {
  getListTransactionsQueryKey,
  useDeleteAllTransactions,
  useListTransactions,
} from "@app/api-client/endpoints/transactions"
import { DataSettings } from "./data-settings"

vi.mock("@app/api-client/endpoints/transactions", async (orig) => ({
  ...(await orig<typeof import("@app/api-client/endpoints/transactions")>()),
  useListTransactions: vi.fn(),
  useDeleteAllTransactions: vi.fn(),
}))

const mutate = vi.fn()
const reset = vi.fn()

let queryClient = new QueryClient()
const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
)

function mockTotal(total: number | undefined) {
  vi.mocked(useListTransactions).mockReturnValue({
    data: total === undefined ? undefined : { total, items: [] },
  } as unknown as ReturnType<typeof useListTransactions>)
}

const mockDeleteAll = (state: { isSuccess?: boolean } = {}) =>
  vi.mocked(useDeleteAllTransactions).mockReturnValue({
    mutate,
    reset,
    isPending: false,
    ...state,
  } as unknown as ReturnType<typeof useDeleteAllTransactions>)

const ALL_COPY =
  "Permanently deletes all your transactions, including deleted ones. This cannot be undone."

describe("DataSettings", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    queryClient = new QueryClient()
    mockDeleteAll()
  })

  it("confirms with the count, then deletes everything", async () => {
    mockTotal(12)
    render(<DataSettings />, { wrapper })
    await userEvent.click(
      screen.getByRole("button", { name: "Delete all transactions" }),
    )
    expect(
      screen.getByText(
        "Permanently deletes all 12 transactions. This cannot be undone.",
      ),
    ).toBeInTheDocument()
    expect(mutate).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole("button", { name: "Delete all" }))
    expect(mutate).toHaveBeenCalledTimes(1)
    act(() => mutate.mock.calls[0][1].onSuccess())
    expect(
      screen.queryByText("Delete all transactions?"),
    ).not.toBeInTheDocument()
  })

  it.each([
    ["at 0", 0],
    ["before the count loads", undefined],
  ])("is enabled %s, and confirms without a count", async (_, total) => {
    mockTotal(total)
    render(<DataSettings />, { wrapper })
    const button = screen.getByRole("button", {
      name: "Delete all transactions",
    })
    expect(button).toBeEnabled()
    await userEvent.click(button)
    expect(screen.getByText(ALL_COPY)).toBeInTheDocument()
  })

  it("refreshes the list from the hook, so a closed settings dialog still refreshes", async () => {
    mockTotal(3)
    render(<DataSettings />, { wrapper })
    const invalidate = vi.spyOn(queryClient, "invalidateQueries")
    const onSuccess = vi.mocked(useDeleteAllTransactions).mock.calls[0][0]
      ?.mutation?.onSuccess as () => Promise<void>
    await onSuccess()
    expect(invalidate).toHaveBeenCalledWith({
      queryKey: getListTransactionsQueryKey(),
    })
  })

  it("keeps Delete all disabled once it succeeded, and starts fresh on the next opening", async () => {
    mockTotal(3)
    mockDeleteAll({ isSuccess: true })
    render(<DataSettings />, { wrapper })
    await userEvent.click(
      screen.getByRole("button", { name: "Delete all transactions" }),
    )
    expect(reset).toHaveBeenCalled()
    expect(screen.getByRole("button", { name: "Delete all" })).toBeDisabled()
  })
})
