import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"

import { formatAmount, formatSignedAmount } from "./format"
import { Money } from "./money"

describe("Money", () => {
  it("renders a transaction signed, income in green", () => {
    render(
      <>
        <Money amount="3200.00" kind="transaction" />
        <Money amount="-84.20" kind="transaction" />
      </>,
    )
    expect(screen.getByText(formatSignedAmount("3200.00"))).toHaveClass(
      "tabular-nums",
      "text-positive",
    )
    expect(screen.getByText(formatSignedAmount("-84.20"))).not.toHaveClass(
      "text-negative",
    )
  })

  it("renders a total unsigned and uncoloured", () => {
    render(<Money amount="-40.00" kind="total" />)
    const el = screen.getByText(formatAmount("-40.00"))
    expect(el).not.toHaveClass("text-positive")
    expect(el).not.toHaveClass("text-negative")
  })

  it("passes span props through, and adds the caller's classes", () => {
    render(<Money amount="-5.00" kind="net" id="net" className="text-sm" />)
    const el = screen.getByText(formatSignedAmount("-5.00"))
    expect(el).toHaveAttribute("id", "net")
    expect(el).toHaveClass("text-negative", "text-sm")
  })
})
