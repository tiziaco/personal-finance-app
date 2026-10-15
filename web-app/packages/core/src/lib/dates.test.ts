import { describe, it, expect } from "vitest"
import { isIsoDay, parseIsoDay, toIsoDay } from "./dates"

describe("dates", () => {
  it("round-trips a local day", () => {
    expect(toIsoDay(new Date(2026, 2, 3))).toBe("2026-03-03")
    expect(toIsoDay(parseIsoDay("2026-03-03")!)).toBe("2026-03-03")
  })

  it("rejects what is not a real day, without throwing", () => {
    for (const bad of [
      "",
      "foo",
      "2026-0",
      "2026-1-1",
      "2026-02-30",
      "2026-13-01",
    ])
      expect(parseIsoDay(bad)).toBeUndefined()
    expect(isIsoDay("2024-02-29")).toBe(true)
  })
})
