import { describe, it, expect, vi } from "vitest"
import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { ServerDataTable } from "./server-data-table"
import type { ColumnDef } from "./columns"

type Row = { id: string; name: string }
const columns: ColumnDef<Row>[] = [
  { accessorKey: "name", id: "name", header: "Name" },
]
const controls = {
  sorting: [],
  pagination: { pageIndex: 0, pageSize: 20 },
  totalCount: 2,
  onSortingChange: () => {},
  onPaginationChange: () => {},
}

function renderTable(
  data: Row[],
  renderBulkActions = vi.fn((rows: Row[]) => <span>{rows.length} chosen</span>),
) {
  const utils = render(
    <ServerDataTable
      columns={columns}
      data={data}
      controls={controls}
      enableRowSelection
      renderBulkActions={renderBulkActions}
    />,
  )
  return { ...utils, renderBulkActions }
}

describe("row selection", () => {
  const page1 = [
    { id: "a", name: "A" },
    { id: "b", name: "B" },
  ]

  it("shows the bulk bar only while rows are selected", async () => {
    renderTable(page1)
    expect(screen.queryByText(/selected/)).toBeNull()
    await userEvent.click(
      screen.getAllByRole("checkbox", { name: "Select row" })[0],
    )
    expect(screen.getByText("1 selected")).toBeInTheDocument()
    expect(screen.getByText("1 chosen")).toBeInTheDocument()
  })

  it("the header checkbox selects the page, Clear empties it", async () => {
    renderTable(page1)
    await userEvent.click(
      screen.getByRole("checkbox", { name: "Select all on this page" }),
    )
    expect(screen.getByText("2 selected")).toBeInTheDocument()
    await userEvent.click(
      screen.getByRole("button", { name: "Clear selection" }),
    )
    expect(screen.queryByText(/selected/)).toBeNull()
  })

  it("drops selected rows that leave the screen (a page or filter change)", async () => {
    const { rerender, renderBulkActions } = renderTable(page1)
    await userEvent.click(
      screen.getAllByRole("checkbox", { name: "Select row" })[0],
    )
    rerender(
      <ServerDataTable
        columns={columns}
        data={[{ id: "c", name: "C" }]}
        controls={controls}
        enableRowSelection
        renderBulkActions={renderBulkActions}
      />,
    )
    expect(screen.queryByText(/selected/)).toBeNull()
  })

  it("a row that left the screen stays deselected when it returns", async () => {
    const { rerender, renderBulkActions } = renderTable(page1)
    await userEvent.click(
      screen.getAllByRole("checkbox", { name: "Select row" })[0],
    )
    const table = (data: Row[]) => (
      <ServerDataTable
        columns={columns}
        data={data}
        controls={controls}
        enableRowSelection
        renderBulkActions={renderBulkActions}
      />
    )
    rerender(table([{ id: "c", name: "C" }]))
    rerender(table(page1))
    expect(screen.queryByText(/selected/)).toBeNull()
    expect(
      screen.getAllByRole("checkbox", { name: "Select row" })[0],
    ).not.toBeChecked()
  })

  it("adds no checkbox column unless enabled", () => {
    render(
      <ServerDataTable columns={columns} data={page1} controls={controls} />,
    )
    expect(screen.queryByRole("checkbox")).toBeNull()
  })
  it("floats the bulk bar after the table, not above it", async () => {
    renderTable(page1)
    await userEvent.click(
      screen.getAllByRole("checkbox", { name: "Select row" })[0],
    )
    const bar = screen.getByRole("toolbar", { name: "Bulk actions" })
    const table = screen.getByRole("table")
    // after the table in document order: it overlays the rows, it does not push them down
    expect(
      table.compareDocumentPosition(bar) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
    // the count reads as one phrase for screen readers
    expect(within(bar).getByText("1 selected")).toBeInTheDocument()
  })
})
