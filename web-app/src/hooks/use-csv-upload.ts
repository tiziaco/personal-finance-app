'use client'

import { useAuth } from '@clerk/nextjs'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { uploadCSV, confirmCSVUpload } from '@/lib/api/transactions'
import type { CSVUploadProposalResponse } from '@/types/csv-upload'

export function useUploadCSV() {
  const { getToken } = useAuth()

  return useMutation({
    mutationFn: async (file: File): Promise<CSVUploadProposalResponse> => {
      const token = await getToken()
      return uploadCSV(token, file)
    },
    onError: () => {
      toast.error('Failed to process CSV — check the file format')
    },
  })
}

export function useConfirmCSVUpload() {
  const { getToken } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (payload: {
      mappingId: string
      confirmedMapping: Record<string, string>
    }) => {
      const token = await getToken()
      return confirmCSVUpload(token, payload.mappingId, payload.confirmedMapping)
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      toast.success(
        `Imported ${data.imported} transactions${data.skipped > 0 ? `, skipped ${data.skipped}` : ''}`
      )
    },
    onError: () => {
      toast.error('Import failed — please try again')
    },
  })
}
