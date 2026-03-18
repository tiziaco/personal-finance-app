'use client'

import { useState } from 'react'
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
import { useCreateTransaction } from '@/hooks/use-transaction-mutations'
import { CATEGORY_OPTIONS } from '@/types/transaction'
import type { CategoryEnum } from '@/types/transaction'

interface AddTransactionDialogProps {
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

export function AddTransactionDialog({ open, onOpenChange }: AddTransactionDialogProps) {
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [calendarOpen, setCalendarOpen] = useState(false)
  const { mutate, isPending } = useCreateTransaction()

  function handleOpenChange(next: boolean) {
    if (!next) setForm(EMPTY_FORM)
    onOpenChange(next)
  }

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const trimmedMerchant = form.merchant.trim()
    if (!form.date || !trimmedMerchant || !form.amount || !form.category) return

    const parsedAmount = parseFloat(form.amount)
    if (!isFinite(parsedAmount)) return

    mutate({
      date: form.date,
      merchant: trimmedMerchant,
      amount: form.amount,
      category: form.category,
      description: form.description.trim() || undefined,
      is_recurring: form.is_recurring,
    })
    handleOpenChange(false)
  }

  const isValid =
    !!(form.date && form.merchant.trim() && form.category) &&
    isFinite(parseFloat(form.amount))

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Add Transaction</DialogTitle>
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
            <Label htmlFor="at-merchant">Merchant</Label>
            <Input
              id="at-merchant"
              type="text"
              placeholder="e.g. Spotify"
              value={form.merchant}
              onChange={(e) => setForm((f) => ({ ...f, merchant: e.target.value }))}
              required
            />
          </div>

          {/* Amount */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="at-amount">Amount</Label>
            <Input
              id="at-amount"
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
            <Label htmlFor="at-description">
              Description <span className="text-muted-foreground text-xs">(optional)</span>
            </Label>
            <Input
              id="at-description"
              type="text"
              placeholder="e.g. Monthly subscription"
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            />
          </div>

          {/* Is recurring */}
          <div className="flex items-center gap-2">
            <Checkbox
              id="at-recurring"
              checked={form.is_recurring}
              onCheckedChange={(checked) =>
                setForm((f) => ({ ...f, is_recurring: checked === true }))
              }
            />
            <Label htmlFor="at-recurring" className="cursor-pointer">
              Recurring transaction
            </Label>
          </div>

          <DialogFooter showCloseButton>
            <Button type="submit" disabled={isPending || !isValid}>
              {isPending ? 'Adding…' : 'Add Transaction'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
