import { beforeEach, describe, expect, it, vi } from "vitest"
import { act, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"
import { toast } from "sonner"
import { ApiError } from "@app/api-client"
import {
  useConfirmTransactionsImport,
  useUploadTransactionsCsv,
} from "@app/api-client/endpoints/transaction-imports"
import type { ImportPreview, ImportResult } from "@app/api-client/types"
import { getListTransactionsQueryKey } from "@app/api-client/endpoints/transactions"
import { ImportCsvDialog } from "./import-csv-dialog"

vi.mock("sonner", () => ({ toast: { success: vi.fn() } }))
vi.mock("@app/api-client/endpoints/transaction-imports", () => ({
  useUploadTransactionsCsv: vi.fn(),
  useConfirmTransactionsImport: vi.fn(),
}))

const uploadMutate = vi.fn()
const confirmMutate = vi.fn()
const user = userEvent.setup({ applyAccept: false })
let queryClient = new QueryClient()
const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
)

const preview = {
  upload_id: "u1",
  filename: "konto.csv",
  row_count: 2,
  mapping_source: "proposed",
  columns: [
    {
      name: "Datum",
      proposed_field: "date",
      empty_rate: 0,
      date_format: "dd.mm.yyyy",
      amount_style: null,
    },
    {
      name: "Empfaenger",
      proposed_field: "merchant",
      empty_rate: 0,
      date_format: null,
      amount_style: null,
    },
    {
      name: "Betrag",
      proposed_field: "amount",
      empty_rate: 0,
      date_format: null,
      amount_style: "1.234,56",
    },
  ],
  sample_rows: [["15.01.2026", "REWE", "-3,00"]],
} as ImportPreview

const result: ImportResult = {
  imported: 412,
  skipped_duplicates: 3,
  uncategorised: 1,
  rejected: [{ row: 14, reason: "unreadable date “31.02.2026”" }],
}

/** The hook-level options the dialog passed to the confirm hook (onSuccess, meta). */
const confirmOptions = () =>
  vi.mocked(useConfirmTransactionsImport).mock.calls.at(-1)![0]!.mutation!
/** Run the hook-level onSuccess as TanStack would once the confirm resolves. */
const succeed = (r: ImportResult) =>
  (
    confirmOptions().onSuccess as unknown as (
      data: ImportResult,
    ) => Promise<void>
  )(r)

function renderDialog(open = true) {
  const onOpenChange = vi.fn()
  const view = render(
    <ImportCsvDialog open={open} onOpenChange={onOpenChange} />,
    { wrapper },
  )
  return {
    onOpenChange,
    unmount: view.unmount,
    rerender: (next: boolean) =>
      view.rerender(
        <ImportCsvDialog open={next} onOpenChange={onOpenChange} />,
      ),
  }
}

async function reachReview() {
  await user.upload(
    screen.getByLabelText("CSV file"),
    new File(["x"], "konto.csv", { type: "text/csv" }),
  )
  act(() => uploadMutate.mock.calls[0][1].onSuccess(preview))
}

