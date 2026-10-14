import { describe, it, expect, vi, beforeEach } from "vitest"
import { act, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"
import {
  getListTransactionsQueryKey,
  useBatchDeleteTransactions,
} from "@app/api-client/endpoints/transactions"
import { DeleteTransactionsDialog } from "./delete-transactions-dialog"

vi.mock("@app/api-client/endpoints/transactions", async (orig) => ({
  ...(await orig<typeof import("@app/api-client/endpoints/transactions")>()),
  useBatchDeleteTransactions: vi.fn(),
}))

const mutate = vi.fn()

let queryClient = new QueryClient()
const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
)

const mockHook = (state: { isPending?: boolean; isSuccess?: boolean } = {}) =>
  vi.mocked(useBatchDeleteTransactions).mockReturnValue({
    mutate,
    isPending: false,
    isSuccess: false,
    ...state,
  } as unknown as ReturnType<typeof useBatchDeleteTransactions>)

describe("DeleteTransactionsDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    queryClient = new QueryClient()
    mockHook()
  })

  it("deletes one through the batch route, then closes", async () => {
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

    expect(mutate.mock.calls[0][0]).toEqual({ data: { ids: ["a"] } })
    await act(() => mutate.mock.calls[0][1].onSuccess())
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

    expect(mutate.mock.calls[0][0]).toEqual({ data: { ids: ["a", "b"] } })
  })

  it("refreshes the list from the hook, so a dialog gone by then still refreshes", async () => {
    render(
      <DeleteTransactionsDialog ids={["a"]} open onOpenChange={vi.fn()} />,
      { wrapper },
    )
    const invalidate = vi.spyOn(queryClient, "invalidateQueries")
    const onSuccess = vi.mocked(useBatchDeleteTransactions).mock.calls[0][0]
      ?.mutation?.onSuccess as () => Promise<void>
    await onSuccess()
    expect(invalidate).toHaveBeenCalledWith({
      queryKey: getListTransactionsQueryKey(),
    })
  })

  it("cannot be closed while the delete is in flight", async () => {
    mockHook({ isPending: true })
    const onOpenChange = vi.fn()
    render(
      <DeleteTransactionsDialog ids={["a"]} open onOpenChange={onOpenChange} />,
      { wrapper },
    )
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled()
    await userEvent.keyboard("{Escape}")
    expect(onOpenChange).not.toHaveBeenCalled()
  })

  it("keeps Delete disabled once the delete succeeded, until the dialog closes", () => {
    mockHook({ isSuccess: true })
    render(
      <DeleteTransactionsDialog ids={["a"]} open onOpenChange={vi.fn()} />,
      { wrapper },
    )
    expect(screen.getByRole("button", { name: "Delete" })).toBeDisabled()
  })
})
