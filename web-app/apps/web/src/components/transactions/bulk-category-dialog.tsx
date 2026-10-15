"use client"

import { useState } from "react"
import { useBatchUpdateTransactionCategory } from "@app/api-client/endpoints/transactions"
import type { Category } from "@app/api-client/types"
import { Button } from "@app/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@app/ui/dialog"
import { Label } from "@app/ui/label"
import { CategorySelect } from "./category-select"
import { useCategories } from "./use-categories"
import { useRefreshTransactionsOnSuccess } from "./use-invalidate-transactions"

/** Moves several transactions to one category (all or nothing). */
export function BulkCategoryDialog({
  ids,
  open,
  onOpenChange,
  onDone,
}: {
  ids: string[]
  open: boolean
  onOpenChange: (open: boolean) => void
  onDone: () => void
}) {
  const { categories } = useCategories()
  const [category, setCategory] = useState<Category | "">("")
  const { mutate, isPending, isSuccess } = useBatchUpdateTransactionCategory(
    useRefreshTransactionsOnSuccess(),
  )
  const apply = () => {
    if (!category) return
    mutate(
      { data: { ids, category } },
      {
        onSuccess: () => {
          onDone()
          onOpenChange(false)
        },
      },
    )
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{`Recategorise ${ids.length} transactions`}</DialogTitle>
          <DialogDescription>
            They all move to the category you pick.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-2">
          <Label htmlFor="bulk-category">Category</Label>
          <CategorySelect
            id="bulk-category"
            value={category}
            onChange={setCategory}
            categories={categories}
          />
        </div>
        <DialogFooter>
          <DialogClose render={<Button variant="outline" />}>
            Cancel
          </DialogClose>
          <Button
            disabled={!category || isPending || isSuccess}
            onClick={apply}
          >
            Apply
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
