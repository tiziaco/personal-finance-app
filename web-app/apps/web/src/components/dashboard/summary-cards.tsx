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
import { amountSign } from "@/components/transactions/format"
import { Money } from "@/components/transactions/money"
import { formatMonth } from "./month"

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`

function SummaryCard({
  title,
  value,
  subtitle,
  icon: Icon,
  kind = "total",
}: {
  title: string
  value: string
  subtitle: string
  icon: ComponentType<{ className?: string }>
  /** A net is signed and toned; a total stays unsigned. */
  kind?: "total" | "net"
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
        <p className="text-2xl font-semibold">
          <Money amount={value} kind={kind} />
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
  const netNegative = amountSign(dashboard.net_balance) < 0
  return (
    <div className={cn("grid grid-cols-2 gap-4 md:grid-cols-4", className)}>
      <SummaryCard
        title="Total spent"
        value={dashboard.total_spent}
        subtitle={month}
        icon={CreditCard}
      />
      <SummaryCard
        title="Recurring costs"
        value={dashboard.recurring_spent}
        subtitle={plural(dashboard.recurring_count, "recurring payment")}
        icon={RefreshCw}
      />
      <SummaryCard
        title="Net balance"
        value={dashboard.net_balance}
        subtitle={month}
        icon={netNegative ? TrendingDown : TrendingUp}
        kind="net"
      />
      <SummaryCard
        title="Average cashflow"
        value={dashboard.average_cashflow}
        subtitle={`average of ${plural(dashboard.cashflow_months, "month")}`}
        icon={PiggyBank}
        kind="net"
      />
    </div>
  )
}
