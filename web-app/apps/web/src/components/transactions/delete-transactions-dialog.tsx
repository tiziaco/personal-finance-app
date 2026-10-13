"use client"

import {
  useBatchDeleteTransactions,
  useDeleteTransaction,
} from "@app/api-client/endpoints/transactions"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@app/ui/alert-dialog"
import { useRefreshTransactionsOnSuccess } from "./use-invalidate-transactions"

/** Confirms, then deletes one transaction or a batch (all or nothing). */
export function DeleteTransactionsDialog({
  ids,
  open,
  onOpenChange,
  onDeleted,
}: {
  ids: string[]
  open: boolean
  onOpenChange: (open: boolean) => void
  onDeleted?: () => void
}) {
  // The refresh rides on the hooks, so it runs even if the dialog is gone by then.
  const refresh = useRefreshTransactionsOnSuccess()
  const one = useDeleteTransaction(refresh)
  const many = useBatchDeleteTransactions(refresh)
  const done = () => {
    onDeleted?.()
    onOpenChange(false)
  }
  const title =
    ids.length === 1
      ? "Delete this transaction?"
      : `Delete ${ids.length} transactions?`
  const confirm = () =>
    ids.length === 1
      ? one.mutate({ transactionId: ids[0] }, { onSuccess: done })
      : many.mutate({ data: { ids } }, { onSuccess: done })
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>
            It disappears from your lists and analytics.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            // Stays disabled after success, through the closing animation.
            disabled={
              one.isPending || many.isPending || one.isSuccess || many.isSuccess
            }
            onClick={confirm}
          >
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
