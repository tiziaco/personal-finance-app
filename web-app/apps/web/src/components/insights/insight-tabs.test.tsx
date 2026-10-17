import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { InsightResponse } from "@app/api-client/types"
import { InsightTabs } from "./insight-tabs"

const make = (
  summary: string,
  severity: InsightResponse["severity"],
  section: InsightResponse["section"],
) =>
  ({
    summary,
    severity,
    section,
    narrative: "n",
    period: "month",
  }) as InsightResponse

const INSIGHTS = [
  make("Low spend", "low", "spending"),
  make("Big anomaly", "critical", "anomalies"),
  make("Other spend", "high", "spending"),
]

const ui = (
  <InsightTabs
    insights={INSIGHTS}
    referenceMonth="2026-09"
    monthToDateThrough={null}
  />
)

describe("InsightTabs", () => {
  it("lists All first, sorted by severity, with section counts", () => {
    render(ui)
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual([
      "All 3",
      "Spending 2",
      "Recurring 0",
      "Savings 0",
      "Anomalies 1",
      "Comparisons 0",
    ])
    const summaries = screen
      .getAllByTestId("insight-summary")
      .map((e) => e.textContent)
    expect(summaries).toEqual(["Big anomaly", "Other spend", "Low spend"])
  })

  it("filters to a section", async () => {
    render(ui)
    await userEvent.click(screen.getByRole("tab", { name: /Spending/ }))
    expect(screen.getAllByTestId("insight-summary")).toHaveLength(2)
    expect(screen.queryByText("Big anomaly")).not.toBeInTheDocument()
  })

  it("says so for an empty tab", async () => {
    render(ui)
    await userEvent.click(screen.getByRole("tab", { name: /Savings/ }))
    expect(
      screen.getByText("No Savings insights this time."),
    ).toBeInTheDocument()
  })
})
