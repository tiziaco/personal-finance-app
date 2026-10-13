import { describe, it, expect } from "vitest"
import { act, renderHook } from "@testing-library/react"
import { withNuqsTestingAdapter } from "@app/data-table/url-state/testing"
import { EMPTY_TRANSACTIONS_FILTERS } from "./transactions-table-params"
import { useTransactionsTableState } from "./use-transactions-table-state"

describe("useTransactionsTableState", () => {
  it("reads filters, page and sort from the URL", () => {
    const { result } = renderHook(() => useTransactionsTableState(), {
      wrapper: withNuqsTestingAdapter({
        searchParams: "?category=atm&page=2&ordering=-amount",
      }),
    })
    expect(result.current.filters.categories).toEqual(["atm"])
    expect(result.current.pageIndex).toBe(1)
    expect(result.current.sorting).toEqual([{ id: "amount", desc: true }])
  })

  it("setting categories writes category and resets page", async () => {
    let url: URLSearchParams | undefined
    const { result } = renderHook(() => useTransactionsTableState(), {
      wrapper: withNuqsTestingAdapter({
        searchParams: "?page=3",
        onUrlUpdate: (u) => (url = u.searchParams),
      }),
    })
    await act(async () => {
      await (result.current.setFilters({
        ...EMPTY_TRANSACTIONS_FILTERS,
        categories: ["salary"],
      }) as unknown as Promise<unknown>)
    })
    expect(url?.get("category")).toBe("salary")
    expect(url?.get("page")).toBeNull()
  })

  it("search writes search", async () => {
    let url: URLSearchParams | undefined
    const { result } = renderHook(() => useTransactionsTableState(), {
      wrapper: withNuqsTestingAdapter({
        onUrlUpdate: (u) => (url = u.searchParams),
      }),
    })
    await act(async () => {
      await (result.current.setSearch("rewe") as unknown as Promise<unknown>)
    })
    expect(url?.get("search")).toBe("rewe")
  })
})
