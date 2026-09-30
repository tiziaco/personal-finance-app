import { describe, it, expect } from "vitest"
import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ColumnDef } from "@tanstack/react-table"
import { ClientDataTable } from "./client-data-table"

type Person = { id: number; name: string }
const people: Person[] = [
  { id: 1, name: "Linus" },
  { id: 2, name: "Ada" },
  { id: 3, name: "Grace" },
]
const columns: ColumnDef<Person>[] = [{ accessorKey: "name", header: "Name" }]

const names = () =>
  screen
    .getAllByRole("row")
    .slice(1)
    .map((row) => within(row).getAllByRole("cell")[0].textContent)

describe("ClientDataTable", () => {
  it("searches in memory", async () => {
    render(
      <ClientDataTable
        columns={columns}
        data={people}
        searchable
        searchPlaceholder="Search people"
      />,
    )
    await userEvent.type(
      screen.getByRole("searchbox", { name: "Search people" }),
      "gra",
    )
    expect(names()).toEqual(["Grace"])
  })

  it("has no search box unless searchable", () => {
    render(<ClientDataTable columns={columns} data={people} />)
    expect(screen.queryByRole("searchbox")).toBeNull()
  })

  it("sorts in memory when a header is clicked", async () => {
    render(<ClientDataTable columns={columns} data={people} />)
    await userEvent.click(screen.getByRole("button", { name: "Name" }))
    expect(names()).toEqual(["Ada", "Grace", "Linus"])
    await userEvent.click(screen.getByRole("button", { name: "Name" }))
    expect(names()).toEqual(["Linus", "Grace", "Ada"])
  })

  it("pages in memory", async () => {
    render(<ClientDataTable columns={columns} data={people} pageSize={2} />)
    expect(names()).toEqual(["Linus", "Ada"])
    await userEvent.click(screen.getByRole("button", { name: "Next page" }))
    expect(names()).toEqual(["Grace"])
  })
})
