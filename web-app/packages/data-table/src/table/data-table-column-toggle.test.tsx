import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ColumnDef } from "@tanstack/react-table"
import { ClientDataTable } from "./client-data-table"

type Person = { id: number; name: string; city: string }
const people: Person[] = [{ id: 1, name: "Ada", city: "London" }]
const columns: ColumnDef<Person>[] = [
  { accessorKey: "name", header: "Name" },
  { accessorKey: "city", header: "City" },
]

describe("DataTableColumnToggle", () => {
  it("hides a column from the menu and shows it again", async () => {
    const user = userEvent.setup()
    render(<ClientDataTable columns={columns} data={people} showColumnToggle />)
    expect(
      screen.getByRole("columnheader", { name: "City" }),
    ).toBeInTheDocument()

    const toggleCity = async () => {
      await user.click(screen.getByRole("button", { name: "Columns" }))
      await user.click(
        await screen.findByRole("menuitemcheckbox", { name: "City" }),
      )
      await user.keyboard("{Escape}")
    }

    await toggleCity()
    expect(screen.queryByRole("columnheader", { name: "City" })).toBeNull()

    await toggleCity()
    expect(
      screen.getByRole("columnheader", { name: "City" }),
    ).toBeInTheDocument()
  })
})
