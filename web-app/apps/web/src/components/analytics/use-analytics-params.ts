"use client"

import {
  createParser,
  parseAsNumberLiteral,
  parseAsStringLiteral,
  useQueryStates,
} from "@app/data-table/url-state/params"

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

// parseAsNumberLiteral reads "12abc" as 12 (it goes through parseFloat); a
// period is a whole-number string and nothing else.
function parseAsPeriod<T extends number>(choices: readonly T[]) {
  const literal = parseAsNumberLiteral(choices)
  return createParser<T>({
    parse: (query) => (/^\d+$/.test(query) ? literal.parse(query) : null),
    serialize: literal.serialize,
  })
}

// The tab and each ranged tab's period, in the URL. A value outside the offered
// choices reads as the default; writing the default removes its key.
const analyticsParsers = {
  tab: parseAsStringLiteral(ANALYTICS_TABS).withDefault("category"),
  [PERIODS.category.key]: parseAsPeriod(PERIODS.category.choices).withDefault(
    PERIODS.category.fallback,
  ),
  [PERIODS.flow.key]: parseAsPeriod(PERIODS.flow.choices).withDefault(
    PERIODS.flow.fallback,
  ),
  [PERIODS.trends.key]: parseAsPeriod(PERIODS.trends.choices).withDefault(
    PERIODS.trends.fallback,
  ),
}

export function useAnalyticsParams() {
  // Replace history and skip the server round trip: the tabs fetch their own data.
  const [params, setParams] = useQueryStates(analyticsParsers, {
    history: "replace",
    shallow: true,
    clearOnDefault: true,
  })

  return {
    tab: params.tab,
    setTab: (next: AnalyticsTab) => setParams({ tab: next }),
    months: (forTab: RangedTab): number => params[PERIODS[forTab].key],
    setMonths: (forTab: RangedTab, value: number) =>
      setParams({ [PERIODS[forTab].key]: value }),
  }
}
