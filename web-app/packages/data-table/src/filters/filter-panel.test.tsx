import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { FilterPanel } from "./filter-panel"

describe("FilterPanel", () => {
  it("shows the active count and clears all from the popover", async () => {
    const onClearAll = vi.fn()
    render(
      <FilterPanel activeCount={2} onClearAll={onClearAll}>
        <p>fields</p>
      </FilterPanel>,
    )
    await userEvent.click(screen.getByRole("button", { name: /Filters/ }))
    expect(screen.getByRole("button", { name: /Filters/ })).toHaveTextContent(
      "2",
    )
    await userEvent.click(
      await screen.findByRole("button", { name: "Clear all" }),
    )
    expect(onClearAll).toHaveBeenCalled()
  })

  it("hides Clear all when nothing is active", async () => {
    render(
      <FilterPanel activeCount={0} onClearAll={() => {}}>
        <p>fields</p>
      </FilterPanel>,
    )
    await userEvent.click(screen.getByRole("button", { name: /Filters/ }))
    expect(await screen.findByText("fields")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Clear all" })).toBeNull()
  })
})
