"use client"

import { SettingSection } from "@/components/ui/setting-section"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { useDeleteAllTransactions } from "@/hooks/use-transaction-mutations"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"

export function DataSection() {
  const deleteAll = useDeleteAllTransactions()

  return (
    <div className="space-y-6">

      <SettingSection title="Transactions">
        <div className="flex items-center justify-between gap-4">
          <p className="text-sm text-muted-foreground">
            Permanently remove all your transaction history
          </p>
          <AlertDialog>
            <AlertDialogTrigger
              render={
                <Button
                  variant="outline"
                  size="sm"
                  className="border-destructive text-destructive hover:text-destructive hover:bg-destructive/10 shrink-0 min-h-12"
                >
                  Delete All Transactions
                </Button>
              }
            />
            <AlertDialogContent size="sm">
              <AlertDialogHeader>
                <AlertDialogTitle>Delete all transactions?</AlertDialogTitle>
                <AlertDialogDescription>
                  This will permanently remove all your transaction history. This
                  action cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  variant="destructive"
                  onClick={() => deleteAll.mutate()}
                  disabled={deleteAll.isPending}
                >
                  {deleteAll.isPending ? "Deleting…" : "Delete all"}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </SettingSection>

      <SettingSection title="Data Management">
        <div className="flex items-center justify-between gap-4">
          <p className="text-sm text-muted-foreground">Manage or delete your chats</p>
          <Button variant="outline" size="sm" className="border-destructive text-destructive hover:text-destructive hover:bg-destructive/10 min-h-12">
            Delete All Chats
          </Button>
        </div>
      </SettingSection>

      <SettingSection title="Storage">
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label>Memory Usage</Label>
            <span className="text-sm text-muted-foreground">0 MB</span>
          </div>
          <div className="flex justify-end">
            <Button variant="outline" size="sm">
              Clear Memory
            </Button>
          </div>
        </div>
      </SettingSection>
    </div>
  )
}
