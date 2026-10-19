"use client"

import { useId } from "react"
import type { TransactionResponse } from "@app/api-client/types"
import { Card, CardContent } from "@app/ui/card"
import { CategoryTile } from "./category-icon"
import { cn } from "@app/core/lib/utils"
import {
  formatDate,
  formatSignedAmount,
  transactionAmountClass,
} from "./format"

/** A transaction on a phone: tapping it opens the edit dialog. */
export function TransactionCard({
  transaction,
  categoryLabel,
  onEdit,
}: {
  transaction: TransactionResponse
  categoryLabel: string
  onEdit: () => void
}) {
  const id = useId()
  const meta = `${formatDate(transaction.date)} · ${categoryLabel}`
  return (
    <button
      type="button"
      onClick={onEdit}
      aria-label={`Edit ${transaction.merchant}`}
      aria-describedby={`${id}-meta ${id}-amount`}
      className="block w-full rounded-xl text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <Card size="sm" className="transition-colors active:bg-muted">
        <CardContent className="flex items-center gap-3">
          <CategoryTile slug={transaction.category} />
          <div className="min-w-0 flex-1">
            <p className="truncate font-medium">{transaction.merchant}</p>
            <p id={`${id}-meta`} className="text-xs text-muted-foreground">
              {meta}
            </p>
          </div>
          <span
            id={`${id}-amount`}
            className={cn(
              "tabular-nums",
              transactionAmountClass(transaction.amount),
            )}
          >
            {formatSignedAmount(transaction.amount)}
          </span>
        </CardContent>
      </Card>
    </button>
  )
}
