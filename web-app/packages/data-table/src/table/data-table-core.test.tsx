import { describe, it, expect, vi } from "vitest"
import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ColumnDef, SortingState, Updater } from "@tanstack/react-table"
import { DataTableCore, getColumnFreezeInfo } from "./data-table-core"
import type { ServerTableControls } from "./table-state"

type Person = { id: number; name: string; city: string }
const people: Person[] = [
  { id: 1, name: "Ada", city: "London" },
  { id: 2, name: "Linus", city: "Helsinki" },
  { id: 3, name: "Grace", city: "New York" },
]
const columns: ColumnDef<Person>[] = [
  { accessorKey: "name", header: "Name" },
  { accessorKey: "city", header: "City", enableSorting: false },
]
const client = { kind: "client", pageSize: 10 } as const

function controls(
  overrides: Partial<ServerTableControls> = {},
): ServerTableControls {
  return {
    sorting: [],
    pagination: { pageIndex: 0, pageSize: 10 },
    totalCount: 3,
    onSortingChange: vi.fn(),
    onPaginationChange: vi.fn(),
    ...overrides,
  }
}

const firstColumn = () =>
  screen
    .getAllByRole("row")
    .slice(1)
    .map((row) => within(row).getAllByRole("cell")[0].textContent)

describe("DataTableCore", () => {
  it("renders headers and rows", () => {
    render(<DataTableCore columns={columns} data={people} mode={client} />)
    expect(
      screen.getByRole("columnheader", { name: /Name/ }),
    ).toBeInTheDocument()
    expect(firstColumn()).toEqual(["Ada", "Linus", "Grace"])
  })

  it("shows noDataMessage when there are no rows", () => {
    render(
      <DataTableCore
        columns={columns}
        data={[]}
        noDataMessage="Nothing here"
        mode={client}
      />,
    )
    expect(screen.getByText("Nothing here")).toBeInTheDocument()
  })

  it("shows skeleton rows instead of noDataMessage while loading", () => {
    const { container } = render(
      <DataTableCore
        columns={columns}
        data={[]}
        isLoading
        noDataMessage="Nothing here"
        mode={client}
      />,
    )
    expect(screen.queryByText("Nothing here")).toBeNull()
    expect(
      container.querySelectorAll('[data-slot="skeleton"]').length,
    ).toBeGreaterThan(0)
  })

  it("shows errorMessage in place of rows", () => {
    render(
      <DataTableCore
        columns={columns}
        data={people}
        errorMessage="Could not load"
        mode={client}
      />,
    )
    expect(screen.getByRole("alert")).toHaveTextContent("Could not load")
    expect(screen.queryByText("Ada")).toBeNull()
  })

  it("marks the table busy and disables the pager while pending", () => {
    render(
      <DataTableCore
        columns={columns}
        data={people}
        isPending
        mode={{ kind: "server", controls: controls({ totalCount: 30 }) }}
      />,
    )
    expect(screen.getByRole("table")).toHaveAttribute("aria-busy", "true")
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled()
  })

  it("only renders sort buttons for sortable columns", () => {
    render(<DataTableCore columns={columns} data={people} mode={client} />)
    expect(screen.getByRole("button", { name: "Name" })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "City" })).toBeNull()
    expect(screen.getByRole("columnheader", { name: /Name/ })).toHaveAttribute(
      "aria-sort",
      "none",
    )
  })

  it("in server mode, hands sort changes back and does not sort in memory", async () => {
    const c = controls()
    render(
      <DataTableCore
        columns={columns}
        data={people}
        mode={{ kind: "server", controls: c }}
      />,
    )
    await userEvent.click(screen.getByRole("button", { name: "Name" }))
    const updater = vi.mocked(c.onSortingChange).mock
      .calls[0][0] as Updater<SortingState>
    const next = typeof updater === "function" ? updater([]) : updater
    expect(next).toEqual([{ id: "name", desc: false }])
    expect(firstColumn()).toEqual(["Ada", "Linus", "Grace"])
  })

  it("keeps a single-column sort when shift-clicking a second column", async () => {
    const c = controls()
    const cols: ColumnDef<Person>[] = [
      { accessorKey: "name", header: "Name" },
      { accessorKey: "city", header: "City" },
    ]
    render(
      <DataTableCore
        columns={cols}
        data={people}
        mode={{ kind: "server", controls: c }}
      />,
    )
    await userEvent.keyboard("{Shift>}")
    await userEvent.click(screen.getByRole("button", { name: "City" }))
    await userEvent.keyboard("{/Shift}")
    const updater = vi.mocked(c.onSortingChange).mock
      .calls[0][0] as Updater<SortingState>
    const next =
      typeof updater === "function"
        ? updater([{ id: "name", desc: false }])
        : updater
    expect(next).toHaveLength(1)
  })

  it("makes frozen header cells sticky", () => {
    render(
      <DataTableCore
        columns={columns}
        data={people}
        freezeColumns={{ left: 1 }}
        mode={client}
      />,
    )
    expect(screen.getByRole("columnheader", { name: /Name/ })).toHaveStyle({
      position: "sticky",
    })
  })

  it("measures only its own header cells for frozen offsets, not a nested table's", async () => {
    const observed: Element[] = []
    const Original = globalThis.ResizeObserver
    globalThis.ResizeObserver = class {
      observe(el: Element) {
        observed.push(el)
      }
      unobserve() {}
      disconnect() {}
    } as unknown as typeof ResizeObserver
    try {
      const props = {
        columns,
        data: people.slice(0, 1),
        freezeColumns: { left: 1 },
        mode: client,
        renderSubComponent: () => (
          <table>
            <thead>
              <tr>
                <th data-column-id="nested">Nested</th>
              </tr>
            </thead>
          </table>
        ),
      }
      const { rerender } = render(
        <DataTableCore {...props} columnVisibility={{}} />,
      )
      await userEvent.click(screen.getByRole("button", { name: "Expand row" }))
      observed.length = 0
      rerender(<DataTableCore {...props} columnVisibility={{ city: false }} />)
      expect(
        observed.map((el) => (el as HTMLElement).dataset.columnId),
      ).toEqual(["expander", "name"])
    } finally {
      globalThis.ResizeObserver = Original
    }
  })

  it("hides columns from defaultColumnVisibility", () => {
    render(
      <DataTableCore
        columns={columns}
        data={people}
        defaultColumnVisibility={{ city: false }}
        mode={client}
      />,
    )
    expect(screen.queryByRole("columnheader", { name: /City/ })).toBeNull()
  })

  it("follows controlled columnVisibility", () => {
    const { rerender } = render(
      <DataTableCore
        columns={columns}
        data={people}
        columnVisibility={{ city: false }}
        mode={client}
      />,
    )
    expect(screen.queryByRole("columnheader", { name: /City/ })).toBeNull()
    rerender(
      <DataTableCore
        columns={columns}
        data={people}
        columnVisibility={{ city: true }}
        mode={client}
      />,
    )
    expect(
      screen.getByRole("columnheader", { name: /City/ }),
    ).toBeInTheDocument()
  })

  it("expands a row into its sub-component", async () => {
    render(
      <DataTableCore
        columns={columns}
        data={people}
        renderSubComponent={(row) => <p>Details for {row.original.name}</p>}
        mode={client}
      />,
    )
    await userEvent.click(
      screen.getAllByRole("button", { name: "Expand row" })[0],
    )
    expect(screen.getByText("Details for Ada")).toBeInTheDocument()
  })

  it("calls onRowClick with the row", async () => {
    const onRowClick = vi.fn()
    render(
      <DataTableCore
        columns={columns}
        data={people}
        onRowClick={onRowClick}
        mode={client}
      />,
    )
    await userEvent.click(screen.getByText("Linus"))
    expect(onRowClick.mock.calls[0][0].original).toEqual(people[1])
  })
})

describe("getColumnFreezeInfo", () => {
  const ids = ["a", "b", "c", "d"]
  const widths = { a: 100, b: 50, c: 80, d: 60 }

  it("offsets left-frozen columns by the widths before them", () => {
    expect(getColumnFreezeInfo(1, ids, widths, { left: 2 })).toEqual({
      frozen: true,
      side: "left",
      offset: 100,
    })
  })

  it("offsets right-frozen columns by the widths after them", () => {
    expect(getColumnFreezeInfo(2, ids, widths, { right: 2 })).toEqual({
      frozen: true,
      side: "right",
      offset: 60,
    })
  })

  it("leaves middle columns unfrozen", () => {
    expect(getColumnFreezeInfo(2, ids, widths, { left: 2, right: 1 })).toEqual({
      frozen: false,
    })
  })
})
