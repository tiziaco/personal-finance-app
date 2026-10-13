"use client"

import { useState } from "react"
import {
  useDeleteAllTransactions,
  useListTransactions,
} from "@app/api-client/endpoints/transactions"
import { SettingSection } from "@app/ui/setting-section"
import { Button } from "@app/ui/button"
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
import { useRefreshTransactionsOnSuccess } from "@/components/transactions/use-invalidate-transactions"

export function DataSettings() {
  const [open, setOpen] = useState(false)
  // Active rows only: deleted ones are removed too, so the button is never disabled at 0.
  const total = useListTransactions({ limit: 1 }).data?.total
  // The refresh rides on the hook, so it runs even if Settings closed by then.
  const deleteAll = useDeleteAllTransactions(useRefreshTransactionsOnSuccess())
  const description = total
    ? `Permanently deletes all ${total} transactions. This cannot be undone.`
    : "Permanently deletes all your transactions, including deleted ones. This cannot be undone."

  return (
    <div className="space-y-6">
      <SettingSection title="Transactions">
        <div className="flex items-center justify-between gap-4">
          <p className="text-sm text-muted-foreground">
            Remove every transaction you have.
          </p>
          <Button
            variant="destructive"
            size="sm"
            onClick={() => {
              deleteAll.reset()
              setOpen(true)
            }}
          >
            Delete all transactions
          </Button>
        </div>
      </SettingSection>
      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete all transactions?</AlertDialogTitle>
            <AlertDialogDescription>{description}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              // Stays disabled after success, through the closing animation.
              disabled={deleteAll.isPending || deleteAll.isSuccess}
              onClick={() =>
                deleteAll.mutate(undefined, {
                  onSuccess: () => setOpen(false),
                })
              }
            >
              Delete all
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
