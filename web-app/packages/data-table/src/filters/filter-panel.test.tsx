import { describe, it, expect, vi } from "vitest"
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { FilterPanel, FilterSection } from "./filter-panel"

describe("FilterPanel", () => {
  it("opens a sheet with the active count, and clears all from its footer", async () => {
    const onClearAll = vi.fn()
    render(
      <FilterPanel activeCount={2} onClearAll={onClearAll}>
        <p>fields</p>
      </FilterPanel>,
    )
    const trigger = screen.getByRole("button", { name: /Filters/ })
    expect(trigger).toHaveTextContent("2")
    await userEvent.click(trigger)
    const sheet = await screen.findByRole("dialog", { name: "Filters" })
    expect(within(sheet).getByText("2 active")).toBeInTheDocument()
    expect(within(sheet).getByText("fields")).toBeInTheDocument()
    await userEvent.click(
      within(sheet).getByRole("button", { name: "Clear all filters" }),
    )
    expect(onClearAll).toHaveBeenCalled()
  })

  it("has no count and no Clear all when nothing is active", async () => {
    render(
      <FilterPanel activeCount={0} onClearAll={() => {}}>
        <p>fields</p>
      </FilterPanel>,
    )
    await userEvent.click(screen.getByRole("button", { name: /Filters/ }))
    const sheet = await screen.findByRole("dialog", { name: "Filters" })
    expect(within(sheet).queryByText(/active/)).toBeNull()
    expect(
      within(sheet).queryByRole("button", { name: "Clear all filters" }),
    ).toBeNull()
  })

  it("closes from its close button", async () => {
    render(
      <FilterPanel activeCount={0} onClearAll={() => {}}>
        <p>fields</p>
      </FilterPanel>,
    )
    await userEvent.click(screen.getByRole("button", { name: /Filters/ }))
    const sheet = await screen.findByRole("dialog", { name: "Filters" })
    await userEvent.click(within(sheet).getByRole("button", { name: "Close" }))
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
  })
})

describe("FilterSection", () => {
  it("names its group by the title", () => {
    render(
      <FilterSection title="Amount range">
        <input aria-label="Min" />
      </FilterSection>,
    )
    expect(
      screen.getByRole("group", { name: "Amount range" }),
    ).toContainElement(screen.getByLabelText("Min"))
  })
})