describe("ImportCsvDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    queryClient = new QueryClient()
    vi.mocked(useUploadTransactionsCsv).mockReturnValue({
      mutate: uploadMutate,
      isPending: false,
    } as never)
    vi.mocked(useConfirmTransactionsImport).mockReturnValue({
      mutate: confirmMutate,
      isPending: false,
    } as never)
  })

  it("refuses a file that is not a CSV without sending it", async () => {
    renderDialog()
    await user.upload(
      screen.getByLabelText("CSV file"),
      new File(["x"], "notes.txt"),
    )
    expect(screen.getByRole("alert")).toHaveTextContent("Choose a .csv file.")
    expect(uploadMutate).not.toHaveBeenCalled()
  })

  it("uploads a CSV and shows its review", async () => {
    renderDialog()
    await reachReview()
    expect(uploadMutate.mock.calls[0][0]).toEqual({
      data: { file: expect.any(File) },
    })
    expect(screen.getByText("Empfaenger")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Import 2 rows" })).toBeEnabled()
  })

  it("shows a refused upload inline", async () => {
    renderDialog()
    await user.upload(
      screen.getByLabelText("CSV file"),
      new File(["x"], "konto.csv"),
    )
    act(() =>
      uploadMutate.mock.calls[0][1].onError(
        new ApiError("HTTP 422", 422, { details: { reason: "no_rows" } }, null),
      ),
    )
    expect(screen.getByRole("alert")).toHaveTextContent(
      "The file has a header but no rows.",
    )
  })

  it("imports and shows the result", async () => {
    renderDialog()
    await reachReview()
    await user.click(screen.getByRole("button", { name: "Import 2 rows" }))
    expect(confirmMutate.mock.calls[0][0]).toEqual({
      uploadId: "u1",
      data: {
        mapping: { Datum: "date", Empfaenger: "merchant", Betrag: "amount" },
      },
    })
    expect(
      screen.getByText(/Importing and categorising 2 rows/),
    ).toBeInTheDocument()
    await act(() => succeed(result))
    expect(screen.getByText("412")).toBeInTheDocument()
    expect(
      screen.getByText("Row 14: unreadable date “31.02.2026”"),
    ).toBeInTheDocument()
    expect(toast.success).not.toHaveBeenCalled()
  })

  it("refreshes the list from the hook, so a closed dialog still refreshes", async () => {
    renderDialog()
    const invalidate = vi.spyOn(queryClient, "invalidateQueries")
    await act(() => succeed(result))
    expect(invalidate).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: getListTransactionsQueryKey() }),
    )
  })

  it("toasts the counts when the dialog was closed mid-import, and View details reopens it", async () => {
    const { onOpenChange, rerender } = renderDialog()
    await reachReview()
    await user.click(screen.getByRole("button", { name: "Import 2 rows" }))
    rerender(false)
    await act(() => succeed(result))
    const [message, options] = vi.mocked(toast.success).mock.calls[0]
    expect(message).toBe("Imported 412 · 3 duplicates skipped · 1 rejected")
    ;(
      options as unknown as { action: { onClick: () => void } }
    ).action.onClick()
    expect(onOpenChange).toHaveBeenCalledWith(true)
  })

  it("reports after the page is left: counts-only toast, and failures are not silenced", async () => {
    const { unmount } = renderDialog()
    await reachReview()
    await user.click(screen.getByRole("button", { name: "Import 2 rows" }))
    const options = confirmOptions()
    unmount()
    await act(() =>
      (options.onSuccess as unknown as (d: ImportResult) => Promise<void>)(
        result,
      ),
    )
    expect(toast.success).toHaveBeenCalledWith(
      "Imported 412 · 3 duplicates skipped · 1 rejected",
      undefined,
    )
    expect(
      (options.meta!.silentError as (e: unknown) => boolean)(
        new ApiError("HTTP 503", 503, {}, null),
      ),
    ).toBe(false)
  })

  it("formats toast counts alike and uses the singular", async () => {
    const { rerender } = renderDialog()
    rerender(false)
    await act(() =>
      succeed({
        imported: 5,
        skipped_duplicates: 1,
        uncategorised: 0,
        rejected: [],
      }),
    )
    expect(vi.mocked(toast.success).mock.calls[0][0]).toBe(
      "Imported 5 · 1 duplicate skipped · 0 rejected",
    )
    await act(() =>
      succeed({
        imported: 5000,
        skipped_duplicates: 1204,
        uncategorised: 0,
        rejected: [],
      }),
    )
    expect(vi.mocked(toast.success).mock.calls[1][0]).toBe(
      "Imported 5,000 · 1,204 duplicates skipped · 0 rejected",
    )
  })

  it("says the import carries on if closed", async () => {
    renderDialog()
    await reachReview()
    await user.click(screen.getByRole("button", { name: "Import 2 rows" }))
    expect(
      screen.getByText("You can close this; the import carries on."),
    ).toBeInTheDocument()
  })

  it("sends one confirm for a double click", async () => {
    renderDialog()
    await reachReview()
    await user.dblClick(screen.getByRole("button", { name: "Import 2 rows" }))
    expect(confirmMutate).toHaveBeenCalledTimes(1)
  })

  it("reopens on the result after a success while closed", async () => {
    const { rerender } = renderDialog()
    await reachReview()
    await user.click(screen.getByRole("button", { name: "Import 2 rows" }))
    rerender(false)
    await act(() => succeed(result))
    rerender(true)
    expect(screen.getByText("412")).toBeInTheDocument()
  })

  it("a failure after closing is left to QueryProvider's toast", async () => {
    const { rerender } = renderDialog()
    const silent = confirmOptions().meta!.silentError as (e: unknown) => boolean
    const unavailable = new ApiError("HTTP 503", 503, {}, null)
    expect(silent(unavailable)).toBe(true)
    rerender(false)
    expect(
      (confirmOptions().meta!.silentError as (e: unknown) => boolean)(
        unavailable,
      ),
    ).toBe(false)
  })

  it("goes back to choosing a file when the upload expired", async () => {
    renderDialog()
    await reachReview()
    await user.click(screen.getByRole("button", { name: "Import 2 rows" }))
    act(() =>
      confirmMutate.mock.calls[0][1].onError(
        new ApiError("HTTP 404", 404, {}, null),
      ),
    )
    expect(screen.getByRole("alert")).toHaveTextContent(
      "This upload has expired. Choose the file again.",
    )
    expect(screen.getByLabelText("CSV file")).toBeInTheDocument()
  })

  it("offers to try again when categorisation is down", async () => {
    renderDialog()
    await reachReview()
    await user.click(screen.getByRole("button", { name: "Import 2 rows" }))
    act(() =>
      confirmMutate.mock.calls[0][1].onError(
        new ApiError("HTTP 503", 503, {}, null),
      ),
    )
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Categorisation isn't available right now.",
    )
    await user.click(screen.getByRole("button", { name: "Try again" }))
    expect(confirmMutate).toHaveBeenCalledTimes(2)
  })
})
