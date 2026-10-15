import { describe, it, expect } from "vitest"
import { renderHook, act } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"
import { getListTransactionsQueryKey } from "@app/api-client/endpoints/transactions"
import { getGetDashboardQueryKey } from "@app/api-client/endpoints/analytics"
import { useInvalidateTransactions } from "./use-invalidate-transactions"

const setup = () => {
  const client = new QueryClient({
    defaultOptions: { queries: { staleTime: Infinity } },
  })
  const list = getListTransactionsQueryKey({ limit: 10 })
  const dashboard = getGetDashboardQueryKey()
  const spending = ["/api/v1/analytics/spending", { date_from: "2026-01-01" }]
  const unrelated = ["/api/v1/conversation"]
  for (const key of [list, dashboard, spending, unrelated]) {
    client.setQueryData(key, {})
  }
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  const { result } = renderHook(() => useInvalidateTransactions(), {
    wrapper,
  })
  const stale = (key: readonly unknown[]) =>
    client.getQueryState(key)?.isInvalidated
  return {
    invalidate: result.current,
    stale,
    list,
    dashboard,
    spending,
    unrelated,
  }
}

describe("useInvalidateTransactions", () => {
  it("marks the list and every analytics query stale, and nothing else", async () => {
    const { invalidate, stale, list, dashboard, spending, unrelated } = setup()
    await act(() => invalidate())
    expect(stale(list)).toBe(true)
    expect(stale(dashboard)).toBe(true)
    expect(stale(spending)).toBe(true)
    expect(stale(unrelated)).toBe(false)
  })
})
