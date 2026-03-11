'use client'

import { useAuth } from '@clerk/nextjs'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { updateTransaction, batchUpdateTransactions, createTransaction } from '@/lib/api/transactions'
import type { CategoryEnum, CreateTransactionRequest, TransactionListResponse, TransactionResponse } from '@/types/transaction'

export function useUpdateTransaction() {
  const { getToken } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (payload: { id: number; category: CategoryEnum }) => {
      const token = await getToken()
      return updateTransaction(token, payload.id, { category: payload.category })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      toast.success('Category updated')
    },
    onError: () => {
      toast.error('Failed to update category')
    },
  })
}

export function useBatchUpdateTransactions() {
  const { getToken } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (items: Array<{ id: number; category: CategoryEnum }>) => {
      const token = await getToken()
      return batchUpdateTransactions(token, { items })
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      toast.success(`${data.updated} transactions updated`)
    },
    onError: () => {
      toast.error('Bulk update failed')
    },
  })
}

export function useCreateTransaction() {
  const { getToken } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (payload: CreateTransactionRequest) => {
      const token = await getToken()
      return createTransaction(token, payload)
    },

    onMutate: async (payload) => {
      // Cancel in-flight queries to avoid overwriting optimistic update
      await queryClient.cancelQueries({ queryKey: ['transactions'] })

      // Snapshot all cached transaction pages for rollback
      const previousData = queryClient.getQueriesData<TransactionListResponse>({
        queryKey: ['transactions'],
      })

      // Build optimistic transaction with a temporary negative ID
      const optimistic: TransactionResponse = {
        id: -Date.now(),
        user_id: '',
        date: payload.date,
        merchant: payload.merchant,
        amount: payload.amount,
        description: payload.description ?? null,
        original_category: null,
        category: payload.category,
        confidence_score: 1,
        is_recurring: payload.is_recurring ?? false,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }

      // Prepend to every cached transaction list
      queryClient.setQueriesData<TransactionListResponse>(
        { queryKey: ['transactions'] },
        (old) => {
          if (!old) return old
          return { ...old, items: [optimistic, ...old.items], total: old.total + 1 }
        }
      )

      return { previousData }
    },

    onError: (_err, _variables, context) => {
      // Roll back all snapshots
      context?.previousData.forEach(([queryKey, data]) => {
        queryClient.setQueryData(queryKey, data)
      })
      toast.error('Failed to add transaction')
    },

    onSuccess: () => {
      toast.success('Transaction added')
    },

    onSettled: () => {
      // Sync real server state regardless of outcome
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
    },
  })
}
