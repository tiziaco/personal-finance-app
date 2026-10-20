"use client"

import { useState, type FormEvent } from "react"
import { ApiError } from "@app/api-client"
import {
  useCreateTransaction,
  useUpdateTransaction,
} from "@app/api-client/endpoints/transactions"
import type {
  Category,
  TransactionResponse,
  TransactionUpdate,
} from "@app/api-client/types"
import { todayIsoDay } from "@app/core/lib/dates"
import { DatePicker } from "@app/components/forms/date-picker"
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
import { Input } from "@app/ui/input"
import { Label } from "@app/ui/label"
import { Switch } from "@app/ui/switch"
import { Textarea } from "@app/ui/textarea"
import { parseAmount } from "./amount-input"
import { formatDate, formatSignedAmount } from "./format"
import { CategorySelect } from "./category-select"
import { useCategories } from "./use-categories"
import { DeleteTransactionsDialog } from "./delete-transactions-dialog"
import { useRefreshTransactionsOnSuccess } from "./use-invalidate-transactions"

type Target =
  { mode: "add" } | { mode: "edit"; transaction: TransactionResponse }

type FormState = {
  date: string
  merchant: string
  amount: string
  category: Category | ""
  description: string
  recurring: boolean
}

/** The fields an edit compares and sends, in the API's shape. */
type Values = {
  date: string
  merchant: string
  amount: string
  category: Category
  description: string | null
  is_recurring: boolean
}

const AMOUNT_ERROR = "Enter an amount like -4.50"
const MISSING_ERROR = "Fill in the date, merchant and category."

/** A 409: an active transaction already has this date, merchant, amount and description. */
const isDuplicate = (error: unknown) =>
  error instanceof ApiError && error.status === 409

function initialState(target: Target): FormState {
  if (target.mode === "add") {
    return {
      date: todayIsoDay(),
      merchant: "",
      amount: "",
      category: "",
      description: "",
      recurring: false,
    }
  }
  const t = target.transaction
  return {
    date: t.date,
    merchant: t.merchant,
    amount: t.amount,
    category: t.category,
    description: t.description ?? "",
    recurring: t.is_recurring,
  }
}

/** Only the fields whose value differs from the transaction's. */
function changes(t: TransactionResponse, next: Values): TransactionUpdate {
  const data: TransactionUpdate = {}
  if (next.date !== t.date) data.date = next.date
  if (next.merchant !== t.merchant) data.merchant = next.merchant
  if (next.amount !== parseAmount(t.amount)) data.amount = next.amount
  if (next.category !== t.category) data.category = next.category
  if (next.description !== (t.description ?? null))
    data.description = next.description
  if (next.is_recurring !== t.is_recurring)
    data.is_recurring = next.is_recurring
  return data
}

/** Add a transaction, or edit one sending only what changed. */
export function TransactionFormDialog(
  props: Target & { open: boolean; onOpenChange: (open: boolean) => void },
) {
  const { open, onOpenChange } = props
  const target: Target =
    props.mode === "add"
      ? { mode: "add" }
      : { mode: "edit", transaction: props.transaction }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {/* A nested dialog (the delete confirm) gets no backdrop of its own from
          Base UI, so dim this popup under it: the two read as separate layers. */}
      <DialogContent className="data-nested-dialog-open:after:absolute data-nested-dialog-open:after:inset-0 data-nested-dialog-open:after:rounded-[inherit] data-nested-dialog-open:after:bg-black/80">
        {/* The form mounts with the popup, so each opening starts from fresh state. */}
        <TransactionForm target={target} onClose={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  )
}

