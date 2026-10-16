import { describe, it, expect } from "vitest"
import { formatKeyFigure } from "./key-figure"

describe("formatKeyFigure", () => {
  it("formats an amount as money", () => {
    expect(
      formatKeyFigure({ kind: "amount", value: "1234.50", qualifier: "" }),
    ).toMatch(/^€\s?1,?234\.50$|1.?234[.,]50\s?€/)
  })

  it("always signs a percent: no decimals from 10, one below", () => {
    expect(
      formatKeyFigure({ kind: "percent", value: "12.4", qualifier: "" }),
    ).toBe("+12%")
    expect(
      formatKeyFigure({ kind: "percent", value: "-8", qualifier: "" }),
    ).toBe("−8.0%")
    expect(
      formatKeyFigure({ kind: "percent", value: "-25.6", qualifier: "" }),
    ).toBe("−26%")
    expect(
      formatKeyFigure({ kind: "percent", value: "3.25", qualifier: "" }),
    ).toBe("+3.3%")
  })

  it("leaves a count as is", () => {
    expect(formatKeyFigure({ kind: "count", value: "4", qualifier: "" })).toBe(
      "4",
    )
  })

  it("appends a non-empty qualifier", () => {
    expect(
      formatKeyFigure({ kind: "percent", value: "12", qualifier: "vs August" }),
    ).toBe("+12% vs August")
    expect(formatKeyFigure({ kind: "count", value: "4", qualifier: "" })).toBe(
      "4",
    )
  })
})
