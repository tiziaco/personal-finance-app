"use client"

import { Bar, BarChart, CartesianGrid, Cell, XAxis, YAxis } from "recharts"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@app/ui/chart"
import { formatAmount } from "@/components/transactions/format"
import { ChartLegend } from "./chart-legend"
import {
  BAR_TOOLTIP,
  GRID,
  MARGIN,
  MONEY_Y_AXIS,
  X_AXIS,
  monthTooltipLabel,
  partialOpacity,
  pointOf,
} from "./chart-parts"
import type { MonthPoint } from "./month-points"

const config: ChartConfig = {
  income: { label: "Income", color: "var(--chart-income)" },
  expenses: { label: "Expenses", color: "var(--chart-expense)" },
}

/** Grouped bars of income and expenses per month; a partial month is drawn lighter. */
export function FlowChart({ points }: { points: MonthPoint[] }) {
  return (
    <div className="flex flex-col gap-3">
      <ChartLegend config={config} />
      <ChartContainer config={config} className="aspect-[2/1] w-full">
        <BarChart data={points} margin={MARGIN}>
          <CartesianGrid {...GRID} />
          <XAxis {...X_AXIS} />
          <YAxis {...MONEY_Y_AXIS} />
          <ChartTooltip
            {...BAR_TOOLTIP}
            content={({ active, payload }) => (
              <ChartTooltipContent
                active={active}
                payload={payload}
                label={monthTooltipLabel(pointOf<MonthPoint>(payload))}
                formatter={(value) => formatAmount(String(value))}
              />
            )}
          />
          {(["income", "expenses"] as const).map((key) => (
            <Bar
              key={key}
              dataKey={key}
              fill={`var(--color-${key})`}
              radius={[3, 3, 0, 0]}
              isAnimationActive={false}
            >
              {points.map((p) => (
                <Cell key={p.month} fillOpacity={partialOpacity(p)} />
              ))}
            </Bar>
          ))}
        </BarChart>
      </ChartContainer>
    </div>
  )
}
