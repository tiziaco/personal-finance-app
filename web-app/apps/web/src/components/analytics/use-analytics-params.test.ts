import { renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { useAnalyticsParams } from "./use-analytics-params"

const mocks = vi.hoisted(() => ({ current: "", replace: vi.fn() }))
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(mocks.current),
  usePathname: () => "/analytics",
  useRouter: () => ({ replace: mocks.replace }),
}))

function setup(current: string) {
  mocks.current = current
  return renderHook(() => useAnalyticsParams())
}

describe("useAnalyticsParams", () => {
  beforeEach(() => {
    mocks.replace.mockClear()
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
    expect(mocks.replace).toHaveBeenCalledWith(
      "/analytics?tab=flow&trend_months=12&flow_months=12",
      { scroll: false },
    )
  })

  it("leaves defaults out of the URL", () => {
    const { result, rerender } = setup("tab=flow&flow_months=12")
    result.current.setMonths("flow", 6)
    mocks.current = "tab=flow"
    rerender()
    result.current.setTab("category")
    expect(mocks.replace).toHaveBeenLastCalledWith("/analytics", {
      scroll: false,
    })
  })
})
