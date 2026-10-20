import { describe, it, expect } from "vitest"

import { cn } from "./utils"

describe("cn", () => {
  it("treats the type scale as font sizes: the later size wins", () => {
    expect(cn("text-sm", "text-caption")).toBe("text-caption")
    expect(cn("text-h3", "text-sm")).toBe("text-sm")
  })

  it("keeps a type-scale size beside a text colour", () => {
    expect(cn("text-h3", "text-muted-foreground")).toBe(
      "text-h3 text-muted-foreground",
    )
  })
})
