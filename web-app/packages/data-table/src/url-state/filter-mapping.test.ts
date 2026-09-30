import { describe, it, expect } from "vitest"
import {
  compactQuery,
  dateMode,
  dateVal,
  toMulti,
  toSingle,
} from "./filter-mapping"

describe("filterMapping", () => {
  it("treats 0 as a real id", () => {
    expect(toSingle([0])).toBe(0)
    expect(toMulti(0)).toEqual([0])
    expect(toSingle([])).toBeNull()
    expect(toMulti(null)).toEqual([])
  })

  it("dateVal drops a date the mode doesn't use", () => {
    const d = { mode: "gte" as const, date1: "2026-01-01", date2: "2026-02-01" }
    expect(dateVal(d, 1)).toBe("2026-01-01")
    expect(dateVal(d, 2)).toBeNull()
  })

  it("dateMode infers a mode for links without one", () => {
    expect(dateMode("a", "b")).toBe("range")
    expect(dateMode("a", null)).toBe("gte")
    expect(dateMode(null, "b")).toBe("lte")
    expect(dateMode(null, null)).toBeNull()
  })

  it("re-exports compactQuery", () => {
    expect(compactQuery({ a: "", b: 1 })).toEqual({ b: 1 })
  })
})
