"use client"

import { useBatchDeleteTransactions } from "@app/api-client/endpoints/transactions"
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

/** Confirms, then deletes one transaction or several (all or nothing): the batch route takes one id too. */
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
  // The refresh rides on the hook, so it runs even if the dialog is gone by then.
  const { mutate, isPending, isSuccess } = useBatchDeleteTransactions(
    useRefreshTransactionsOnSuccess(),
  )
  // Not closable mid-delete: closing would unmount the dialog and skip
  // onDeleted, leaving an edit form open on a deleted transaction.
  const setOpen = (next: boolean) => (next || !isPending) && onOpenChange(next)
  const title =
    ids.length === 1
      ? "Delete this transaction?"
      : `Delete ${ids.length} transactions?`
  const confirm = () =>
    mutate(
      { data: { ids } },
      {
        onSuccess: () => {
          onDeleted?.()
          onOpenChange(false)
        },
      },
    )
  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>
            It disappears from your lists and analytics.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isPending}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            // Stays disabled after success, through the closing animation.
            disabled={isPending || isSuccess}
            onClick={confirm}
          >
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
