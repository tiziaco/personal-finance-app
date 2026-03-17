'use client'

import { useAuth } from '@clerk/nextjs'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { updateTransaction, batchUpdateTransactions, createTransaction, batchDeleteTransactions } from '@/lib/api/transactions'
import type { CategoryEnum, CreateTransactionRequest, TransactionListResponse, TransactionResponse, TransactionUpdateRequest } from '@/types/transaction'

export function useUpdateTransactionCategory() {
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

export function useUpdateTransaction() {
  const { getToken } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (payload: { id: number } & TransactionUpdateRequest) => {
      const { id, ...data } = payload
      const token = await getToken()
      return updateTransaction(token, id, data)
    },

    onMutate: async (payload) => {
      // Cancel in-flight queries to avoid overwriting optimistic update
      await queryClient.cancelQueries({ queryKey: ['transactions'] })

      // Snapshot all cached transaction pages for rollback
      const previousData = queryClient.getQueriesData<TransactionListResponse>({
        queryKey: ['transactions'],
      })

      const { id, ...changes } = payload

      // Merge changed fields onto the matching transaction in every cached page
      queryClient.setQueriesData<TransactionListResponse>(
        { queryKey: ['transactions'] },
        (old) => {
          if (!old) return old
          return {
            ...old,
            items: old.items.map((item) =>
              item.id === id ? { ...item, ...changes } : item
            ),
          }
        }
      )

      return { previousData }
    },

    onError: (_err, _variables, context) => {
      // Roll back all snapshots
      context?.previousData.forEach(([queryKey, data]) => {
        queryClient.setQueryData(queryKey, data)
      })
      toast.error('Failed to update transaction')
    },

    onSuccess: () => {
      toast.success('Transaction updated')
    },

    onSettled: () => {
      // Sync real server state regardless of outcome
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
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
  const { getToken, userId } = useAuth()
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
        user_id: userId ?? '',
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

export function useDeleteTransaction() {
  const { getToken } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (id: number) => {
      const token = await getToken()
      return batchDeleteTransactions(token, { ids: [id] })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      toast.success('Transaction deleted')
    },
    onError: () => {
      toast.error('Failed to delete transaction')
    },
  })
}

export function useBulkDeleteTransactions() {
  const { getToken } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (ids: number[]) => {
      const token = await getToken()
      const chunkSize = 100
      const chunks: number[][] = []
      for (let i = 0; i < ids.length; i += chunkSize) {
        chunks.push(ids.slice(i, i + chunkSize))
      }
      const results = await Promise.all(
        chunks.map((chunk) => batchDeleteTransactions(token, { ids: chunk }))
      )
      return results.reduce((sum, r) => sum + r.deleted, 0)
    },
    onSuccess: (deleted) => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      toast.success(`${deleted} ${deleted === 1 ? 'transaction' : 'transactions'} deleted`)
    },
    onError: () => {
      toast.error('Failed to delete transactions')
    },
  })
}
