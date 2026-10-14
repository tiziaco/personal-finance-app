import { describe, it, expect } from "vitest"
import { useState } from "react"
import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { DateFilterControl } from "./date-filter-control"
import {
  EMPTY_DATE_FILTER,
  type DateFilterValue,
} from "../url-state/date-filter"

function DateHarness({
  initial = EMPTY_DATE_FILTER,
}: {
  initial?: DateFilterValue
}) {
  const [value, setValue] = useState(initial)
  return (
    <>
      <DateFilterControl label="Created" value={value} onChange={setValue} />
      <output>{JSON.stringify(value)}</output>
    </>
  )
}

// Base UI's Select: open the combobox, then pick from the listbox it portals.
async function pickMode(option: string) {
  await userEvent.click(screen.getByRole("combobox", { name: "Created" }))
  await userEvent.click(
    within(await screen.findByRole("listbox")).getByRole("option", {
      name: option,
    }),
  )
}

describe("DateFilterControl", () => {
  it("shows Any date until a mode is picked", () => {
    render(<DateHarness />)
    expect(screen.getByRole("combobox", { name: "Created" })).toHaveTextContent(
      "Any date",
    )
  })

  it("shows the date pickers the mode uses", async () => {
    render(<DateHarness />)
    expect(screen.queryByRole("button", { name: /^Created from/ })).toBeNull()
    await pickMode("On or after")
    expect(
      screen.getByRole("button", { name: /^Created from/ }),
    ).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /^Created to/ })).toBeNull()
    await pickMode("Between")
    expect(
      screen.getByRole("button", { name: /^Created to/ }),
    ).toBeInTheDocument()
  })

  it("picks a day from the calendar as a local ISO date", async () => {
    render(
      <DateHarness initial={{ mode: "gte", date1: "2026-03-03", date2: "" }} />,
    )
    await userEvent.click(screen.getByRole("button", { name: /^Created from/ }))
    await userEvent.click(
      await screen.findByRole("button", { name: /March 14/ }),
    )
    expect(screen.getByRole("status")).toHaveTextContent('"date1":"2026-03-14"')
  })

  it("resets to empty when the mode is cleared", async () => {
    render(
      <DateHarness initial={{ mode: "gte", date1: "2026-01-01", date2: "" }} />,
    )
    await pickMode("Any date")
    expect(screen.getByRole("status")).toHaveTextContent(
      JSON.stringify(EMPTY_DATE_FILTER),
    )
  })
})
