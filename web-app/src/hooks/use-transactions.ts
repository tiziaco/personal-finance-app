'use client'

import { useAuth } from '@clerk/nextjs'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { fetchTransactions } from '@/lib/api/transactions'
import type { TransactionFilters, TransactionListResponse } from '@/types/transaction'

export function useTransactions(filters: TransactionFilters = {}, page: number = 0) {
  const { getToken } = useAuth()
  const limit = 25
  const offset = page * limit

  return useQuery<TransactionListResponse>({
    queryKey: ['transactions', filters, page],
    queryFn: async () => {
      const token = await getToken()
      return fetchTransactions(token, { ...filters, offset, limit })
    },
    placeholderData: keepPreviousData,   // keeps old page visible while fetching next — v5 syntax
    staleTime: 30 * 1000,               // 30 seconds — transactions change on upload
  })
}
