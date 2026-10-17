import { useId, type ComponentType } from "react"
import {
  CreditCard,
  PiggyBank,
  RefreshCw,
  TrendingDown,
  TrendingUp,
} from "lucide-react"
import type { DashboardResponse } from "@app/api-client/types"
import { Card, CardContent, CardHeader, CardTitle } from "@app/ui/card"
import { cn } from "@app/core/lib/utils"
import { formatAmount, isExpense } from "@/components/transactions/format"
import { formatMonth } from "./month"

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`

function SummaryCard({
  title,
  value,
  subtitle,
  icon: Icon,
  negative = false,
}: {
  title: string
  value: string
  subtitle: string
  icon: ComponentType<{ className?: string }>
  negative?: boolean
}) {
  const id = useId()
  return (
    <Card role="group" aria-labelledby={id} size="sm">
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle
          id={id}
          className="text-sm font-medium text-muted-foreground"
        >
          {title}
        </CardTitle>
        <Icon className="size-4 text-muted-foreground" />
      </CardHeader>
      <CardContent className="space-y-1">
        <p
          className={cn(
            "text-2xl font-semibold tabular-nums",
            negative && "text-destructive",
          )}
        >
          {formatAmount(value)}
        </p>
        <p className="text-xs text-muted-foreground">{subtitle}</p>
      </CardContent>
    </Card>
  )
}

/** The four cards for the reference month: two by two on a phone, one row from md up. */
export function SummaryCards({
  dashboard,
  className,
}: {
  dashboard: DashboardResponse
  className?: string
}) {
  const month = dashboard.reference_month
    ? formatMonth(dashboard.reference_month)
    : ""
  const netNegative = isExpense(dashboard.net_balance)
  return (
    <div className={cn("grid grid-cols-2 gap-4 md:grid-cols-4", className)}>
      <SummaryCard
        title="Total Spent"
        value={dashboard.total_spent}
        subtitle={month}
        icon={CreditCard}
      />
      <SummaryCard
        title="Recurring Costs"
        value={dashboard.recurring_spent}
        subtitle={plural(dashboard.recurring_count, "recurring payment")}
        icon={RefreshCw}
      />
      <SummaryCard
        title="Net Balance"
        value={dashboard.net_balance}
        subtitle={month}
        icon={netNegative ? TrendingDown : TrendingUp}
        negative={netNegative}
      />
      <SummaryCard
        title="Average Cashflow"
        value={dashboard.average_cashflow}
        subtitle={`average of ${plural(dashboard.cashflow_months, "month")}`}
        icon={PiggyBank}
        negative={isExpense(dashboard.average_cashflow)}
      />
    </div>
  )
}
