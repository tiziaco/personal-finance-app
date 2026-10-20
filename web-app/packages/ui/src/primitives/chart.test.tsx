import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { ChartContainer, ChartTooltipContent } from "./chart"

// jsdom has no layout: the real container measures 0×0 and renders no children.
vi.mock("recharts", async (orig) => ({
  ...(await orig()),
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
}))

const config = { avg: { label: "Average", color: "red" } }

describe("ChartTooltipContent", () => {
  it("leaves out a series drawn with tooltipType none", () => {
    render(
      <ChartContainer config={config}>
        <ChartTooltipContent
          active
          payload={[
            { dataKey: "avg", value: 1, type: "none" },
            { dataKey: "avg", value: 2 },
          ]}
        />
      </ChartContainer>,
    )
    expect(screen.getAllByText("Average")).toHaveLength(1)
    expect(screen.queryByText("1")).toBeNull()
  })

  it("renders nothing when every series is hidden", () => {
    const { container } = render(
      <ChartContainer config={config}>
        <ChartTooltipContent
          active
          label="Jan"
          payload={[{ dataKey: "avg", value: 1, type: "none" }]}
        />
      </ChartContainer>,
    )
    expect(screen.queryByText("Jan")).toBeNull()
    expect(container.querySelector(".bg-popover")).toBeNull()
  })
})
