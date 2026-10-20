"use client"

import type { CategorySpendResponse } from "@app/api-client/types"
import { Badge } from "@app/ui/badge"

import { formatAmount } from "@/components/transactions/format"
import { CategoryGlyph } from "@/components/transactions/category-icon"
import { useCategories } from "@/components/transactions/use-categories"

import { Change } from "./change"
import { formatPct } from "./format"

/** Every category as a bar sized by its share, with its change against the previous period. */
export function CategoryRanking({
  categories,
}: {
  categories: CategorySpendResponse[]
}) {
  const { label } = useCategories()
  return (
    <ul aria-label="Spending by category" className="flex flex-col gap-4">
      {categories.map((c) => (
        <li key={c.category} className="flex flex-col gap-1.5">
          <div className="flex items-baseline justify-between gap-3">
            <span className="flex min-w-0 items-center gap-2 font-medium">
              <CategoryGlyph slug={c.category} />
              <span className="truncate">{label(c.category)}</span>
            </span>
            <span className="shrink-0 tabular-nums">
              {formatAmount(c.total)}{" "}
              <span className="text-sm text-muted-foreground">
                {formatPct(c.share_pct)}
              </span>
            </span>
          </div>
          <div aria-hidden className="h-2 rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-chart-1"
              style={{ width: `${c.share_pct}%` }}
            />
          </div>
          <div className="text-sm">
            {c.previous_total !== null && c.change_pct === null ? (
              <Badge variant="secondary">new</Badge>
            ) : (
              <Change pct={c.change_pct} kind="spend" up="more" down="less" />
            )}
          </div>
        </li>
      ))}
    </ul>
  )
}
