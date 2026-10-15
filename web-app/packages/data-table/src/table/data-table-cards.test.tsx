import { describe, it, expect, afterEach } from "vitest"
import { render, screen } from "@testing-library/react"
import { ServerDataTable } from "./server-data-table"
import type { ColumnDef } from "./columns"

type Row = { id: string; name: string }
const columns: ColumnDef<Row>[] = [
  { accessorKey: "name", id: "name", header: "Name" },
]
const controls = {
  sorting: [],
  pagination: { pageIndex: 0, pageSize: 20 },
  totalCount: 1,
  onSortingChange: () => {},
  onPaginationChange: () => {},
}

// useIsMobile reads window.innerWidth inside an effect; the matchMedia stub
// in vitest.setup.ts only supplies the listener API.
function setWidth(px: number) {
  Object.defineProperty(window, "innerWidth", { configurable: true, value: px })
}

describe("renderCard", () => {
  afterEach(() => setWidth(1024))

  it("renders cards instead of the table on a phone", () => {
    setWidth(400)
    render(
      <ServerDataTable
        columns={columns}
        data={[{ id: "a", name: "A" }]}
        controls={controls}
        renderCard={(row) => <p>card {row.original.name}</p>}
      />,
    )
    expect(screen.getByText("card A")).toBeInTheDocument()
    expect(screen.queryByRole("table")).toBeNull()
  })

  it("keeps the table on a desktop", () => {
    setWidth(1024)
    render(
      <ServerDataTable
        columns={columns}
        data={[{ id: "a", name: "A" }]}
        controls={controls}
        renderCard={(row) => <p>card {row.original.name}</p>}
      />,
    )
    expect(screen.getByRole("table")).toBeInTheDocument()
  })

  it("shows the empty message in card mode too", () => {
    setWidth(400)
    render(
      <ServerDataTable
        columns={columns}
        data={[]}
        controls={controls}
        renderCard={() => null}
        noDataMessage="Nothing here"
      />,
    )
    expect(screen.getByText("Nothing here")).toBeInTheDocument()
  })
})
