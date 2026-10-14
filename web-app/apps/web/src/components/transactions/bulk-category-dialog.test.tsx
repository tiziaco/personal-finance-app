import { describe, it, expect, vi, beforeEach } from "vitest"
import { act, render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"
import {
  getListTransactionsQueryKey,
  useBatchUpdateTransactionCategory,
  useListTransactionCategories,
} from "@app/api-client/endpoints/transactions"
import { BulkCategoryDialog } from "./bulk-category-dialog"

vi.mock("@app/api-client/endpoints/transactions", async (orig) => ({
  ...(await orig<typeof import("@app/api-client/endpoints/transactions")>()),
  useBatchUpdateTransactionCategory: vi.fn(),
  useListTransactionCategories: vi.fn(),
}))

const hook = vi.mocked(useBatchUpdateTransactionCategory)
const mutate = vi.fn()

let queryClient = new QueryClient()
const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
)

const mockHook = (state: { isPending?: boolean; isSuccess?: boolean } = {}) =>
  hook.mockReturnValue({
    mutate,
    isPending: false,
    ...state,
  } as unknown as ReturnType<typeof useBatchUpdateTransactionCategory>)

// Base UI's Select: open the combobox, then pick from the listbox it portals.
async function pickOption(combobox: string, option: string) {
  await userEvent.click(screen.getByRole("combobox", { name: combobox }))
  await userEvent.click(
    within(await screen.findByRole("listbox")).getByRole("option", {
      name: option,
    }),
  )
}

describe("BulkCategoryDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    queryClient = new QueryClient()
    mockHook()
    vi.mocked(useListTransactionCategories).mockReturnValue({
      data: [{ value: "atm", label: "ATM" }],
    } as unknown as ReturnType<typeof useListTransactionCategories>)
  })

  it("applies one category to every id, then clears the selection and closes", async () => {
    const onOpenChange = vi.fn()
    const onDone = vi.fn()
    render(
      <BulkCategoryDialog
        ids={["a", "b"]}
        open
        onOpenChange={onOpenChange}
        onDone={onDone}
      />,
      { wrapper },
    )
    await pickOption("Category", "ATM")
    await userEvent.click(screen.getByRole("button", { name: "Apply" }))
    expect(mutate.mock.calls[0][0]).toEqual({
      data: { ids: ["a", "b"], category: "atm" },
    })
    act(() => mutate.mock.calls[0][1].onSuccess())
    expect(onDone).toHaveBeenCalled()
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it("refreshes the list from the hook, so a dialog closed mid-update still refreshes", async () => {
    render(
      <BulkCategoryDialog
        ids={["a"]}
        open
        onOpenChange={vi.fn()}
        onDone={vi.fn()}
      />,
      { wrapper },
    )
    const invalidate = vi.spyOn(queryClient, "invalidateQueries")
    const onSuccess = hook.mock.calls[0][0]?.mutation
      ?.onSuccess as () => Promise<void>
    await onSuccess()
    expect(invalidate).toHaveBeenCalledWith({
      queryKey: getListTransactionsQueryKey(),
    })
  })

  it("keeps Apply disabled once the update succeeded, until the dialog closes", async () => {
    mockHook({ isSuccess: true })
    render(
      <BulkCategoryDialog
        ids={["a"]}
        open
        onOpenChange={vi.fn()}
        onDone={vi.fn()}
      />,
      { wrapper },
    )
    await pickOption("Category", "ATM")
    expect(screen.getByRole("button", { name: "Apply" })).toBeDisabled()
  })
})
