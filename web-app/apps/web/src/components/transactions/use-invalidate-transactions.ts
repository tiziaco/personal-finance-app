"use client"

import { useCallback } from "react"
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
