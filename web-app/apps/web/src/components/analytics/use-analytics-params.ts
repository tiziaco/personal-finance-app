"use client"

import { usePathname, useSearchParams } from "next/navigation"

export const ANALYTICS_TABS = [
  "category",
  "flow",
  "trends",
  "seasonality",
] as const
export type AnalyticsTab = (typeof ANALYTICS_TABS)[number]

export const PERIODS = {
  category: { key: "category_months", choices: [1, 3, 6], fallback: 3 },
  flow: { key: "flow_months", choices: [3, 6, 12], fallback: 6 },
  trends: { key: "trend_months", choices: [4, 6, 12, 24], fallback: 4 },
} as const
export type RangedTab = keyof typeof PERIODS

/** Whether a value is one of the page's tabs. */
export function isAnalyticsTab(v: unknown): v is AnalyticsTab {
  return ANALYTICS_TABS.some((tab) => tab === v)
}

const DEFAULT_TAB: AnalyticsTab = "category"

export function useAnalyticsParams() {
  const params = useSearchParams()
  const pathname = usePathname()

  const rawTab = params.get("tab")
  const tab = isAnalyticsTab(rawTab) ? rawTab : DEFAULT_TAB

  function months(forTab: RangedTab): number {
    const { key, choices, fallback } = PERIODS[forTab]
    const raw = params.get(key)
    if (raw === null || !/^\d+$/.test(raw)) return fallback
    const value = Number(raw)
    return (choices as readonly number[]).includes(value) ? value : fallback
  }

  function write(key: string, value: string, fallback: string) {
    const next = new URLSearchParams(params.toString())
    if (value === fallback) next.delete(key)
    else next.set(key, value)
    const qs = next.toString()
    // Update the URL without fetching the page again from the server; Next
    // keeps useSearchParams in sync with history.replaceState.
    window.history.replaceState(null, "", qs ? `${pathname}?${qs}` : pathname)
  }

  return {
    tab,
    setTab: (next: AnalyticsTab) => write("tab", next, DEFAULT_TAB),
    months,
    setMonths: (forTab: RangedTab, value: number) =>
      write(
        PERIODS[forTab].key,
        String(value),
        String(PERIODS[forTab].fallback),
      ),
  }
}
