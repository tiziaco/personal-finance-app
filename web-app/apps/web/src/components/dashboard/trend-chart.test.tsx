import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { TrendChart } from "./trend-chart"

describe("TrendChart", () => {
  it("dashes the expenses swatch in the legend, as the line is dashed", () => {
    render(
      <TrendChart
        points={[{ month: "2026-09", income: "10", expenses: "5" }]}
      />,
    )
    const swatch = (label: string) =>
      screen.getByText(label).closest("li")!.querySelector("span")!
    expect(swatch("Expenses").className).toContain("border-dashed")
    expect(swatch("Income").className).not.toContain("border-dashed")
  })
})
