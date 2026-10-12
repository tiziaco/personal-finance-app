// apps/web/src/components/orders/use-orders-table-state.test.tsx
import { describe, it, expect } from "vitest"
import { act, renderHook } from "@testing-library/react"
import { withNuqsTestingAdapter } from "@app/data-table/url-state/testing"
import { useOrdersTableState } from "./use-orders-table-state"

describe("useOrdersTableState", () => {
  it("reads filters, page and sort from the URL", () => {
    const { result } = renderHook(() => useOrdersTableState(), {
      wrapper: withNuqsTestingAdapter({
        searchParams:
          "?status=shipped&created_mode=gte&created_from=2026-01-01&page=2&ordering=-total",
      }),
    })
    expect(result.current.filters).toEqual({
      status: "shipped",
      customer: null,
      created: { mode: "gte", date1: "2026-01-01", date2: "" },
    })
    expect(result.current.pageIndex).toBe(1)
    expect(result.current.sorting).toEqual([{ id: "total", desc: true }])
  })

  it("removing a filter pushes history and resets page", async () => {
    let url: URLSearchParams | undefined
    let history: string | undefined
    const { result } = renderHook(() => useOrdersTableState(), {
      wrapper: withNuqsTestingAdapter({
        searchParams: "?status=shipped&page=3",
        onUrlUpdate: (u) => {
          url = u.searchParams
          history = u.options.history
        },
      }),
    })
    await act(async () => {
      // setFilters returns nuqs's flush promise; its declared type is void.
      await (result.current.setFilters((f) => ({ ...f, status: null })) as unknown as Promise<unknown>)
    })
    expect(url?.get("status")).toBeNull()
    expect(url?.get("page")).toBeNull()
    expect(history).toBe("push")
  })
})
