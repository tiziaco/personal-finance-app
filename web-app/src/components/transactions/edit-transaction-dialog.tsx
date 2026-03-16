'use client'

import { useState, useEffect } from 'react'
import { format, parse } from 'date-fns'
import { CalendarIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Calendar } from '@/components/ui/calendar'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { useUpdateTransaction } from '@/hooks/use-transaction-mutations'
import { CATEGORY_OPTIONS } from '@/types/transaction'
import type { CategoryEnum, TransactionResponse, TransactionUpdateRequest } from '@/types/transaction'

interface EditTransactionDialogProps {
  transaction: TransactionResponse | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

interface FormState {
  date: string
  merchant: string
  amount: string
  category: CategoryEnum | ''
  description: string
  is_recurring: boolean
}

const EMPTY_FORM: FormState = {
  date: '',
  merchant: '',
  amount: '',
  category: '',
  description: '',
  is_recurring: false,
}

function transactionToForm(t: TransactionResponse): FormState {
  return {
    // Backend returns ISO 8601 datetime — extract the date part only
    date: t.date.split('T')[0],
    merchant: t.merchant,
    amount: t.amount,
    category: t.category,
    description: t.description ?? '',
    is_recurring: t.is_recurring,
  }
}

export function EditTransactionDialog({ transaction, open, onOpenChange }: EditTransactionDialogProps) {
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [calendarOpen, setCalendarOpen] = useState(false)
  const { mutate, isPending } = useUpdateTransaction()

  // Reset form whenever a different transaction is opened
  useEffect(() => {
    if (transaction) {
      setForm(transactionToForm(transaction))
    } else {
      setForm(EMPTY_FORM)
    }
  }, [transaction?.id])

  function handleOpenChange(next: boolean) {
    if (!next) setForm(EMPTY_FORM)
    onOpenChange(next)
  }

  // Build PATCH payload — only include fields that have changed
  function buildPayload(): TransactionUpdateRequest {
    if (!transaction) return {}

    const payload: TransactionUpdateRequest = {}
    const originalDate = transaction.date.split('T')[0]

    if (form.date && form.date !== originalDate) payload.date = form.date
    if (form.merchant.trim() !== transaction.merchant) payload.merchant = form.merchant.trim()
    // Compare numerically to avoid false positives from string representation differences ("-42.5" vs "-42.50")
    if (isFinite(parseFloat(form.amount)) && parseFloat(form.amount) !== parseFloat(transaction.amount)) {
      payload.amount = form.amount
    }
    if (form.category && form.category !== transaction.category) payload.category = form.category
    // Backend uses exclude_none=True so null cannot clear description — omit empty strings
    const trimmedDesc = form.description.trim()
    if (trimmedDesc !== (transaction.description ?? '')) {
      if (trimmedDesc) payload.description = trimmedDesc
    }
    if (form.is_recurring !== transaction.is_recurring) payload.is_recurring = form.is_recurring

    return payload
  }

  const changedFields = buildPayload()
  const hasChanges = Object.keys(changedFields).length > 0
  const isValid = !!(form.date && form.merchant.trim() && form.category) && isFinite(parseFloat(form.amount))

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!transaction || !hasChanges || !isValid) return

    mutate(
      { id: transaction.id, ...changedFields },
      { onSuccess: () => handleOpenChange(false) }
    )
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Edit Transaction</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4 mt-2">
          {/* Date */}
          <div className="flex flex-col gap-1.5">
            <Label>Date</Label>
            <Popover open={calendarOpen} onOpenChange={setCalendarOpen}>
              <PopoverTrigger
                render={
                  <Button
                    variant="outline"
                    className="w-full justify-start text-left font-normal"
                  >
                    <CalendarIcon className="mr-2 h-4 w-4 opacity-50" />
                    {form.date
                      ? format(parse(form.date, 'yyyy-MM-dd', new Date()), 'PPP')
                      : <span className="text-muted-foreground">Pick a date</span>}
                  </Button>
                }
              />
              <PopoverContent className="w-auto p-0" align="start">
                <Calendar
                  mode="single"
                  selected={form.date ? parse(form.date, 'yyyy-MM-dd', new Date()) : undefined}
                  onSelect={(date) => {
                    if (date) setForm((f) => ({ ...f, date: format(date, 'yyyy-MM-dd') }))
                    setCalendarOpen(false)
                  }}
                />
              </PopoverContent>
            </Popover>
          </div>

          {/* Merchant */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="et-merchant">Merchant</Label>
            <Input
              id="et-merchant"
              type="text"
              placeholder="e.g. Spotify"
              value={form.merchant}
              onChange={(e) => setForm((f) => ({ ...f, merchant: e.target.value }))}
              required
            />
          </div>

          {/* Amount */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="et-amount">Amount</Label>
            <Input
              id="et-amount"
              type="number"
              step="0.01"
              placeholder="e.g. -9.99 (negative = expense)"
              value={form.amount}
              onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
              required
            />
          </div>

          {/* Category */}
          <div className="flex flex-col gap-1.5">
            <Label>Category</Label>
            <Select
              value={form.category}
              onValueChange={(v) => setForm((f) => ({ ...f, category: v as CategoryEnum }))}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select category" />
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

          {/* Description */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="et-description">
              Description <span className="text-muted-foreground text-xs">(optional)</span>
            </Label>
            <Input
              id="et-description"
              type="text"
              placeholder="e.g. Monthly subscription"
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            />
          </div>

          {/* Is recurring */}
          <div className="flex items-center gap-2">
            <Checkbox
              id="et-recurring"
              checked={form.is_recurring}
              onCheckedChange={(checked) =>
                setForm((f) => ({ ...f, is_recurring: checked === true }))
              }
            />
            <Label htmlFor="et-recurring" className="cursor-pointer">
              Recurring transaction
            </Label>
          </div>

          <DialogFooter showCloseButton>
            <Button type="submit" disabled={isPending || !isValid || !hasChanges}>
              {isPending ? 'Saving…' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
