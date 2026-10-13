import { describe, it, expect } from "vitest"
import { parseAmount } from "./amount-input"

describe("parseAmount", () => {
  it.each([
    ["-4,50", "-4.50"],
    ["-4.5", "-4.50"],
    ["12", "12.00"],
    [" 2400.00 ", "2400.00"],
    ["+3,2", "3.20"],
    ["9999999999.99", "9999999999.99"],
  ])("%s → %s", (input, expected) => expect(parseAmount(input)).toBe(expected))

  it.each(["", "abc", "4,505", "1.2.3", "-", "12345678901.00", "1e3"])(
    "rejects %s",
    (input) => expect(parseAmount(input)).toBeNull(),
  )
})
