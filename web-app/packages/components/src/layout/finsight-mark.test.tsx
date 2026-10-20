import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"

import { FinsightMark } from "./finsight-mark"

describe("FinsightMark", () => {
  it("is an image named Finsight by default", () => {
    render(<FinsightMark />)
    expect(screen.getByRole("img", { name: "Finsight" })).toBeInTheDocument()
  })

  it("is hidden from screen readers when decorative", () => {
    const { container } = render(<FinsightMark decorative />)
    expect(screen.queryByRole("img")).toBeNull()
    const svg = container.querySelector("svg")
    expect(svg).toHaveAttribute("aria-hidden", "true")
    expect(svg).not.toHaveAttribute("aria-label")
  })
})
