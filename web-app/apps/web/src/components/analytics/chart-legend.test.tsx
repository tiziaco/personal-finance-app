import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import type { ChartConfig } from "@app/ui/chart"
import { ChartLegend } from "./chart-legend"

const config: ChartConfig = {
  expenses: { label: "Expenses", color: "var(--chart-expense)" },
  rollingAvg: { label: "3-month average", color: "var(--muted-foreground)" },
}

describe("ChartLegend", () => {
  it("names every series", () => {
    render(<ChartLegend config={config} />)
    expect(screen.getByText("Expenses")).toBeInTheDocument()
    expect(screen.getByText("3-month average")).toBeInTheDocument()
    expect(screen.getAllByRole("listitem")).toHaveLength(2)
  })
})
