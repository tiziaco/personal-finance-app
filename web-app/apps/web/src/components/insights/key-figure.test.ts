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

  it("decides decimals from the rounded value", () => {
    expect(
      formatKeyFigure({ kind: "percent", value: "9.96", qualifier: "" }),
    ).toBe("+10%")
    expect(
      formatKeyFigure({ kind: "percent", value: "-9.96", qualifier: "" }),
    ).toBe("−10%")
  })

  it("renders the qualifier alone for a non-numeric percent", () => {
    expect(
      formatKeyFigure({
        kind: "percent",
        value: "abc",
        qualifier: "vs August",
      }),
    ).toBe("vs August")
    expect(
      formatKeyFigure({ kind: "percent", value: "abc", qualifier: "" }),
    ).toBe("")
  })
})
