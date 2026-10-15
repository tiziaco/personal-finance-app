import { describe, it, expect, vi } from "vitest"
import { act, renderHook } from "@testing-library/react"
import { parseAsInteger, parseAsString } from "nuqs"
import {
  withNuqsTestingAdapter,
  type OnUrlUpdateFunction,
  type UrlUpdateEvent,
} from "nuqs/adapters/testing"
import {
  createUrlTableStateHook,
  useUrlTableState,
} from "./use-url-table-state"
import { prefixKeys } from "./prefix-keys"

const parsers = {
  page: parseAsInteger.withDefault(1),
  ordering: parseAsString,
  search: parseAsString.withDefault(""),
  type: parseAsString,
}

function setup(
  searchParams: string,
  onUrlUpdate?: OnUrlUpdateFunction,
  urlKeys?: Record<string, string>,
) {
  return renderHook(() => useUrlTableState(parsers, { urlKeys }), {
    wrapper: withNuqsTestingAdapter({ searchParams, onUrlUpdate }),
  })
}

describe("useUrlTableState", () => {
  it("derives pageIndex and sorting from the URL", () => {
    const { result } = setup("?type=warehouse&page=3&ordering=-name")
    expect(result.current.values.type).toBe("warehouse")
    expect(result.current.pageIndex).toBe(2)
    expect(result.current.sorting).toEqual([{ id: "name", desc: true }])
  })

  it("setFilters resets page", async () => {
    let event: UrlUpdateEvent | undefined
    const { result } = setup("?type=warehouse&page=3", (u) => (event = u))
    await act(async () => {
      await result.current.setFilters({ type: "factory" })
    })
    expect(event?.searchParams.get("type")).toBe("factory")
    expect(event?.searchParams.get("page")).toBeNull()
    expect(event?.options.history).toBe("push")
  })

  it("clamps pageIndex at zero for page=0", () => {
    const { result } = setup("?page=0")
    expect(result.current.pageIndex).toBe(0)
  })

  it("debounces typed search and lets a clear win inside the window", async () => {
    vi.useFakeTimers()
    try {
      const events: UrlUpdateEvent[] = []
      const { result } = setup("", (u) => events.push(u))
      act(() => {
        void result.current.setSearch("acme")
      })
      await act(async () => {
        await vi.advanceTimersByTimeAsync(299)
      })
      expect(events).toHaveLength(0)
      await act(async () => {
        // nuqs flushes a few ms after the nominal window.
        await vi.advanceTimersByTimeAsync(51)
      })
      expect(events.at(-1)?.searchParams.get("search")).toBe("acme")

      act(() => {
        void result.current.setSearch("acm")
      })
      await act(async () => {
        await vi.advanceTimersByTimeAsync(100)
        void result.current.setSearch("")
        await vi.advanceTimersByTimeAsync(500)
      })
      expect(events.at(-1)?.searchParams.get("search")).toBeNull()
    } finally {
      vi.useRealTimers()
    }
  })

  it("setPage pushes history and keeps other keys", async () => {
    let event: UrlUpdateEvent | undefined
    const { result } = setup("?type=warehouse&page=3", (u) => (event = u))
    await act(async () => {
      await result.current.setPage(4)
    })
    expect(event?.searchParams.get("page")).toBe("5")
    expect(event?.searchParams.get("type")).toBe("warehouse")
    expect(event?.options.history).toBe("push")
  })

  it("setPage replaces history when asked", async () => {
    let event: UrlUpdateEvent | undefined
    const { result } = setup("?page=3", (u) => (event = u))
    await act(async () => {
      await result.current.setPage(1, { history: "replace" })
    })
    expect(event?.searchParams.get("page")).toBe("2")
    expect(event?.options.history).toBe("replace")
  })

  it("setSort pushes history and resets page", async () => {
    let event: UrlUpdateEvent | undefined
    const { result } = setup("?page=3", (u) => (event = u))
    await act(async () => {
      await result.current.setSort([{ id: "name", desc: true }])
    })
    expect(event?.searchParams.get("ordering")).toBe("-name")
    expect(event?.searchParams.get("page")).toBeNull()
    expect(event?.options.history).toBe("push")
  })

  it("setSearch replaces history after the debounce and resets page", async () => {
    let event: UrlUpdateEvent | undefined
    const { result } = setup("?page=3", (u) => (event = u))
    await act(async () => {
      await result.current.setSearch("acme")
    })
    expect(event?.searchParams.get("search")).toBe("acme")
    expect(event?.searchParams.get("page")).toBeNull()
    expect(event?.options.history).toBe("replace")
  })

  it("clearing search removes the key", async () => {
    let event: UrlUpdateEvent | undefined
    const { result } = setup("?search=acme", (u) => (event = u))
    await act(async () => {
      await result.current.setSearch("")
    })
    expect(event?.searchParams.get("search")).toBeNull()
  })

  it("reads and writes prefixed keys", async () => {
    let event: UrlUpdateEvent | undefined
    const { result } = setup(
      "?orders_page=3&orders_type=x&page=9",
      (u) => (event = u),
      prefixKeys(parsers, "orders"),
    )
    expect(result.current.pageIndex).toBe(2)
    expect(result.current.values.type).toBe("x")
    await act(async () => {
      await result.current.setFilters({ type: "y" })
    })
    expect(event?.searchParams.get("orders_type")).toBe("y")
    expect(event?.searchParams.get("orders_page")).toBeNull()
    expect(event?.searchParams.get("page")).toBe("9") // another list's key is untouched
  })

  it("keeps setter and sorting identities across a rerender", () => {
    const { result, rerender } = setup("?ordering=-name")
    const first = result.current
    rerender()
    expect(result.current.setFilters).toBe(first.setFilters)
    expect(result.current.setPage).toBe(first.setPage)
    expect(result.current.setSort).toBe(first.setSort)
    expect(result.current.setSearch).toBe(first.setSearch)
    expect(result.current.sorting).toBe(first.sorting)
  })
})

