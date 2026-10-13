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
import { useInvalidateTransactions } from "@/components/transactions/use-invalidate-transactions"

export function DataSettings() {
  const [open, setOpen] = useState(false)
  const total = useListTransactions({ limit: 1 }).data?.total ?? 0
  const deleteAll = useDeleteAllTransactions()
  const invalidate = useInvalidateTransactions()
  const description = `Permanently deletes all ${total} transactions. This cannot be undone.`

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
            disabled={total === 0}
            onClick={() => setOpen(true)}
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
              disabled={deleteAll.isPending}
              onClick={() =>
                deleteAll.mutate(undefined, {
                  onSuccess: async () => {
                    await invalidate()
                    setOpen(false)
                  },
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
