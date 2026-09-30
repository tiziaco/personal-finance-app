import { beforeEach, describe, expect, it } from "vitest"
import { act, renderHook } from "@testing-library/react"
import { useStoredColumnVisibility } from "./use-stored-column-visibility"

const DEFAULTS = { sku: false }

describe("useStoredColumnVisibility", () => {
  beforeEach(() => window.localStorage.clear())

  it("returns the defaults when nothing is stored", () => {
    const { result } = renderHook(() =>
      useStoredColumnVisibility("t", DEFAULTS),
    )
    expect(result.current.columnVisibility).toEqual({ sku: false })
  })

  it("merges the stored value over the defaults", () => {
    window.localStorage.setItem(
      "table-columns:t",
      JSON.stringify({ sku: true, stock: false }),
    )
    const { result } = renderHook(() =>
      useStoredColumnVisibility("t", DEFAULTS),
    )
    expect(result.current.columnVisibility).toEqual({ sku: true, stock: false })
  })

  it("persists a change and reflects it", () => {
    const { result } = renderHook(() =>
      useStoredColumnVisibility("t", DEFAULTS),
    )
    act(() =>
      result.current.onColumnVisibilityChange({ sku: true, price: false }),
    )
    expect(result.current.columnVisibility).toEqual({ sku: true, price: false })
    expect(JSON.parse(window.localStorage.getItem("table-columns:t")!)).toEqual(
      { sku: true, price: false },
    )
  })

  it("falls back to the defaults on corrupt JSON", () => {
    window.localStorage.setItem("table-columns:t", "{not json")
    const { result } = renderHook(() =>
      useStoredColumnVisibility("t", DEFAULTS),
    )
    expect(result.current.columnVisibility).toEqual({ sku: false })
  })
})
