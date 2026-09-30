import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { act, renderHook } from "@testing-library/react"
import { useLocalTableState } from "./use-local-table-state"

type Filters = { status: string | null; owner: string | null }
const setup = () =>
  renderHook(() =>
    useLocalTableState<Filters>({
      initialFilters: { status: null, owner: null },
    }),
  )

describe("useLocalTableState", () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it("starts on page 1 with no sort or search", () => {
    const { result } = setup()
    expect(result.current.query).toEqual({
      page: 1,
      ordering: null,
      search: "",
      filters: { status: null, owner: null },
    })
    expect(result.current.pageIndex).toBe(0)
  })

  it("resets to page 1 when a filter changes", () => {
    const { result } = setup()
    act(() => result.current.setPage(3))
    expect(result.current.query.page).toBe(4)
    act(() => result.current.setFilters((f) => ({ ...f, status: "active" })))
    expect(result.current.query).toMatchObject({
      page: 1,
      filters: { status: "active" },
    })
  })

  it("writes ordering and resets page when sorting", () => {
    const { result } = setup()
    act(() => result.current.setPage(2))
    act(() => result.current.setSort([{ id: "name", desc: true }]))
    expect(result.current.query).toMatchObject({ page: 1, ordering: "-name" })
    expect(result.current.sorting).toEqual([{ id: "name", desc: true }])
  })

  it("shows typed search at once but debounces it into the query", () => {
    const { result } = setup()
    act(() => result.current.setPage(2))
    act(() => result.current.setSearch("ab"))
    expect(result.current.search).toBe("ab")
    expect(result.current.query.search).toBe("")
    act(() => vi.advanceTimersByTime(300))
    expect(result.current.query).toMatchObject({ search: "ab", page: 1 })
  })

  it("applies a cleared search immediately", () => {
    const { result } = setup()
    act(() => result.current.setSearch("ab"))
    act(() => vi.advanceTimersByTime(300))
    act(() => result.current.setSearch(""))
    expect(result.current.query.search).toBe("")
  })

  it("composes same-tick functional filter updates", () => {
    const { result } = setup()
    act(() => {
      result.current.setFilters((f) => ({ ...f, status: "active" }))
      result.current.setFilters((f) => ({ ...f, owner: "me" }))
    })
    expect(result.current.filters).toEqual({ status: "active", owner: "me" })
  })

  it("keeps setter and sorting identities across a rerender", () => {
    const { result, rerender } = setup()
    const first = result.current
    rerender()
    expect(result.current.setFilters).toBe(first.setFilters)
    expect(result.current.setSort).toBe(first.setSort)
    expect(result.current.setPage).toBe(first.setPage)
    expect(result.current.setSearch).toBe(first.setSearch)
    expect(result.current.sorting).toBe(first.sorting)
  })
})
