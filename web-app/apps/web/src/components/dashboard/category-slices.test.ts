import { describe, it, expect } from "vitest"
import { toCategorySlices } from "./category-slices"
import { formatAmount } from "@/components/transactions/format"

const label = (slug: string) =>
  ({
    household_utilities: "Household & Utilities",
    food_groceries: "Food & Groceries",
  })[slug] ?? slug

describe("toCategorySlices", () => {
  it("labels categories, names the null slice Other and colours slices in order", () => {
    const slices = toCategorySlices(
      [
        { category: "household_utilities", amount: "900.00", share_pct: 81.82 },
        { category: "food_groceries", amount: "150.00", share_pct: 13.64 },
        { category: null, amount: "50.00", share_pct: 4.55 },
      ],
      label,
    )
    expect(slices).toEqual([
      {
        key: "household_utilities",
        name: "Household & Utilities",
        amount: 900,
        display: formatAmount("900.00"),
        share: 81.82,
        fill: "var(--chart-1)",
      },
      {
        key: "food_groceries",
        name: "Food & Groceries",
        amount: 150,
        display: formatAmount("150.00"),
        share: 13.64,
        fill: "var(--chart-2)",
      },
      {
        key: "other",
        name: "Other",
        amount: 50,
        display: formatAmount("50.00"),
        share: 4.55,
        fill: "var(--chart-6)",
      },
    ])
  })
})
