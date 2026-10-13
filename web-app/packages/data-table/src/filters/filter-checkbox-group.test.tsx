import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { FilterCheckboxGroup } from "./filter-checkbox-group"

const options = [
  { value: "a", label: "Alpha" },
  { value: "b", label: "Beta" },
] as const

describe("FilterCheckboxGroup", () => {
  it("adds and removes values, keeping option order", () => {
    const onChange = vi.fn()
    const { rerender } = render(
      <FilterCheckboxGroup
        label="Category"
        options={[...options]}
        value={["b"]}
        onChange={onChange}
      />,
    )
    fireEvent.click(screen.getByRole("checkbox", { name: "Alpha" }))
    expect(onChange).toHaveBeenLastCalledWith(["a", "b"])
    rerender(
      <FilterCheckboxGroup
        label="Category"
        options={[...options]}
        value={["a", "b"]}
        onChange={onChange}
      />,
    )
    fireEvent.click(screen.getByRole("checkbox", { name: "Beta" }))
    expect(onChange).toHaveBeenLastCalledWith(["a"])
  })
})
