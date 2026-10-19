import { describe, it, expect } from "vitest"
import { render } from "@testing-library/react"
import { BikeIcon, TagIcon } from "lucide-react"

import { CATEGORY_ICONS, CategoryTile, categoryIcon } from "./category-icon"

describe("category icons", () => {
  it("maps every server category and falls back to Tag", () => {
    const slugs = [
      "income",
      "salary",
      "transportation",
      "household_utilities",
      "tax_fines",
      "food_groceries",
      "food_delivery",
      "bars_restaurants",
      "atm",
      "insurances",
      "shopping",
      "education",
      "family_friends",
      "donations_charity",
      "healthcare_drug_stores",
      "leisure_entertainment",
      "media_electronics",
      "savings_investments",
      "travel_holidays",
      "miscellaneous",
    ]
    for (const s of slugs) expect(CATEGORY_ICONS[s]).toBeDefined()
    expect(Object.keys(CATEGORY_ICONS)).toHaveLength(20)
    expect(categoryIcon("food_delivery")).toBe(BikeIcon)
    expect(categoryIcon("not_a_category")).toBe(TagIcon)
  })

  it("falls back to Tag for a slug that names an Object.prototype member", () => {
    for (const s of ["constructor", "toString", "__proto__", "hasOwnProperty"])
      expect(categoryIcon(s)).toBe(TagIcon)
  })

  it("renders a tile for an unknown slug without throwing", () => {
    const { container } = render(<CategoryTile slug="not_a_category" />)
    expect(container.querySelector("svg")).not.toBeNull()
    expect(container.firstElementChild).toHaveAttribute("aria-hidden", "true")
  })
})
