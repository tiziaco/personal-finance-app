import { describe, it, expect } from "vitest"
import { formatAmount, isExpense, isLowConfidence } from "./format"

describe("format", () => {
  it("formats an amount string as EUR without float maths", () => {
    expect(formatAmount("-4.50")).toMatch(/4[.,]50/)
    expect(formatAmount("1234567890.12")).toMatch(/1.?234.?567.?890[.,]12/)
  })
  it("reads the sign from the string", () => {
    expect(isExpense("-0.01")).toBe(true)
    expect(isExpense("0.00")).toBe(false)
  })
  it("flags confidence below 70%", () => {
    expect(isLowConfidence(0.69)).toBe(true)
    expect(isLowConfidence(0.7)).toBe(false)
  })
})
