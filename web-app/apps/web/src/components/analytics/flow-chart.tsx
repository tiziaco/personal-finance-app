"use client"

import { Bar, BarChart, CartesianGrid, Cell, XAxis, YAxis } from "recharts"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@app/ui/chart"
import { formatAmount } from "@/components/transactions/format"
import { formatMonth } from "@/components/dashboard/month"
import { ChartLegend } from "./chart-legend"
import { BAR_TOOLTIP } from "./chart-tooltip"
import type { FlowPoint } from "./flow-points"

const config: ChartConfig = {
  income: { label: "Income", color: "var(--chart-income)" },
  expenses: { label: "Expenses", color: "var(--chart-expense)" },
}

const compact = new Intl.NumberFormat(undefined, {
  notation: "compact",
  maximumFractionDigits: 1,
})

/** Grouped bars of income and expenses per month; a partial month is drawn lighter. */
export function FlowChart({ points }: { points: FlowPoint[] }) {
  return (
    <div className="flex flex-col gap-3">
      <ChartLegend config={config} />
      <ChartContainer config={config} className="aspect-[2/1] w-full">
        <BarChart data={points} margin={{ left: 4, right: 8, top: 8 }}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis
            dataKey="label"
            tickLine={false}
            axisLine={false}
            tickMargin={8}
          />
          <YAxis
            tickLine={false}
            axisLine={false}
            width={48}
            tickFormatter={(v: number) => compact.format(v)}
          />
          <ChartTooltip
            {...BAR_TOOLTIP}
            content={({ active, payload }) => {
              const point = payload?.[0]?.payload as FlowPoint | undefined
              return (
                <ChartTooltipContent
                  active={active}
                  payload={payload}
                  label={
                    point
                      ? `${formatMonth(point.month)}${point.partialLabel ? ` (${point.partialLabel})` : ""}`
                      : undefined
                  }
                  formatter={(value) => formatAmount(String(value))}
                />
              )
            }}
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
                <Cell key={p.month} fillOpacity={p.partial ? 0.4 : 1} />
              ))}
            </Bar>
          ))}
        </BarChart>
      </ChartContainer>
    </div>
  )
}
