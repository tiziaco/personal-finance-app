import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import {
  getCoreRowModel,
  getPaginationRowModel,
  useReactTable,
} from "@tanstack/react-table"
import { DataTablePager, getPageItems } from "./data-table-pager"

function Harness({
  rows,
  disabled = false,
}: {
  rows: number
  disabled?: boolean
}) {
  "use no memo"
  // eslint-disable-next-line react-hooks/incompatible-library -- TanStack Table returns a mutable instance; this component opts out of React Compiler
  const table = useReactTable({
    data: Array.from({ length: rows }, (_, i) => ({ id: i })),
    columns: [{ accessorKey: "id" }],
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageIndex: 0, pageSize: 10 } },
  })
  return (
    <>
      <DataTablePager table={table} totalCount={rows} disabled={disabled} />
      <output>{table.getState().pagination.pageIndex}</output>
    </>
  )
}

describe("getPageItems", () => {
  it("lists every page when there are 7 or fewer", () => {
    expect(getPageItems(0, 3)).toEqual([0, 1, 2])
  })
  it("collapses distant pages into ellipses", () => {
    expect(getPageItems(5, 20)).toEqual([0, "...", 4, 5, 6, "...", 19])
  })
})

describe("DataTablePager", () => {
  it("renders nothing for a single page", () => {
    render(<Harness rows={5} />)
    expect(screen.queryByRole("navigation")).toBeNull()
  })

  it("shows the range and moves to the next page", async () => {
    render(<Harness rows={25} />)
    expect(
      screen.getByRole("navigation", { name: "Pagination" }),
    ).toHaveTextContent("Showing 1 to 10 of 25 entries")
    await userEvent.click(screen.getByRole("button", { name: "Next page" }))
    expect(screen.getByRole("status")).toHaveTextContent("1")
    expect(screen.getByRole("button", { name: "2" })).toHaveAttribute(
      "aria-current",
      "page",
    )
  })

  it("disables every button when disabled", () => {
    render(<Harness rows={25} disabled />)
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "2" })).toBeDisabled()
  })
})
