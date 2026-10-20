import { describe, it, expect } from "vitest"
import { render } from "@testing-library/react"
import { BikeIcon, TagIcon } from "lucide-react"
import { Category } from "@app/api-client/types"

import { CATEGORY_ICONS, CategoryTile, categoryIcon } from "./category-icon"

describe("category icons", () => {
  it("maps every category in the contract and falls back to Tag", () => {
    for (const slug of Object.values(Category))
      expect(CATEGORY_ICONS[slug]).toBeDefined()
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
