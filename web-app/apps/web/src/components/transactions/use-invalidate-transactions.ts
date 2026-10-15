"use client"

import { useCallback, useMemo } from "react"
import { useQueryClient, type Query } from "@tanstack/react-query"
import { getListTransactionsQueryKey } from "@app/api-client/endpoints/transactions"

/**
 * Generated query keys are `[url, params?]`, so no key is a prefix of every
 * analytics query's; a predicate on the url catches them all.
 */
const ANALYTICS_KEY_PREFIX = "/api/v1/analytics/"

const isAnalyticsQuery = (query: Query) => {
  const [url] = query.queryKey
  return typeof url === "string" && url.startsWith(ANALYTICS_KEY_PREFIX)
}

/**
 * Refetch every page of the list, and every analytics figure, after a write.
 * The list key without params is a prefix of each page's key.
 */
export function useInvalidateTransactions() {
  const queryClient = useQueryClient()
  return useCallback(
    () =>
      Promise.all([
        queryClient.invalidateQueries({
          queryKey: getListTransactionsQueryKey(),
        }),
        queryClient.invalidateQueries({ predicate: isAnalyticsQuery }),
      ]),
    [queryClient],
  )
}

/**
 * Hook-level mutation options that refetch the list and every analytics
 * figure on success. Hook-level
 * callbacks run even after the component unmounts — a per-call
 * `mutate(…, { onSuccess })` is skipped then — and the mutation stays
 * pending while the refetch runs.
 */
export function useRefreshTransactionsOnSuccess() {
  const invalidate = useInvalidateTransactions()
  return useMemo(
    () => ({ mutation: { onSuccess: () => invalidate() } }),
    [invalidate],
  )
}
