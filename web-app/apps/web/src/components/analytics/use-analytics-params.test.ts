import { act, renderHook } from "@testing-library/react"
import { withNuqsTestingAdapter } from "@app/data-table/url-state/testing"
import { describe, expect, it } from "vitest"

import { useAnalyticsParams } from "./use-analytics-params"

type OnUrlUpdate = NonNullable<
  Parameters<typeof withNuqsTestingAdapter>[0]
>["onUrlUpdate"]
type UrlUpdate = Parameters<NonNullable<OnUrlUpdate>>[0]

function setup(searchParams: string) {
  const updates: UrlUpdate[] = []
  const view = renderHook(() => useAnalyticsParams(), {
    wrapper: withNuqsTestingAdapter({
      searchParams,
      onUrlUpdate: (update) => updates.push(update),
    }),
  })
  return { ...view, updates }
}

describe("useAnalyticsParams", () => {
  it("defaults with an empty URL", () => {
    const { result } = setup("")
    expect(result.current.tab).toBe("category")
    expect(result.current.months("category")).toBe(3)
    expect(result.current.months("flow")).toBe(6)
    expect(result.current.months("trends")).toBe(4)
  })

  it("reads valid values", () => {
    const { result } = setup("?tab=trends&trend_months=24&flow_months=12")
    expect(result.current.tab).toBe("trends")
    expect(result.current.months("trends")).toBe(24)
    expect(result.current.months("flow")).toBe(12)
  })

  it("falls back on unknown or unoffered values", () => {
    const { result } = setup(
      "?tab=nope&flow_months=7&trend_months=abc&category_months=-1",
    )
    expect(result.current.tab).toBe("category")
    expect(result.current.months("flow")).toBe(6)
    expect(result.current.months("trends")).toBe(4)
    expect(result.current.months("category")).toBe(3)
  })

  it("rejects non-integer strings", () => {
    const { result } = setup("?flow_months=12.5&trend_months=12abc")
    expect(result.current.months("flow")).toBe(6)
    expect(result.current.months("trends")).toBe(4)
  })

  it("writes a choice and keeps the other keys", async () => {
    const { result, updates } = setup("?tab=flow&trend_months=12")
    await act(async () => {
      await result.current.setMonths("flow", 12)
    })
    const url = updates.at(-1)?.searchParams
    expect(url?.get("tab")).toBe("flow")
    expect(url?.get("trend_months")).toBe("12")
    expect(url?.get("flow_months")).toBe("12")
    expect(result.current.months("flow")).toBe(12)
  })

  it("leaves defaults out of the URL", async () => {
    const { result, updates } = setup("?tab=flow&flow_months=12")
    await act(async () => {
      await result.current.setMonths("flow", 6)
    })
    expect(updates.at(-1)?.queryString).toBe("?tab=flow")
  })

  it("leaves the default tab out of the URL", async () => {
    const { result, updates } = setup("?tab=flow")
    await act(async () => {
      await result.current.setTab("category")
    })
    expect(updates.at(-1)?.queryString).toBe("")
  })

  it("replaces history and stays shallow", async () => {
    const { result, updates } = setup("")
    await act(async () => {
      await result.current.setTab("seasonality")
      await result.current.setMonths("trends", 12)
    })
    expect(updates.length).toBeGreaterThan(0)
    for (const update of updates) {
      expect(update.options.history).toBe("replace")
      expect(update.options.shallow).toBe(true)
    }
  })
})
