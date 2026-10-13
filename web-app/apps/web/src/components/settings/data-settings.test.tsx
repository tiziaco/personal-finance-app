import { describe, it, expect, vi, beforeEach } from "vitest"
import { act, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"
import {
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

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient()}>
    {children}
  </QueryClientProvider>
)

function mockTotal(total: number) {
  vi.mocked(useListTransactions).mockReturnValue({
    data: { total, items: [] },
  } as unknown as ReturnType<typeof useListTransactions>)
}

describe("DataSettings", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useDeleteAllTransactions).mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof useDeleteAllTransactions>)
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
    await act(() => mutate.mock.calls[0][1].onSuccess())
    expect(
      screen.queryByText("Delete all transactions?"),
    ).not.toBeInTheDocument()
  })

  it("disables the button when there is nothing to delete", () => {
    mockTotal(0)
    render(<DataSettings />, { wrapper })
    expect(
      screen.getByRole("button", { name: "Delete all transactions" }),
    ).toBeDisabled()
  })
})
