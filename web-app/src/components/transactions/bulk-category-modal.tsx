'use client'

import { useState } from 'react'
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
import type { CategoryEnum, TransactionResponse } from '@/types/transaction'
import { CATEGORY_OPTIONS } from '@/types/transaction'

export interface BulkCategoryModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  transactions: TransactionResponse[]
  onSave: (category: CategoryEnum) => void
  isPending: boolean
}

export function BulkCategoryModal({
  open,
  onOpenChange,
  transactions,
  onSave,
  isPending,
}: BulkCategoryModalProps) {
  const [selectedCategory, setSelectedCategory] = useState<CategoryEnum | ''>('')

  const handleSave = () => {
    if (selectedCategory === '') return
    onSave(selectedCategory)
  }

  // Reset selection when modal closes
  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) setSelectedCategory('')
    onOpenChange(nextOpen)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Recategorize {transactions.length} transaction{transactions.length !== 1 ? 's' : ''}</DialogTitle>
        </DialogHeader>

        <Select
          value={selectedCategory}
          onValueChange={(value) => {
            if (value) setSelectedCategory(value as CategoryEnum)
          }}
        >
          <SelectTrigger className="w-full">
            <SelectValue placeholder="Select a category" />
          </SelectTrigger>
          <SelectContent>
            {CATEGORY_OPTIONS.map((cat) => (
              <SelectItem key={cat} value={cat}>
                {cat}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <DialogFooter showCloseButton>
          <Button onClick={handleSave} disabled={isPending || selectedCategory === ''}>
            {isPending ? 'Saving…' : 'Save'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
