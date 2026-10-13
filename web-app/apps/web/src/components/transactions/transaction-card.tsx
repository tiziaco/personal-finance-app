import type { TransactionResponse } from "@app/api-client/types"
import { Card, CardContent } from "@app/ui/card"
import { formatAmount, formatDate, isExpense } from "./format"

export function TransactionCard({
  transaction,
  categoryLabel,
}: {
  transaction: TransactionResponse
  categoryLabel: string
}) {
  const meta = `${formatDate(transaction.date)} · ${categoryLabel}`
  return (
    <Card size="sm">
      <CardContent className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-medium">{transaction.merchant}</p>
          <p className="text-xs text-muted-foreground">{meta}</p>
        </div>
        <span
          className={
            isExpense(transaction.amount)
              ? "text-destructive tabular-nums"
              : "text-emerald-600 tabular-nums dark:text-emerald-400"
          }
        >
          {formatAmount(transaction.amount)}
        </span>
      </CardContent>
    </Card>
  )
}
