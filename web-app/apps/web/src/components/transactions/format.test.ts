import { describe, it, expect } from "vitest"
import {
  formatAmount,
  formatPercent,
  formatSignedAmount,
  isExpense,
  isLowConfidence,
  transactionAmountClass,
} from "./format"

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
  describe("formatPercent", () => {
    const adaptive = { decimals: "adaptive" } as const
    const whole = { decimals: "whole", unsignedZero: true } as const
    it("adaptive: one decimal below 10, none from there, always signed", () => {
      expect(formatPercent(9.4, adaptive)).toBe("+9.4%")
      expect(formatPercent(9.96, adaptive)).toBe("+10%")
      expect(formatPercent(-12.4, adaptive)).toBe("−12%")
      expect(formatPercent(0, adaptive)).toBe("+0.0%")
      expect(formatPercent(-0.04, adaptive)).toBe("+0.0%")
    })
    it("whole: rounds, and a zero has no sign when unsignedZero", () => {
      expect(formatPercent(12.4, whole)).toBe("+12%")
      expect(formatPercent(-4.6, whole)).toBe("−5%")
      expect(formatPercent(0.3, whole)).toBe("0%")
      expect(formatPercent(0.3, { decimals: "whole" })).toBe("+0%")
    })
  })
  describe("formatSignedAmount", () => {
    it("signs with a true minus and a plus, no space", () => {
      expect(formatSignedAmount("-84.20", "en-GB")).toBe("−€84.20")
      expect(formatSignedAmount("3200", "en-GB")).toBe("+€3,200.00")
    })
    it("leads with the sign when the symbol trails", () => {
      expect(formatSignedAmount("-84.20", "it-IT")).toMatch(/^−84,20\s€$/u)
    })
    it("never signs a zero and never emits a hyphen-minus", () => {
      expect(formatSignedAmount("0.00", "en-GB")).toBe("€0.00")
      expect(formatSignedAmount("-0.00", "en-GB")).toBe("€0.00")
      expect(formatSignedAmount("-1.00")).not.toContain("-")
    })
  })
  describe("transactionAmountClass", () => {
    it("greens income only", () => {
      expect(transactionAmountClass("12.00")).toBe("text-positive")
      expect(transactionAmountClass("-12.00")).toBe("")
      expect(transactionAmountClass("0.00")).toBe("")
    })
  })
})
