"use client"

import { useCallback, useMemo } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { getListTransactionsQueryKey } from "@app/api-client/endpoints/transactions"

/** Refetch every page of the list after a write. The key without params is a prefix of each page's key. */
export function useInvalidateTransactions() {
  const queryClient = useQueryClient()
  return useCallback(
    () =>
      queryClient.invalidateQueries({
        queryKey: getListTransactionsQueryKey(),
      }),
    [queryClient],
  )
}

/**
 * Hook-level mutation options that refetch the list on success. Hook-level
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