describe("createUrlTableStateHook", () => {
  const twoKeyParsers = {
    page: parseAsInteger.withDefault(1),
    ordering: parseAsString,
    search: parseAsString.withDefault(""),
    a: parseAsString,
    b: parseAsString,
  }
  type TwoKeyFilters = { a: string | null; b: string | null }
  const useTwoKeyTableState = createUrlTableStateHook({
    parsers: twoKeyParsers,
    toFilters: (v): TwoKeyFilters => ({ a: v.a, b: v.b }),
    fromFilters: (f: TwoKeyFilters) => ({ a: f.a, b: f.b }),
  })

  it("returns filters in the mapped shape", () => {
    const { result } = renderHook(() => useTwoKeyTableState(), {
      wrapper: withNuqsTestingAdapter({ searchParams: "?a=1&page=2" }),
    })
    expect(result.current.filters).toEqual({ a: "1", b: null })
    expect(result.current.pageIndex).toBe(1)
  })

  it("reads and writes prefixed keys via urlKeys", async () => {
    let event: UrlUpdateEvent | undefined
    const useOrders = createUrlTableStateHook({
      parsers: twoKeyParsers,
      urlKeys: prefixKeys(twoKeyParsers, "orders"),
      toFilters: (v): TwoKeyFilters => ({ a: v.a, b: v.b }),
      fromFilters: (f: TwoKeyFilters) => ({ a: f.a, b: f.b }),
    })
    const { result } = renderHook(() => useOrders(), {
      wrapper: withNuqsTestingAdapter({
        searchParams: "?orders_a=1&orders_page=2&a=9",
        onUrlUpdate: (u) => (event = u),
      }),
    })
    expect(result.current.filters).toEqual({ a: "1", b: null })
    expect(result.current.pageIndex).toBe(1)
    await act(async () => {
      await (result.current.setFilters({
        a: "1",
        b: "2",
      }) as unknown as Promise<unknown>)
    })
    expect(event?.searchParams.get("orders_b")).toBe("2")
    expect(event?.searchParams.get("orders_page")).toBeNull()
    expect(event?.searchParams.get("a")).toBe("9")
  })

  it("composes same-tick functional updates instead of clobbering", async () => {
    let event: UrlUpdateEvent | undefined
    const { result } = renderHook(() => useTwoKeyTableState(), {
      wrapper: withNuqsTestingAdapter({
        searchParams: "",
        onUrlUpdate: (u) => (event = u),
      }),
    })
    await act(async () => {
      result.current.setFilters((prev) => ({ ...prev, a: "1" }))
      await (result.current.setFilters((prev) => ({
        ...prev,
        b: "2",
      })) as unknown as Promise<unknown>)
    })
    expect(event?.searchParams.get("a")).toBe("1")
    expect(event?.searchParams.get("b")).toBe("2")
    expect(event?.options.history).toBe("push")
  })

  it("keeps setFilters and filters identities across a rerender", () => {
    const { result, rerender } = renderHook(() => useTwoKeyTableState(), {
      wrapper: withNuqsTestingAdapter({ searchParams: "?a=1" }),
    })
    const first = result.current
    rerender()
    expect(result.current.setFilters).toBe(first.setFilters)
    expect(result.current.filters).toBe(first.filters)
  })
})

// hasMemory: the adapter keeps what the hook wrote, as a browser URL would,
// instead of snapping back to `searchParams` on the next render.
function setupWithMemory(searchParams: string) {
  return renderHook(() => useUrlTableState(parsers), {
    wrapper: withNuqsTestingAdapter({ searchParams, hasMemory: true }),
  })
}

describe("useUrlTableState with a generated hook", () => {
  it("writes shallow, so the URL changes without a server round-trip", async () => {
    let event: UrlUpdateEvent | undefined
    const { result } = setup("", (u) => (event = u))
    await act(async () => {
      await result.current.setFilters({ type: "factory" })
    })
    expect(event?.options.shallow).toBe(true)
  })

  it("holds query.search back until typing pauses, then resets the page with it", async () => {
    vi.useFakeTimers()
    try {
      const { result } = setupWithMemory("?page=3")
      act(() => {
        void result.current.setSearch("acme")
      })
      expect(result.current.search).toBe("acme")
      expect(result.current.query).toMatchObject({ search: "", page: 3 })
      expect(result.current.pageIndex).toBe(2)
      await act(async () => {
        await vi.advanceTimersByTimeAsync(350)
      })
      expect(result.current.query).toMatchObject({ search: "acme", page: 1 })
      expect(result.current.pageIndex).toBe(0)
    } finally {
      vi.useRealTimers()
    }
  })

  it("applies filter and page changes to query at once", async () => {
    const { result } = setupWithMemory("?page=3")
    await act(async () => {
      await result.current.setFilters({ type: "factory" })
    })
    expect(result.current.query).toMatchObject({ type: "factory", page: 1 })
  })

  it("keeps query's identity across a rerender", () => {
    const { result, rerender } = setup("?type=warehouse")
    const first = result.current.query
    rerender()
    expect(result.current.query).toBe(first)
  })
})
