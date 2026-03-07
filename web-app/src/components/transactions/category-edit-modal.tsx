'use client'

import { useState, useEffect } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { useUpdateTransaction } from '@/hooks/use-transaction-mutations'
import { useFormatCurrency } from '@/hooks/use-currency-format'
import { useFormatDate } from '@/hooks/use-date-format'
import { type CategoryEnum, type TransactionResponse, CATEGORY_OPTIONS } from '@/types/transaction'

interface CategoryEditModalProps {
  transaction: TransactionResponse | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function CategoryEditModal({ transaction, open, onOpenChange }: CategoryEditModalProps) {
  const formatDate = useFormatDate()
  const formatCurrency = useFormatCurrency()
  const [selectedCategory, setSelectedCategory] = useState<CategoryEnum | undefined>()
  const { mutate, isPending } = useUpdateTransaction()

  // Reset selectedCategory when switching between transactions — avoids showing stale selection
  useEffect(() => {
    setSelectedCategory(undefined)
  }, [transaction?.id])

  const handleSave = () => {
    if (!transaction || !selectedCategory) return
    mutate(
      { id: transaction.id, category: selectedCategory },
      { onSuccess: () => onOpenChange(false) }
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Category</DialogTitle>
        </DialogHeader>

        {transaction && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              {transaction.merchant} &middot; {formatCurrency(transaction.amount)} &middot; {formatDate(transaction.date)}
            </p>

            <Select
              value={selectedCategory ?? transaction.category}
              onValueChange={(value) => {
                if (value) setSelectedCategory(value as CategoryEnum)
              }}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CATEGORY_OPTIONS.map((cat) => (
                  <SelectItem key={cat} value={cat}>
                    {cat}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        <DialogFooter showCloseButton>
          <Button
            onClick={handleSave}
            disabled={isPending || !selectedCategory}
          >
            {isPending ? 'Saving…' : 'Save'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
