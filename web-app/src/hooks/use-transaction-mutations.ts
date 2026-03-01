'use client'

import { useAuth } from '@clerk/nextjs'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { updateTransaction, batchUpdateTransactions } from '@/lib/api/transactions'
import type { CategoryEnum } from '@/types/transaction'

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
