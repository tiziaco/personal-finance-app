import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { FilterChip } from "./filter-chip"

describe("FilterChip", () => {
  it("removes itself", async () => {
    const onRemove = vi.fn()
    render(<FilterChip label="Status: Shipped" onRemove={onRemove} />)
    await userEvent.click(
      screen.getByRole("button", { name: "Remove Status: Shipped" }),
    )
    expect(onRemove).toHaveBeenCalled()
  })
})
