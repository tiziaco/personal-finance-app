import { describe, it, expect } from "vitest"
import type { WeekdaySpendResponse } from "@app/api-client/types"
import { formatAmount } from "@/components/transactions/format"
import { toMonthOfYearPoints, toWeekdayPoints } from "./seasonality-points"

const NAMES = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
]
const day = (i: number): WeekdaySpendResponse => ({
  weekday: i,
  name: NAMES[i],
  total: "300.00",
  count: 10,
  days: 20,
  per_day: "15.00",
  average: "30.00",
  share_pct: 14.3,
})

describe("toWeekdayPoints", () => {
  it("keeps Monday first and per-day text", () => {
    const points = toWeekdayPoints(NAMES.map((_, i) => day(i)))
    expect(points).toHaveLength(7)
    const jan1 = new Date(2024, 0, 1)
    expect(points[0].label).toBe(
      new Intl.DateTimeFormat(undefined, { weekday: "short" }).format(jan1),
    )
    expect(points[0].name).toBe(
      new Intl.DateTimeFormat(undefined, { weekday: "long" }).format(jan1),
    )
    expect(points[6].name).toBe(
      new Intl.DateTimeFormat(undefined, { weekday: "long" }).format(
        new Date(2024, 0, 7),
      ),
    )
    expect(points[0].perDay).toBe(15)
    expect(points[0].perDayText).toBe(formatAmount("15.00"))
    expect(points[0].averageText).toBe(formatAmount("30.00"))
    expect(points[0].count).toBe(10)
    expect(points[0].days).toBe(20)
  })
})

describe("toMonthOfYearPoints", () => {
  it("leaves a month with no years without a bar", () => {
    const [p] = toMonthOfYearPoints([
      { month: 2, average_spend: "0.00", index: null, years: 0 },
    ])
    expect(p.average).toBeNull()
    expect(p.indexText).toBe("no data yet")
    expect(p.label).toBe(
      new Intl.DateTimeFormat(undefined, { month: "short" }).format(
        new Date(2000, 1, 1),
      ),
    )
  })

  it("labels the index", () => {
    const [p] = toMonthOfYearPoints([
      { month: 12, average_spend: "2400.00", index: 135, years: 2 },
    ])
    expect(p.average).toBe(2400)
    expect(p.averageText).toBe(formatAmount("2400.00"))
    expect(p.indexText).toBe("35% above a typical month")
    expect(p.years).toBe(2)
  })
})
