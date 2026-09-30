import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ColumnDef } from "@tanstack/react-table"
import { ServerDataTable } from "./server-data-table"
import { toServerTableControls } from "./table-state"

type Person = { id: number; name: string }
const page: Person[] = Array.from({ length: 10 }, (_, i) => ({
  id: i,
  name: `Person ${i}`,
}))
const columns: ColumnDef<Person>[] = [{ accessorKey: "name", header: "Name" }]

function state() {
  return { sorting: [], pageIndex: 0, setPage: vi.fn(), setSort: vi.fn() }
}

describe("ServerDataTable", () => {
  it("shows the server total in the pager", () => {
    render(
      <ServerDataTable
        columns={columns}
        data={page}
        controls={toServerTableControls(state(), {
          pageSize: 10,
          totalCount: 42,
        })}
      />,
    )
    expect(
      screen.getByRole("navigation", { name: "Pagination" }),
    ).toHaveTextContent("Showing 1 to 10 of 42 entries")
  })

  it("asks for the next page through the state", async () => {
    const s = state()
    render(
      <ServerDataTable
        columns={columns}
        data={page}
        controls={toServerTableControls(s, { pageSize: 10, totalCount: 42 })}
      />,
    )
    await userEvent.click(screen.getByRole("button", { name: "Next page" }))
    expect(s.setPage).toHaveBeenCalledWith(1)
  })

  it("asks for a sort through the state", async () => {
    const s = state()
    render(
      <ServerDataTable
        columns={columns}
        data={page}
        controls={toServerTableControls(s, { pageSize: 10, totalCount: 42 })}
      />,
    )
    await userEvent.click(screen.getByRole("button", { name: "Name" }))
    expect(s.setSort).toHaveBeenCalledWith([{ id: "name", desc: false }])
  })

  it("never renders the in-memory search", () => {
    render(
      <ServerDataTable
        columns={columns}
        data={page}
        controls={toServerTableControls(state(), {
          pageSize: 10,
          totalCount: 42,
        })}
      />,
    )
    expect(screen.queryByRole("searchbox")).toBeNull()
  })
})
