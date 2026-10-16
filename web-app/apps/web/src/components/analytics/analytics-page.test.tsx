import { fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { MockInstance } from "vitest"

import { HUB_NAV } from "@/lib/hub-nav"

import { AnalyticsPage } from "./analytics-page"

const mocks = vi.hoisted(() => ({ current: "" }))
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(mocks.current),
  usePathname: () => "/analytics",
}))

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

function setup(current: string) {
  mocks.current = current
  return render(<AnalyticsPage />)
}

describe("AnalyticsPage", () => {
  let replaceState: MockInstance<History["replaceState"]>

  beforeEach(() => {
    replaceState = vi
      .spyOn(window.history, "replaceState")
      .mockImplementation(() => {})
  })

  afterEach(() => {
    replaceState.mockRestore()
  })

  it("opens By Category by default", () => {
    setup("")
    expect(
      screen.getByRole("heading", { level: 1, name: "Analytics" }),
    ).toBeTruthy()
    expect(screen.getByText("category 3")).toBeTruthy()
    expect(screen.queryByText(/^flow/)).toBeNull()
  })

  it("opens the tab in the URL with its period", () => {
    setup("tab=trends&trend_months=12")
    expect(screen.getByText("trends 12")).toBeTruthy()
    expect(screen.queryByText(/^category/)).toBeNull()
    expect(screen.queryByText(/^flow/)).toBeNull()
    expect(screen.queryByText(/^seasonality/)).toBeNull()
  })

  it("switching tab writes the URL", () => {
    setup("")
    fireEvent.click(screen.getByRole("tab", { name: "Seasonality" }))
    expect(replaceState).toHaveBeenCalledWith(
      null,
      "",
      "/analytics?tab=seasonality",
    )
  })

  it("lists Analytics after Transactions", () => {
    expect(HUB_NAV.map((i) => i.title)).toEqual([
      "Home",
      "Transactions",
      "Analytics",
      "Chat",
    ])
  })
})
