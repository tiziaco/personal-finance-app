import { describe, it, expect } from "vitest"
import type { InsightLinkResponse } from "@app/api-client/types"
import { insightHref } from "./insight-link"

const href = (
  link: InsightLinkResponse | null | undefined,
  period: "month" | "month_to_date" = "month",
) => insightHref(link, period, "2026-09", "2026-10-14")

describe("insightHref", () => {
  it("is null without a link", () => {
    expect(href(null)).toBeNull()
    expect(href(undefined)).toBeNull()
  })

  it("links recurring with no dates", () => {
    expect(href({ kind: "recurring" })).toBe("/transactions?is_recurring=true")
  })

  it("links a category over the reference month", () => {
    expect(href({ kind: "category", category: "food_groceries" })).toBe(
      "/transactions?category=food_groceries&date_from=2026-09-01&date_to=2026-09-30",
    )
  })

  it("links a category over the month so far", () => {
    expect(
      href({ kind: "category", category: "food_groceries" }, "month_to_date"),
    ).toBe(
      "/transactions?category=food_groceries&date_from=2026-10-01&date_to=2026-10-14",
    )
  })

  it("encodes a merchant", () => {
    expect(href({ kind: "merchant", merchant: "Café & Bar" })).toBe(
      "/transactions?search=Caf%C3%A9%20%26%20Bar&date_from=2026-09-01&date_to=2026-09-30",
    )
  })

  it("handles February's last day", () => {
    expect(
      insightHref(
        { kind: "category", category: "x" },
        "month",
        "2028-02",
        null,
      ),
    ).toBe("/transactions?category=x&date_from=2028-02-01&date_to=2028-02-29")
  })

  it("is null when the link lacks its target or the period lacks its month", () => {
    expect(href({ kind: "category" })).toBeNull()
    expect(href({ kind: "merchant", merchant: "" })).toBeNull()
    expect(
      insightHref(
        { kind: "category", category: "x" },
        "month_to_date",
        "2026-09",
        null,
      ),
    ).toBeNull()
  })
})
