'use client'

import { CSVUploadDialog } from './csv-upload-dialog'
import { useUploadStore } from '@/lib/stores/upload-store'
import { useConfirmCSVUpload } from '@/hooks/use-csv-upload'

export function UploadManager() {
  const open = useUploadStore((s) => s.open)
  const setOpen = useUploadStore((s) => s.setOpen)
  const setIsImporting = useUploadStore((s) => s.setIsImporting)
  const confirmMutation = useConfirmCSVUpload()

  function handleConfirm(mappingId: string, confirmedMapping: Record<string, string>) {
    setOpen(false)
    setIsImporting(true)
    confirmMutation.mutate(
      { mappingId, confirmedMapping },
      { onSettled: () => setIsImporting(false) }
    )
  }

  return <CSVUploadDialog open={open} onOpenChange={setOpen} onConfirm={handleConfirm} />
}
