import { describe, it, expect } from "vitest"
import { pruneSelection } from "./row-selection"

describe("pruneSelection", () => {
  it("keeps only rows still on screen", () => {
    expect(
      pruneSelection({ a: true, b: true, c: true }, ["b", "c", "d"]),
    ).toEqual({ b: true, c: true })
  })
  it("drops unselected entries", () => {
    expect(pruneSelection({ a: false, b: true }, ["a", "b"])).toEqual({
      b: true,
    })
  })
  it("returns the same object when nothing changes", () => {
    const s = { a: true }
    expect(pruneSelection(s, ["a"])).toBe(s)
  })
})
