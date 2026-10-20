import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { act, render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"
import { ApiError } from "@app/api-client"
import {
  getListTransactionsQueryKey,
  useBatchDeleteTransactions,
  useCreateTransaction,
  useListTransactionCategories,
  useUpdateTransaction,
} from "@app/api-client/endpoints/transactions"
import type { TransactionResponse } from "@app/api-client/types"
import { formatDate, formatSignedAmount } from "./format"
import { TransactionFormDialog } from "./transaction-form-dialog"

vi.mock("@app/api-client/endpoints/transactions", async (orig) => ({
  ...(await orig<typeof import("@app/api-client/endpoints/transactions")>()),
  useCreateTransaction: vi.fn(),
  useUpdateTransaction: vi.fn(),
  useBatchDeleteTransactions: vi.fn(),
  useListTransactionCategories: vi.fn(),
}))

const create = vi.mocked(useCreateTransaction)
const update = vi.mocked(useUpdateTransaction)
const cats = vi.mocked(useListTransactionCategories)
const createMutate = vi.fn()
const updateMutate = vi.fn()
const deleteMutate = vi.fn()

let queryClient = new QueryClient()
const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
)

const existing: TransactionResponse = {
  id: "t1",
  date: "2026-03-03",
  merchant: "Späti",
  amount: "-4.50",
  category: "food_groceries",
  description: "Old",
  is_recurring: false,
  confidence: 1,
  created_at: "2026-03-03T10:00:00Z",
  updated_at: "2026-03-03T10:00:00Z",
}

const renderAdd = (onOpenChange = vi.fn()) =>
  render(
    <TransactionFormDialog mode="add" open onOpenChange={onOpenChange} />,
    { wrapper },
  )

async function fillAdd(amount: string) {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText("Merchant"), "Späti")
  await user.type(screen.getByLabelText("Amount"), amount)
  await user.click(screen.getByRole("combobox", { name: "Category" }))
  await user.click(
    within(await screen.findByRole("listbox")).getByRole("option", {
      name: "Food & Groceries",
    }),
  )
  return user
}