function TransactionForm({
  target,
  onClose,
}: {
  target: Target
  onClose: () => void
}) {
  const { categories } = useCategories()
  const refresh = useRefreshTransactionsOnSuccess()
  // The add dialog explains a duplicate inline, so QueryProvider must not toast it.
  const create = useCreateTransaction({
    mutation: { ...refresh.mutation, meta: { silentError: isDuplicate } },
  })
  const update = useUpdateTransaction(refresh)
  const [form, setForm] = useState<FormState>(() => initialState(target))
  const [amountError, setAmountError] = useState(false)
  const [missing, setMissing] = useState(false)
  const [duplicate, setDuplicate] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((f) => ({ ...f, [key]: value }))
    setDuplicate(false)
    setMissing(false)
    if (key === "amount") setAmountError(false)
  }

  const submit = (allowDuplicate: boolean) => {
    const amount = parseAmount(form.amount)
    if (!amount) return setAmountError(true)
    const merchant = form.merchant.trim()
    if (!form.date || !merchant || !form.category) return setMissing(true)
    const values: Values = {
      date: form.date,
      merchant,
      amount,
      category: form.category,
      description: form.description.trim() || null,
      is_recurring: form.recurring,
    }
    if (target.mode === "add") {
      create.mutate(
        { data: { ...values, allow_duplicate: allowDuplicate } },
        {
          onSuccess: onClose,
          onError: (error) => {
            if (isDuplicate(error)) setDuplicate(true)
          },
        },
      )
      return
    }
    const data = changes(target.transaction, values)
    if (Object.keys(data).length === 0) return onClose()
    update.mutate(
      { transactionId: target.transaction.id, data },
      { onSuccess: onClose },
    )
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    submit(false)
  }

  // A saved form stays disabled through the closing animation.
  const pending =
    create.isPending || update.isPending || create.isSuccess || update.isSuccess
  const adding = target.mode === "add"
  // A duplicate's notice is worded from the dialog's own input, never the error body.
  const duplicateText = `You already have a transaction on ${formatDate(form.date)} at ${form.merchant.trim()} for ${formatSignedAmount(parseAmount(form.amount) ?? "0")}.`

  return (
    <>
      <DialogHeader>
        <DialogTitle>
          {adding ? "Add a transaction" : "Edit transaction"}
        </DialogTitle>
        <DialogDescription>
          Money out is negative, money in positive.
        </DialogDescription>
      </DialogHeader>
      <form onSubmit={onSubmit} className="grid gap-4" noValidate>
        <div className="grid gap-2">
          <Label htmlFor="transaction-date">Date</Label>
          <DatePicker
            id="transaction-date"
            value={form.date}
            onChange={(date) => set("date", date)}
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="transaction-merchant">Merchant</Label>
          <Input
            id="transaction-merchant"
            required
            maxLength={255}
            value={form.merchant}
            onChange={(e) => set("merchant", e.target.value)}
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="transaction-amount">Amount</Label>
          <Input
            id="transaction-amount"
            required
            inputMode="decimal"
            placeholder="-9.99"
            aria-invalid={amountError || undefined}
            aria-describedby="transaction-amount-hint"
            value={form.amount}
            onChange={(e) => set("amount", e.target.value)}
          />
          <p
            id="transaction-amount-hint"
            className={
              amountError
                ? "text-xs text-destructive"
                : "text-xs text-muted-foreground"
            }
          >
            {amountError ? AMOUNT_ERROR : "Negative for money out"}
          </p>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="transaction-category">Category</Label>
          <CategorySelect
            id="transaction-category"
            value={form.category}
            onChange={(category) => set("category", category)}
            categories={categories}
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="transaction-description">Description</Label>
          <Textarea
            id="transaction-description"
            maxLength={1000}
            value={form.description}
            onChange={(e) => set("description", e.target.value)}
          />
        </div>
        <div className="flex items-center gap-2">
          <Switch
            id="transaction-recurring"
            checked={form.recurring}
            onCheckedChange={(checked) => set("recurring", checked)}
          />
          <Label htmlFor="transaction-recurring">Recurring</Label>
        </div>
        {missing && <p className="text-xs text-destructive">{MISSING_ERROR}</p>}
        {duplicate && (
          <p
            role="alert"
            className="rounded-lg bg-muted px-3 py-2 text-sm text-foreground"
          >
            {duplicateText}
          </p>
        )}
        <DialogFooter>
          {target.mode === "edit" && (
            <Button
              type="button"
              variant="destructive"
              className="sm:mr-auto"
              disabled={pending}
              onClick={() => setConfirmingDelete(true)}
            >
              Delete
            </Button>
          )}
          <DialogClose render={<Button type="button" variant="outline" />}>
            Cancel
          </DialogClose>
          {duplicate ? (
            <Button
              type="button"
              disabled={pending}
              onClick={() => submit(true)}
            >
              Add anyway
            </Button>
          ) : (
            <Button type="submit" disabled={pending}>
              {adding ? "Add" : "Save"}
            </Button>
          )}
        </DialogFooter>
      </form>
      {target.mode === "edit" && confirmingDelete && (
        <DeleteTransactionsDialog
          ids={[target.transaction.id]}
          open
          onOpenChange={(open) => !open && setConfirmingDelete(false)}
          onDeleted={onClose}
        />
      )}
    </>
  )
}
