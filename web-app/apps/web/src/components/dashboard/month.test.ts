import { describe, it, expect } from "vitest"
import { formatMonth } from "./month"

const expected = (month: "long" | "short") =>
  new Intl.DateTimeFormat(undefined, {
    month,
    year: month === "long" ? "numeric" : undefined,
  }).format(new Date(2026, 8, 1))

describe("formatMonth", () => {
  it("names a YYYY-MM month in the user's locale", () => {
    expect(formatMonth("2026-09")).toBe(expected("long"))
    expect(formatMonth("2026-09", "short")).toBe(expected("short"))
  })

  it("returns the key unchanged when it is not a month", () => {
    expect(formatMonth("nope")).toBe("nope")
  })
})
