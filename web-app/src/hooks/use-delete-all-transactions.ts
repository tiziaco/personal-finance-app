"use client"

import { useAuth } from "@clerk/nextjs"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { fetchTransactions, batchDeleteTransactions } from "@/lib/api/transactions"

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
      queryClient.invalidateQueries({ queryKey: ["transactions"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard"] })
      queryClient.invalidateQueries({ queryKey: ["analytics"] })
      queryClient.invalidateQueries({ queryKey: ["insights"] })
      toast.success(
        count > 0
          ? `${count} transaction${count === 1 ? "" : "s"} deleted`
          : "No transactions to delete"
      )
    },
    onError: () => {
      toast.error("Failed to delete transactions. Please try again.")
    },
  })
}
