import { describe, it, expect } from "vitest"
import {
  dateFilterLabel,
  isDateFilterActive,
  usesFrom,
  usesTo,
} from "./date-filter"

describe("dateFilterLabel", () => {
  it("labels each mode by the bounds it uses", () => {
    expect(
      dateFilterLabel("Created", {
        mode: "gte",
        date1: "2026-01-01",
        date2: "",
      }),
    ).toBe("Created ≥ 2026-01-01")
    expect(
      dateFilterLabel("Created", {
        mode: "lte",
        date1: "",
        date2: "2026-02-01",
      }),
    ).toBe("Created ≤ 2026-02-01")
    expect(
      dateFilterLabel("Created", {
        mode: "range",
        date1: "2026-01-01",
        date2: "2026-02-01",
      }),
    ).toBe("Created 2026-01-01 – 2026-02-01")
  })

  it("labels a one-sided range by the bound that is set", () => {
    expect(
      dateFilterLabel("Created", {
        mode: "range",
        date1: "",
        date2: "2026-02-01",
      }),
    ).toBe("Created ≤ 2026-02-01")
  })

  it("is null when nothing filters", () => {
    expect(
      dateFilterLabel("Created", { mode: "gte", date1: "", date2: "" }),
    ).toBeNull()
    expect(
      dateFilterLabel("Created", {
        mode: null,
        date1: "2026-01-01",
        date2: "",
      }),
    ).toBeNull()
    expect(isDateFilterActive({ mode: "gte", date1: "", date2: "" })).toBe(
      false,
    )
  })
})

describe("usesFrom / usesTo", () => {
  it("maps modes to the inputs they show", () => {
    expect([usesFrom("gte"), usesTo("gte")]).toEqual([true, false])
    expect([usesFrom("lte"), usesTo("lte")]).toEqual([false, true])
    expect([usesFrom("range"), usesTo("range")]).toEqual([true, true])
    expect([usesFrom(null), usesTo(null)]).toEqual([false, false])
  })
})
