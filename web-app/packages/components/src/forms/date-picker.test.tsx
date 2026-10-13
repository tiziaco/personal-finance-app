import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { DatePicker } from "./date-picker"

describe("DatePicker", () => {
  it("shows the placeholder when empty", () => {
    render(
      <DatePicker value="" onChange={() => {}} placeholder="Pick a date" />,
    )
    expect(
      screen.getByRole("button", { name: /Pick a date/ }),
    ).toBeInTheDocument()
  })

  it("shows the chosen day as a local date", () => {
    render(<DatePicker value="2026-03-03" onChange={() => {}} />)
    expect(
      screen.getByRole("button", { name: /2026|Mar|3/ }),
    ).toHaveTextContent(/3/)
  })

  it("reports a picked day as local ISO, never shifted by the timezone", () => {
    const onChange = vi.fn()
    render(<DatePicker value="2026-03-03" onChange={onChange} />)
    fireEvent.click(screen.getByRole("button"))
    fireEvent.click(screen.getByRole("button", { name: /March 14/ }))
    expect(onChange).toHaveBeenCalledWith("2026-03-14")
  })
})
