import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { Change } from "./change"
import { PeriodSelect } from "./period-select"

describe("PeriodSelect", () => {
  it("marks the chosen period and reports a click", () => {
    const onChange = vi.fn()
    render(<PeriodSelect choices={[1, 3, 6]} value={3} onChange={onChange} />)
    expect(screen.getByRole("group", { name: "Period" })).toBeTruthy()
    expect(
      screen
        .getByRole("button", { name: "3 months" })
        .getAttribute("aria-pressed"),
    ).toBe("true")
    expect(
      screen
        .getByRole("button", { name: "1 month" })
        .getAttribute("aria-pressed"),
    ).toBe("false")
    fireEvent.click(screen.getByRole("button", { name: "6 months" }))
    expect(onChange).toHaveBeenCalledWith(6)
  })
})

describe("Change", () => {
  it("spending up reads as bad", () => {
    render(<Change pct={12} kind="spend" up="above" down="below" />)
    const el = screen.getByText(/12\.0% above/)
    expect(el.getAttribute("data-tone")).toBe("bad")
  })

  it("income down reads as bad", () => {
    render(<Change pct={-4} kind="income" up="more" down="less" />)
    const el = screen.getByText(/4\.0% less/)
    expect(el.getAttribute("data-tone")).toBe("bad")
  })

  it("null shows the given reason", () => {
    render(
      <Change
        pct={null}
        kind="spend"
        up="a"
        down="b"
        empty="no comparison yet"
      />,
    )
    expect(screen.getByText("no comparison yet")).toBeTruthy()
  })

  it("zero shows no change", () => {
    render(<Change pct={0} kind="spend" up="a" down="b" />)
    const el = screen.getByText("no change")
    expect(el.getAttribute("data-tone")).toBe("neutral")
  })
})
