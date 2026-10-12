// apps/web/src/components/items/add-items-dialog.test.tsx
import { beforeEach, describe, it, expect, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useState } from "react"
import { AddItemsDialog } from "./add-items-dialog"

// The generated hook is mocked; the test checks what the picker asks for.
const { useListItems } = vi.hoisted(() => ({ useListItems: vi.fn() }))
vi.mock("@app/api-client/endpoints/items", () => ({ useListItems }))

const items = Array.from({ length: 10 }, (_, i) => ({
  id: i + 1,
  name: `Item ${String(i + 1).padStart(2, "0")}`,
  sku: `SKU-${i + 1}`,
  status: "active",
}))

beforeEach(() => {
  useListItems.mockReset()
  useListItems.mockReturnValue({
    data: { items, total: 25, offset: 0, limit: 10 },
    isPending: false,
    isPlaceholderData: false,
    isError: false,
  })
})

const lastParams = () => useListItems.mock.calls.at(-1)?.[0]

function ToggleableDialog() {
  const [open, setOpen] = useState(true)
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Open picker
      </button>
      <AddItemsDialog open={open} onOpenChange={setOpen} onAdd={vi.fn()} />
    </>
  )
}

describe("AddItemsDialog", () => {
  it("asks for the first page, then the next one as offset/limit", async () => {
    render(<AddItemsDialog open onOpenChange={() => {}} onAdd={vi.fn()} />)
    expect(await screen.findByText("Item 01")).toBeInTheDocument()
    expect(lastParams()).toEqual({ offset: 0, limit: 10 })
    await userEvent.click(screen.getByRole("button", { name: "Next page" }))
    expect(lastParams()).toEqual({ offset: 10, limit: 10 })
  })

  it("filters by status and goes back to the first page", async () => {
    render(<AddItemsDialog open onOpenChange={() => {}} onAdd={vi.fn()} />)
    await userEvent.click(await screen.findByRole("button", { name: "Next page" }))
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Status" }), "archived")
    expect(lastParams()).toEqual({ offset: 0, limit: 10, status: "archived" })
  })

  it("starts with an empty search each time it opens", async () => {
    const user = userEvent.setup()
    render(<ToggleableDialog />)
    await user.type(await screen.findByRole("searchbox", { name: "Search items" }), "item 1")
    await user.keyboard("{Escape}")
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())

    await user.click(screen.getByRole("button", { name: "Open picker" }))
    expect(await screen.findByRole("searchbox", { name: "Search items" })).toHaveValue("")
  })
})
