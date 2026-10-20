"use client"

import { Pie, PieChart } from "recharts"
import type { CategorySliceResponse } from "@app/api-client/types"
import { Card, CardContent, CardHeader, CardTitle } from "@app/ui/card"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@app/ui/chart"
import { useCategories } from "@/components/transactions/use-categories"
import { toCategorySlices } from "./category-slices"

/** A donut of the month's top five categories plus Other, with a labelled legend beside it. */
export function CategoryChart({ slices }: { slices: CategorySliceResponse[] }) {
  const { label } = useCategories()
  const data = toCategorySlices(slices, label)
  const config: ChartConfig = Object.fromEntries(
    data.map((s) => [s.key, { label: s.name, color: s.fill }]),
  )
  const display = new Map(data.map((s) => [s.key, s.display]))
  return (
    <Card>
      <CardHeader>
        <CardTitle>Spending by category</CardTitle>
      </CardHeader>
      {data.length === 0 ? (
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No spending this month.
          </p>
        </CardContent>
      ) : (
        // Beside the legend the donut gives way first: it shrinks toward its floor before a name
        // is cut, and the two sit centred in a card the line chart beside it may make taller.
        <CardContent className="flex flex-1 flex-col items-center gap-6 sm:flex-row">
          <ChartContainer
            config={config}
            className="aspect-square min-w-36 shrink-[100] basis-60"
          >
            <PieChart>
              <ChartTooltip
                content={
                  <ChartTooltipContent
                    hideLabel
                    formatter={(_, key) => display.get(key)}
                  />
                }
              />
              <Pie
                data={data}
                dataKey="amount"
                nameKey="key"
                innerRadius="58%"
                outerRadius="100%"
                stroke="var(--chart-gap)"
                strokeWidth={2}
                isAnimationActive={false}
              />
            </PieChart>
          </ChartContainer>
          {/* min-w-0: beside the donut a flex item won't shrink below its nowrap names, and the card clips the amounts. */}
          <ul className="w-full min-w-0 space-y-2 text-sm sm:w-auto sm:flex-auto">
            {data.map((s) => (
              <li key={s.key} className="flex items-start gap-2">
                <span
                  aria-hidden
                  className="mt-[5px] size-2.5 shrink-0 rounded-[2px]"
                  style={{ backgroundColor: s.fill }}
                />
                <span className="min-w-0 flex-1 truncate">{s.name}</span>
                <span className="flex flex-col items-end tabular-nums">
                  {s.display}
                  <span className="text-xs text-muted-foreground">
                    {s.share.toFixed(1)}%
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </CardContent>
      )}
    </Card>
  )
}
