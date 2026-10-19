"use client"

import { useGetCategoryBreakdown } from "@app/api-client/endpoints/analytics"
import { cn } from "@app/core/lib/utils"
import { Skeleton } from "@app/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@app/ui/table"

import { formatAmount } from "@/components/transactions/format"
import { useCategories } from "@/components/transactions/use-categories"

import { CategoryRanking } from "./category-ranking"
import { formatPeriod, purchases } from "./format"
import { PeriodSelect } from "./period-select"
import { ANALYTICS_QUERY } from "./query"
import { QueryGate } from "./query-gate"
import { Section } from "./section"
import { TopMerchants } from "./top-merchants"
import { PERIODS } from "./use-analytics-params"

const WHAT = "your spending by category"
const EMPTY = "No spending in this period."

/** No period, or nothing spent in it. A test of the figure, not arithmetic on it. */
const isEmpty = (data: { date_from: string | null; total_expenses: string }) =>
  data.date_from === null || Number(data.total_expenses) === 0

export function CategoryTab({
  months,
  onMonthsChange,
}: {
  months: number
  onMonthsChange: (months: number) => void
}) {
  const { label } = useCategories()
  const query = useGetCategoryBreakdown({ months, top_n: 50 }, ANALYTICS_QUERY)
  const data = query.data
  const period = data && formatPeriod(data.date_from, data.date_to)
  const previous =
    data && formatPeriod(data.previous_date_from, data.previous_date_to)

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3">
        <PeriodSelect
          choices={PERIODS.category.choices}
          value={months}
          onChange={onMonthsChange}
        />
        {period ? (
          <p
            className={cn(
              "text-sm text-muted-foreground",
              query.isPlaceholderData && "opacity-60",
            )}
          >
            {period}
          </p>
        ) : null}
      </header>

      <QueryGate
        query={query}
        what={WHAT}
        isEmpty={isEmpty}
        empty={EMPTY}
        skeleton={
          <>
            <Section title="Spending by category">
              <Skeleton className="h-64 w-full" />
            </Section>
            <Section title="How often vs how much">
              <Skeleton className="h-40 w-full" />
            </Section>
          </>
        }
      >
        {(d) => (
          <>
            <div className="-mt-3">
              <p className="text-sm text-muted-foreground">Total spent</p>
              <p className="text-3xl font-semibold tabular-nums">
                {formatAmount(d.total_expenses)}
              </p>
              {previous ? (
                <p className="text-sm text-muted-foreground">
                  compared with {previous}
                </p>
              ) : null}
            </div>

            <Section title="Spending by category">
              <CategoryRanking categories={d.top_categories} />
            </Section>

            <Section title="How often vs how much">
              <>
                <Table className="hidden sm:table">
                  <TableHeader>
                    <TableRow>
                      <TableHead>Category</TableHead>
                      <TableHead className="text-right">Purchases</TableHead>
                      <TableHead className="text-right">Average each</TableHead>
                      <TableHead className="text-right">Total</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {d.by_frequency.map((c) => (
                      <TableRow key={c.category}>
                        <TableCell>{label(c.category)}</TableCell>
                        <TableCell className="text-right tabular-nums">
                          {c.count}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {formatAmount(c.average)}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {formatAmount(c.total)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                <ul className="flex flex-col gap-3 sm:hidden">
                  {d.by_frequency.map((c) => (
                    <li key={c.category} className="flex justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate font-medium">
                          {label(c.category)}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {purchases(c.count)} · {formatAmount(c.average)} each
                        </p>
                      </div>
                      <span className="tabular-nums">
                        {formatAmount(c.total)}
                      </span>
                    </li>
                  ))}
                </ul>
              </>
            </Section>
          </>
        )}
      </QueryGate>

      <TopMerchants months={months} />
    </div>
  )
}
