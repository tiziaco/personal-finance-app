import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { Change } from "./change"
import { PeriodSelect } from "./period-select"
import { Section } from "./section"

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

function renderSection(query: {
  data: string[] | undefined
  isError: boolean
  refetch: () => unknown
}) {
  return render(
    <Section
      title="Things"
      query={query}
      what="things"
      skeleton={<div>loading</div>}
      isEmpty={(d) => d.length === 0}
      empty="Nothing here."
    >
      {(d) => <div>{d.join(",")}</div>}
    </Section>,
  )
}

describe("Section", () => {
  it("shows the skeleton while loading", () => {
    renderSection({ data: undefined, isError: false, refetch: vi.fn() })
    expect(screen.getByText("Things")).toBeTruthy()
    expect(screen.getByText("loading")).toBeTruthy()
  })

  it("shows the error with a retry when nothing loaded", () => {
    const refetch = vi.fn()
    renderSection({ data: undefined, isError: true, refetch })
    expect(screen.getByText(/Couldn't load things/)).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Retry" }))
    expect(refetch).toHaveBeenCalled()
  })

  it("keeps data when a refetch fails", () => {
    renderSection({ data: ["a", "b"], isError: true, refetch: vi.fn() })
    expect(screen.getByText("a,b")).toBeTruthy()
    expect(screen.queryByText(/Couldn't load/)).toBeNull()
  })

  it("shows the empty text", () => {
    renderSection({ data: [], isError: false, refetch: vi.fn() })
    expect(screen.getByText("Nothing here.")).toBeTruthy()
  })
})
