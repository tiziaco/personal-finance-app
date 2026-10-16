import { describe, it, expect } from "vitest"
import { formatMonth } from "@/components/dashboard/month"
import {
  changeTone,
  formatDayRange,
  formatIndex,
  formatPct,
  formatPeriod,
  partialLabel,
  purchases,
} from "./format"

const d = (iso: string) => {
  const [y, m, day] = iso.split("-").map(Number)
  return new Date(y, m - 1, day)
}
const range = (o: Intl.DateTimeFormatOptions, a: string, b: string) =>
  new Intl.DateTimeFormat(undefined, o).formatRange(d(a), d(b))
const MONTHS = { month: "short", year: "numeric" } as const
const DAYS = { day: "numeric", month: "short", year: "numeric" } as const

describe("formatPeriod", () => {
  it("names one whole month", () =>
    expect(formatPeriod("2026-09-01", "2026-09-30")).toBe(
      formatMonth("2026-09"),
    ))
  it("ranges whole months by month", () =>
    expect(formatPeriod("2026-07-01", "2026-09-30")).toBe(
      range(MONTHS, "2026-07-01", "2026-09-30"),
    ))
  it("ranges across a year by month", () =>
    expect(formatPeriod("2025-11-01", "2026-01-31")).toBe(
      range(MONTHS, "2025-11-01", "2026-01-31"),
    ))
  it("gives days for the month in progress", () =>
    expect(formatPeriod("2026-10-01", "2026-10-16")).toBe(
      range(DAYS, "2026-10-01", "2026-10-16"),
    ))
  it("gives days when the data starts mid-month", () =>
    expect(formatPeriod("2026-09-12", "2026-10-31")).toBe(
      range(DAYS, "2026-09-12", "2026-10-31"),
    ))
  it("treats 29 Feb as a month end", () =>
    expect(formatPeriod("2028-02-01", "2028-02-29")).toBe(
      formatMonth("2028-02"),
    ))
  it("is null for an invalid day rather than rolling over", () =>
    expect(formatPeriod("2026-02-30", "2026-03-31")).toBeNull())
  it("is null when the period is empty", () =>
    expect(formatPeriod(null, null)).toBeNull())
})

describe("changeTone", () => {
  it("spending up is bad, down is good", () => {
    expect(changeTone(12, "spend")).toBe("bad")
    expect(changeTone(-3, "spend")).toBe("good")
  })
  it("income up is good, down is bad", () => {
    expect(changeTone(4, "income")).toBe("good")
    expect(changeTone(-4, "income")).toBe("bad")
  })
  it("zero and null are neutral", () => {
    expect(changeTone(0, "spend")).toBe("neutral")
    expect(changeTone(null, "income")).toBe("neutral")
  })
})

describe("formatIndex", () => {
  it("above", () => expect(formatIndex(135)).toBe("35% above a typical month"))
  it("below", () => expect(formatIndex(88.4)).toBe("12% below a typical month"))
  it("typical", () => expect(formatIndex(100.3)).toBe("a typical month"))
  it("no data", () => expect(formatIndex(null)).toBe("no data yet"))
})

describe("formatPct", () => {
  const one = (n: number) =>
    `${new Intl.NumberFormat(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(n)}%`
  it("one decimal, sign kept", () => {
    expect(formatPct(8.24)).toBe(one(8.24))
    expect(formatPct(-12)).toBe(one(-12))
  })
})

describe("formatDayRange", () => {
  const DM = { day: "numeric", month: "short" } as const
  it("days 1 to the given day", () =>
    expect(formatDayRange("2026-10", 16)).toBe(
      range(DM, "2026-10-01", "2026-10-16"),
    ))
  it("clamps to a shorter month", () =>
    expect(formatDayRange("2026-09", 31)).toBe(
      range(DM, "2026-09-01", "2026-09-30"),
    ))
})

describe("purchases", () => {
  it("pluralises", () => {
    expect(purchases(0)).toBe("0 purchases")
    expect(purchases(1)).toBe("1 purchase")
    expect(purchases(2)).toBe("2 purchases")
  })
})

describe("partialLabel", () => {
  it("says so far only for the month in progress", () => {
    expect(partialLabel(true, "2026-10", "2026-10")).toBe("so far")
    expect(partialLabel(true, "2026-04", "2026-10")).toBe("partial")
    expect(partialLabel(true, "2026-04", undefined)).toBe("partial")
    expect(partialLabel(false, "2026-10", "2026-10")).toBeNull()
  })
})
