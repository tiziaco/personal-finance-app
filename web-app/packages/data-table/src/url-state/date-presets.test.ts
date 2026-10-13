import { describe, it, expect } from "vitest"
import { datePresetValue } from "./date-presets"

const wed = new Date(2026, 9, 14) // Wed 14 Oct 2026, local time

describe("datePresetValue", () => {
  it("today", () =>
    expect(datePresetValue("today", wed)).toEqual({
      mode: "range",
      date1: "2026-10-14",
      date2: "2026-10-14",
    }))
  it("this week starts Monday", () =>
    expect(datePresetValue("this_week", wed)).toEqual({
      mode: "range",
      date1: "2026-10-12",
      date2: "2026-10-18",
    }))
  it("a Sunday belongs to the week before", () =>
    expect(datePresetValue("this_week", new Date(2026, 9, 18))).toEqual({
      mode: "range",
      date1: "2026-10-12",
      date2: "2026-10-18",
    }))
  it("this month", () =>
    expect(datePresetValue("this_month", wed)).toEqual({
      mode: "range",
      date1: "2026-10-01",
      date2: "2026-10-31",
    }))
  it("last month across a year", () =>
    expect(datePresetValue("last_month", new Date(2026, 0, 10))).toEqual({
      mode: "range",
      date1: "2025-12-01",
      date2: "2025-12-31",
    }))
})
