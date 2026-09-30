import { describe, it, expect } from "vitest"
import { useState } from "react"
import { render, screen } from "@testing-library/react"
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

describe("DateFilterControl", () => {
  it("shows the inputs the mode uses", async () => {
    render(<DateHarness />)
    expect(screen.queryByLabelText("Created from")).toBeNull()
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Created" }),
      "gte",
    )
    expect(screen.getByLabelText("Created from")).toBeInTheDocument()
    expect(screen.queryByLabelText("Created to")).toBeNull()
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Created" }),
      "range",
    )
    expect(screen.getByLabelText("Created to")).toBeInTheDocument()
  })

  it("resets to empty when the mode is cleared", async () => {
    render(
      <DateHarness initial={{ mode: "gte", date1: "2026-01-01", date2: "" }} />,
    )
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Created" }),
      "",
    )
    expect(screen.getByRole("status")).toHaveTextContent(
      JSON.stringify(EMPTY_DATE_FILTER),
    )
  })
})
