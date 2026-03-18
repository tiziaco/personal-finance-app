'use client'

import { useAuth } from '@clerk/nextjs'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { updateTransaction, batchUpdateTransactions, createTransaction, batchDeleteTransactions, fetchTransactions } from '@/lib/api/transactions'
import type { CategoryEnum, CreateTransactionRequest, TransactionListResponse, TransactionUpdateRequest } from '@/types/transaction'

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
  const { getToken } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (payload: CreateTransactionRequest) => {
      const token = await getToken()
      return createTransaction(token, payload)
    },

    onSuccess: () => {
      toast.success('Transaction added')
    },

    onError: () => {
      toast.error('Failed to add transaction')
    },

    onSettled: () => {
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
      const results = await Promise.allSettled(
        chunks.map((chunk) => batchDeleteTransactions(token, { ids: chunk }))
      )
      let deleted = 0
      let hasFailure = false
      for (const result of results) {
        if (result.status === 'fulfilled') {
          deleted += result.value.deleted
        } else {
          hasFailure = true
        }
      }
      if (hasFailure) throw new Error('Some transaction deletions failed.')
      return deleted
    },
    onSuccess: (deleted) => {
      toast.success(`${deleted} ${deleted === 1 ? 'transaction' : 'transactions'} deleted`)
    },
    onError: () => {
      toast.error('Failed to delete transactions')
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
    },
  })
}

export function useDeleteAllTransactions() {
  const { getToken } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async () => {
      const token = await getToken()

      // Step 1: Paginate to collect all transaction IDs
      const allIds: number[] = []
      const pageSize = 100
      let offset = 0

      while (true) {
        const page = await fetchTransactions(token, { limit: pageSize, offset })
        allIds.push(...page.items.map((t) => t.id))
        if (page.items.length < pageSize) break
        offset += pageSize
      }

      if (allIds.length === 0) return 0

      // Step 2: Delete in batches of 100
      let deleted = 0
      for (let i = 0; i < allIds.length; i += pageSize) {
        const chunk = allIds.slice(i, i + pageSize)
        const result = await batchDeleteTransactions(token, { ids: chunk })
        deleted += result.deleted
      }

      return deleted
    },
    onSuccess: (count) => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      queryClient.invalidateQueries({ queryKey: ['analytics'] })
      queryClient.invalidateQueries({ queryKey: ['insights'] })
      toast.success(
        count > 0
          ? `${count} transaction${count === 1 ? '' : 's'} deleted`
          : 'No transactions to delete'
      )
    },
    onError: () => {
      toast.error('Failed to delete transactions. Please try again.')
    },
  })
}
