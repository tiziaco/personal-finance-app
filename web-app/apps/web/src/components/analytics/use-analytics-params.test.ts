import { renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { MockInstance } from "vitest"

import { useAnalyticsParams } from "./use-analytics-params"

const mocks = vi.hoisted(() => ({ current: "" }))
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(mocks.current),
  usePathname: () => "/analytics",
}))

function setup(current: string) {
  mocks.current = current
  return renderHook(() => useAnalyticsParams())
}

describe("useAnalyticsParams", () => {
  let replaceState: MockInstance<History["replaceState"]>

  beforeEach(() => {
    replaceState = vi
      .spyOn(window.history, "replaceState")
      .mockImplementation(() => {})
  })

  afterEach(() => {
    replaceState.mockRestore()
  })

  it("defaults with an empty URL", () => {
    const { result } = setup("")
    expect(result.current.tab).toBe("category")
    expect(result.current.months("category")).toBe(3)
    expect(result.current.months("flow")).toBe(6)
    expect(result.current.months("trends")).toBe(4)
  })

  it("reads valid values", () => {
    const { result } = setup("tab=trends&trend_months=24&flow_months=12")
    expect(result.current.tab).toBe("trends")
    expect(result.current.months("trends")).toBe(24)
    expect(result.current.months("flow")).toBe(12)
  })

  it("falls back on unknown or unoffered values", () => {
    const { result } = setup(
      "tab=nope&flow_months=7&trend_months=abc&category_months=-1",
    )
    expect(result.current.tab).toBe("category")
    expect(result.current.months("flow")).toBe(6)
    expect(result.current.months("trends")).toBe(4)
    expect(result.current.months("category")).toBe(3)
  })

  it("rejects non-integer strings", () => {
    const { result } = setup("flow_months=12.5&trend_months=12abc")
    expect(result.current.months("flow")).toBe(6)
    expect(result.current.months("trends")).toBe(4)
  })

  it("writes a choice and keeps the other keys", () => {
    const { result } = setup("tab=flow&trend_months=12")
    result.current.setMonths("flow", 12)
    expect(replaceState).toHaveBeenCalledWith(
      null,
      "",
      "/analytics?tab=flow&trend_months=12&flow_months=12",
    )
  })

  it("leaves defaults out of the URL", () => {
    const { result, rerender } = setup("tab=flow&flow_months=12")
    result.current.setMonths("flow", 6)
    expect(replaceState).toHaveBeenNthCalledWith(
      1,
      null,
      "",
      "/analytics?tab=flow",
    )
    mocks.current = "tab=flow"
    rerender()
    result.current.setTab("category")
    expect(replaceState).toHaveBeenLastCalledWith(null, "", "/analytics")
  })
})
