import { describe, it, expect, vi, beforeEach } from "vitest"
import { act, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"
import {
  getListTransactionsQueryKey,
  useBatchDeleteTransactions,
  useDeleteTransaction,
} from "@app/api-client/endpoints/transactions"
import { DeleteTransactionsDialog } from "./delete-transactions-dialog"

vi.mock("@app/api-client/endpoints/transactions", async (orig) => ({
  ...(await orig<typeof import("@app/api-client/endpoints/transactions")>()),
  useDeleteTransaction: vi.fn(),
  useBatchDeleteTransactions: vi.fn(),
}))

const one = vi.fn()
const many = vi.fn()

let queryClient = new QueryClient()
const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
)

describe("DeleteTransactionsDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    queryClient = new QueryClient()
    vi.mocked(useDeleteTransaction).mockReturnValue({
      mutate: one,
      isPending: false,
    } as unknown as ReturnType<typeof useDeleteTransaction>)
    vi.mocked(useBatchDeleteTransactions).mockReturnValue({
      mutate: many,
      isPending: false,
    } as unknown as ReturnType<typeof useBatchDeleteTransactions>)
  })

  it("deletes one by id, then closes", async () => {
    const onOpenChange = vi.fn()
    const onDeleted = vi.fn()
    render(
      <DeleteTransactionsDialog
        ids={["a"]}
        open
        onOpenChange={onOpenChange}
        onDeleted={onDeleted}
      />,
      { wrapper },
    )
    expect(screen.getByText("Delete this transaction?")).toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: "Delete" }))

    expect(one.mock.calls[0][0]).toEqual({ transactionId: "a" })
    expect(many).not.toHaveBeenCalled()
    await act(() => one.mock.calls[0][1].onSuccess())
    expect(onDeleted).toHaveBeenCalled()
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it("deletes several in one batch", async () => {
    render(
      <DeleteTransactionsDialog ids={["a", "b"]} open onOpenChange={vi.fn()} />,
      { wrapper },
    )
    expect(screen.getByText("Delete 2 transactions?")).toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: "Delete" }))

    expect(many.mock.calls[0][0]).toEqual({ data: { ids: ["a", "b"] } })
    expect(one).not.toHaveBeenCalled()
  })

  it("refreshes the list from the hooks, so a dialog closed mid-delete still refreshes", async () => {
    render(
      <DeleteTransactionsDialog ids={["a"]} open onOpenChange={vi.fn()} />,
      {
        wrapper,
      },
    )
    const invalidate = vi.spyOn(queryClient, "invalidateQueries")
    for (const hook of [useDeleteTransaction, useBatchDeleteTransactions]) {
      const onSuccess = vi.mocked(hook).mock.calls[0][0]?.mutation
        ?.onSuccess as () => Promise<void>
      await onSuccess()
    }
    expect(invalidate).toHaveBeenCalledTimes(2)
    expect(invalidate).toHaveBeenCalledWith({
      queryKey: getListTransactionsQueryKey(),
    })
  })

  it("keeps Delete disabled once the delete succeeded, until the dialog closes", () => {
    vi.mocked(useDeleteTransaction).mockReturnValue({
      mutate: one,
      isPending: false,
      isSuccess: true,
    } as unknown as ReturnType<typeof useDeleteTransaction>)
    render(
      <DeleteTransactionsDialog ids={["a"]} open onOpenChange={vi.fn()} />,
      {
        wrapper,
      },
    )
    expect(screen.getByRole("button", { name: "Delete" })).toBeDisabled()
  })
})
