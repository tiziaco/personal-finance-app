import type { CategoryTrendResponse } from "@app/api-client/types"
import { Badge } from "@app/ui/badge"

import { formatAmount } from "@/components/transactions/format"
import { useCategories } from "@/components/transactions/use-categories"

import { TONE_CLASS } from "./change"
import { changeTone, formatPct } from "./format"

/** "new" when there was no earlier spend, "stopped" when the later half is zero, else the percent. */
function MoverPct({ pct }: { pct: number | null }) {
  if (pct === null) return <Badge variant="secondary">new</Badge>
  const tone = changeTone(pct, "spend")
  return (
    <span data-tone={tone} className={TONE_CLASS[tone]}>
      <span aria-hidden>{pct > 0 ? "▲" : "▼"}</span>{" "}
      {pct === -100 ? "stopped" : formatPct(Math.abs(pct))}
    </span>
  )
}

/** One list of categories whose monthly average moved between the two halves of the period. */
export function CategoryMovers({
  rows,
  empty,
}: {
  rows: CategoryTrendResponse[]
  empty: string
}) {
  const { label } = useCategories()
  if (rows.length === 0) {
    return <p className="text-sm text-muted-foreground">{empty}</p>
  }
  return (
    <ul className="flex flex-col gap-3">
      {rows.map((r) => (
        <li key={r.category} className="flex justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate font-medium">{label(r.category)}</p>
            <p className="text-xs text-muted-foreground">
              {`${formatAmount(r.earlier_monthly_average)} → ${formatAmount(r.later_monthly_average)} per month`}
            </p>
          </div>
          <div className="text-right tabular-nums">
            <p>{formatAmount(r.change_amount)}</p>
            <p className="text-xs">
              <MoverPct pct={r.change_pct} />
            </p>
          </div>
        </li>
      ))}
    </ul>
  )
}
