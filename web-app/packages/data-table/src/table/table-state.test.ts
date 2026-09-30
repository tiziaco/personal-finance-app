import { describe, it, expect, vi } from "vitest"
import {
  orderingToSorting,
  sortingToOrdering,
  toServerTableControls,
} from "./table-state"

function state(overrides = {}) {
  return {
    sorting: [],
    pageIndex: 2,
    setPage: vi.fn(),
    setSort: vi.fn(),
    ...overrides,
  }
}

describe("toServerTableControls", () => {
  it("builds TanStack pagination from the state", () => {
    const controls = toServerTableControls(state(), {
      pageSize: 25,
      totalCount: 90,
    })
    expect(controls.pagination).toEqual({ pageIndex: 2, pageSize: 25 })
    expect(controls.totalCount).toBe(90)
  })

  it("resolves a functional pagination updater against the current page", () => {
    const s = state()
    const controls = toServerTableControls(s, { pageSize: 25, totalCount: 90 })
    controls.onPaginationChange((p) => ({ ...p, pageIndex: p.pageIndex + 1 }))
    expect(s.setPage).toHaveBeenCalledWith(3)
  })

  it("resolves a functional sorting updater against the current sort", () => {
    const s = state({ sorting: [{ id: "name", desc: false }] })
    const controls = toServerTableControls(s, { pageSize: 25, totalCount: 90 })
    controls.onSortingChange((prev) => prev.map((c) => ({ ...c, desc: true })))
    expect(s.setSort).toHaveBeenCalledWith([{ id: "name", desc: true }])
  })
})

describe("ordering conversion", () => {
  it("reads a leading dash as descending", () => {
    expect(orderingToSorting("-created_at")).toEqual([
      { id: "created_at", desc: true },
    ])
    expect(orderingToSorting("name")).toEqual([{ id: "name", desc: false }])
    expect(orderingToSorting(null)).toEqual([])
  })

  it("writes the first sort column only", () => {
    expect(sortingToOrdering([{ id: "total", desc: true }])).toBe("-total")
    expect(sortingToOrdering([])).toBeNull()
  })
})
