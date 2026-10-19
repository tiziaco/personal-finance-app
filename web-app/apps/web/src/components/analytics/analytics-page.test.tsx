import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { withNuqsTestingAdapter } from "@app/data-table/url-state/testing"
import { describe, expect, it, vi } from "vitest"

import { HUB_NAV } from "@/lib/hub-nav"

import { AnalyticsPage } from "./analytics-page"

type Props = { months: number }
vi.mock("./category-tab", () => ({
  CategoryTab: ({ months }: Props) => <div>category {months}</div>,
}))
vi.mock("./flow-tab", () => ({
  FlowTab: ({ months }: Props) => <div>flow {months}</div>,
}))
vi.mock("./trends-tab", () => ({
  TrendsTab: ({ months }: Props) => <div>trends {months}</div>,
}))
vi.mock("./seasonality-tab", () => ({
  SeasonalityTab: () => <div>seasonality</div>,
}))

function setup(
  searchParams: string,
  onUrlUpdate?: (searchParams: URLSearchParams) => void,
) {
  return render(<AnalyticsPage />, {
    wrapper: withNuqsTestingAdapter({
      searchParams,
      onUrlUpdate: (update) => onUrlUpdate?.(update.searchParams),
    }),
  })
}

describe("AnalyticsPage", () => {
  it("opens By category by default", () => {
    setup("")
    expect(
      screen.getByRole("heading", { level: 1, name: "Analytics" }),
    ).toBeTruthy()
    expect(screen.getByText("category 3")).toBeTruthy()
    expect(screen.queryByText(/^flow/)).toBeNull()
  })

  it("names its tabs in sentence case", () => {
    setup("")
    for (const name of [
      "By category",
      "Income vs expenses",
      "Trends",
      "Seasonality",
    ])
      expect(screen.getByRole("tab", { name })).toBeTruthy()
  })

  it("opens the tab in the URL with its period", () => {
    setup("?tab=trends&trend_months=12")
    expect(screen.getByText("trends 12")).toBeTruthy()
    expect(screen.queryByText(/^category/)).toBeNull()
    expect(screen.queryByText(/^flow/)).toBeNull()
    expect(screen.queryByText(/^seasonality/)).toBeNull()
  })

  it("switching tab writes the URL", async () => {
    const onUrlUpdate = vi.fn()
    setup("", onUrlUpdate)
    fireEvent.click(screen.getByRole("tab", { name: "Seasonality" }))
    await waitFor(() => expect(onUrlUpdate).toHaveBeenCalled())
    expect(onUrlUpdate.mock.lastCall?.[0].get("tab")).toBe("seasonality")
  })

  it("lists Analytics after Transactions", () => {
    expect(HUB_NAV.map((i) => i.title)).toEqual([
      "Home",
      "Transactions",
      "Analytics",
      "Insights",
      "Chat",
    ])
  })
})
