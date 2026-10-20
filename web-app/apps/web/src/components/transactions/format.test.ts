import { describe, it, expect } from "vitest"
import {
  amountClass,
  amountSign,
  formatAmount,
  formatMoney,
  formatPercent,
  formatSignedAmount,
  isLowConfidence,
} from "./format"

describe("format", () => {
  it("formats an amount string as EUR without float maths", () => {
    expect(formatAmount("-4.50")).toMatch(/4[.,]50/)
    expect(formatAmount("1234567890.12")).toMatch(/1.?234.?567.?890[.,]12/)
  })
  describe("amountSign", () => {
    it("reads the sign from the string, not a float", () => {
      expect(amountSign("-0.01")).toBe(-1)
      expect(amountSign("12.00")).toBe(1)
      expect(amountSign("+12.00")).toBe(1)
      expect(amountSign(" -3.10 ")).toBe(-1)
    })
    it("calls every zero zero, signed or not", () => {
      expect(amountSign("0.00")).toBe(0)
      expect(amountSign("-0.00")).toBe(0)
      expect(amountSign("+0")).toBe(0)
    })
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
  describe("formatMoney", () => {
    it("leaves a total unsigned and signs every other kind", () => {
      expect(formatMoney("-84.20", "total")).toBe(formatAmount("-84.20"))
      for (const kind of ["transaction", "net", "spendChange"] as const)
        expect(formatMoney("-84.20", kind)).toBe(formatSignedAmount("-84.20"))
    })
  })
  describe("amountClass", () => {
    it("never colours a total", () => {
      expect(amountClass("12.00", "total")).toBe("")
      expect(amountClass("-12.00", "total")).toBe("")
    })
    it("greens a transaction's income only", () => {
      expect(amountClass("12.00", "transaction")).toBe("text-positive")
      expect(amountClass("-12.00", "transaction")).toBe("")
      expect(amountClass("0.00", "transaction")).toBe("")
    })
    it("tones a net good when up", () => {
      expect(amountClass("5.00", "net")).toBe("text-positive")
      expect(amountClass("-5.00", "net")).toBe("text-negative")
      expect(amountClass("-0.00", "net")).toBe("")
    })
    it("tones a change in spending good when down", () => {
      expect(amountClass("-5.00", "spendChange")).toBe("text-positive")
      expect(amountClass("5.00", "spendChange")).toBe("text-negative")
      expect(amountClass("0.00", "spendChange")).toBe("")
    })
  })
})