describe("TransactionFormDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    queryClient = new QueryClient()
    vi.mocked(useBatchDeleteTransactions).mockReturnValue({
      mutate: deleteMutate,
      isPending: false,
    } as unknown as ReturnType<typeof useBatchDeleteTransactions>)
    // Only Date is faked, so user-event's timers still run.
    vi.useFakeTimers({ toFake: ["Date"] })
    vi.setSystemTime(new Date(2026, 2, 3, 12))
    create.mockReturnValue({
      mutate: createMutate,
      isPending: false,
    } as unknown as ReturnType<typeof useCreateTransaction>)
    update.mockReturnValue({
      mutate: updateMutate,
      isPending: false,
    } as unknown as ReturnType<typeof useUpdateTransaction>)
    cats.mockReturnValue({
      data: [
        { value: "food_groceries", label: "Food & Groceries" },
        { value: "salary", label: "Salary" },
      ],
    } as unknown as ReturnType<typeof useListTransactionCategories>)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it("adds with a comma decimal sent as a dot, today's date, and a silent 409", async () => {
    renderAdd()
    const user = await fillAdd("-4,50")
    await user.click(screen.getByRole("button", { name: "Add" }))

    expect(createMutate).toHaveBeenCalledTimes(1)
    expect(createMutate.mock.calls[0][0]).toEqual({
      data: {
        date: "2026-03-03",
        merchant: "Späti",
        amount: "-4.50",
        category: "food_groceries",
        description: null,
        is_recurring: false,
        allow_duplicate: false,
      },
    })
    const silentError = create.mock.calls[0][0]?.mutation?.meta?.silentError
    expect(silentError).toBeTypeOf("function")
    const silences = silentError as (error: unknown) => boolean
    expect(silences(new ApiError("Conflict", 409, null, null))).toBe(true)
    expect(silences(new ApiError("Server", 500, null, null))).toBe(false)
  })

  it.each(["4,505", "abc"])(
    "rejects the amount %s inline without calling the API",
    async (amount) => {
      renderAdd()
      const user = await fillAdd(amount)
      await user.click(screen.getByRole("button", { name: "Add" }))

      expect(screen.getByText("Enter an amount like -4.50")).toBeInTheDocument()
      expect(createMutate).not.toHaveBeenCalled()
    },
  )

  it("words a 409 from its own input, adds anyway, and clears on an edit", async () => {
    renderAdd()
    const user = await fillAdd("-4,50")
    await user.click(screen.getByRole("button", { name: "Add" }))

    const { onError } = createMutate.mock.calls[0][1]
    act(() =>
      onError(
        new ApiError("Conflict", 409, { error: "DUPLICATE_TRANSACTION" }, null),
      ),
    )

    const expected = `You already have a transaction on ${formatDate("2026-03-03")} at Späti for ${formatSignedAmount("-4.50")}.`
    expect(screen.getByRole("alert")).toHaveTextContent(expected)
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Add anyway" }))
    expect(createMutate).toHaveBeenCalledTimes(2)
    expect(createMutate.mock.calls[1][0].data).toMatchObject({
      amount: "-4.50",
      allow_duplicate: true,
    })

    await user.type(screen.getByLabelText("Merchant"), "x")
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("does not show the notice for another error", async () => {
    renderAdd()
    const user = await fillAdd("-4,50")
    await user.click(screen.getByRole("button", { name: "Add" }))

    const { onError } = createMutate.mock.calls[0][1]
    act(() => onError(new ApiError("Server", 500, null, null)))
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("edits by sending only the changed field", async () => {
    const user = userEvent.setup()
    render(
      <TransactionFormDialog
        mode="edit"
        transaction={existing}
        open
        onOpenChange={vi.fn()}
      />,
      { wrapper },
    )
    await user.clear(screen.getByLabelText("Description"))
    await user.click(screen.getByRole("button", { name: "Save" }))

    expect(updateMutate).toHaveBeenCalledTimes(1)
    expect(updateMutate.mock.calls[0][0]).toEqual({
      transactionId: "t1",
      data: { description: null },
    })
  })

  it("closes without a request when nothing changed", async () => {
    const user = userEvent.setup()
    const onOpenChange = vi.fn()
    render(
      <TransactionFormDialog
        mode="edit"
        transaction={existing}
        open
        onOpenChange={onOpenChange}
      />,
      { wrapper },
    )
    // "-4,50" is the same amount as "-4.50": no change.
    await user.clear(screen.getByLabelText("Amount"))
    await user.type(screen.getByLabelText("Amount"), "-4,50")
    await user.click(screen.getByRole("button", { name: "Save" }))

    expect(updateMutate).not.toHaveBeenCalled()
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  const renderEdit = (onOpenChange = vi.fn()) =>
    render(
      <TransactionFormDialog
        mode="edit"
        transaction={existing}
        open
        onOpenChange={onOpenChange}
      />,
      { wrapper },
    )

  it("refreshes the list from the hooks, so a dialog closed mid-save still refreshes", async () => {
    renderAdd()
    const invalidate = vi.spyOn(queryClient, "invalidateQueries")
    for (const hook of [create, update]) {
      const onSuccess = hook.mock.calls[0][0]?.mutation
        ?.onSuccess as () => Promise<void>
      await onSuccess()
    }
    const listCalls = invalidate.mock.calls.filter(
      ([filters]) =>
        JSON.stringify(filters?.queryKey) ===
        JSON.stringify(getListTransactionsQueryKey()),
    )
    expect(listCalls).toHaveLength(2)
    expect(invalidate).toHaveBeenCalledWith({
      queryKey: getListTransactionsQueryKey(),
    })
  })

  it("closes on success, and keeps Save disabled until it has", async () => {
    const user = userEvent.setup()
    const onOpenChange = vi.fn()
    const { rerender } = renderEdit(onOpenChange)
    await user.clear(screen.getByLabelText("Merchant"))
    await user.type(screen.getByLabelText("Merchant"), "Rewe")
    await user.click(screen.getByRole("button", { name: "Save" }))
    act(() => updateMutate.mock.calls[0][1].onSuccess())
    expect(onOpenChange).toHaveBeenCalledWith(false)

    update.mockReturnValue({
      mutate: updateMutate,
      isPending: false,
      isSuccess: true,
    } as unknown as ReturnType<typeof useUpdateTransaction>)
    rerender(
      <TransactionFormDialog
        mode="edit"
        transaction={existing}
        open
        onOpenChange={onOpenChange}
      />,
    )
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled()
  })

  it("has no Delete action when adding", () => {
    renderAdd()
    expect(screen.queryByRole("button", { name: "Delete" })).toBeNull()
  })

  it("deletes from the edit dialog through the delete confirm, then closes", async () => {
    const user = userEvent.setup()
    const onOpenChange = vi.fn()
    renderEdit(onOpenChange)
    await user.click(screen.getByRole("button", { name: "Delete" }))

    const confirm = await screen.findByRole("alertdialog")
    expect(
      within(confirm).getByText("Delete this transaction?"),
    ).toBeInTheDocument()
    // The edit dialog dims under the confirm, so the two read as separate layers.
    const edit = document.querySelector('[data-slot="dialog-content"]')
    expect(edit).toHaveAttribute("data-nested-dialog-open")
    expect(edit?.className).toContain(
      "data-nested-dialog-open:after:bg-black/80",
    )
    await user.click(within(confirm).getByRole("button", { name: "Delete" }))
    expect(deleteMutate.mock.calls[0][0]).toEqual({ data: { ids: ["t1"] } })

    act(() => deleteMutate.mock.calls[0][1].onSuccess())
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })
})
