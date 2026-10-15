import { describe, it, expect, vi } from "vitest"
import { renderHook } from "@testing-library/react"
import { useClampPage } from "./use-clamp-page"

const run = (
  pageIndex: number,
  page: { total?: number; rowCount?: number; isPlaceholderData?: boolean },
) => {
  const setPage = vi.fn()
  const { result } = renderHook(() =>
    useClampPage(
      { pageIndex, setPage },
      {
        pageSize: 20,
        total: page.total,
        rowCount: page.rowCount,
        isPlaceholderData: page.isPlaceholderData ?? false,
      },
    ),
  )
  return { loading: result.current, setPage }
}

describe("useClampPage", () => {
  it("moves a settled page past the end to the last page, replacing history", () => {
    const { loading, setPage } = run(4, { total: 45, rowCount: 0 })
    expect(loading).toBe(true)
    expect(setPage).toHaveBeenCalledWith(2, { history: "replace" })
  })

  it("waits while the empty page is placeholder data", () => {
    const { loading, setPage } = run(4, {
      total: 45,
      rowCount: 0,
      isPlaceholderData: true,
    })
    expect(loading).toBe(true)
    expect(setPage).not.toHaveBeenCalled()
  })

  it("leaves a page with rows, and a truly empty list, alone", () => {
    expect(run(1, { total: 45, rowCount: 20 })).toMatchObject({
      loading: false,
    })
    const empty = run(0, { total: 0, rowCount: 0 })
    expect(empty.loading).toBe(false)
    expect(empty.setPage).not.toHaveBeenCalled()
  })

  it("does nothing before the first page arrives", () => {
    const { loading, setPage } = run(3, {})
    expect(loading).toBe(false)
    expect(setPage).not.toHaveBeenCalled()
  })
})
