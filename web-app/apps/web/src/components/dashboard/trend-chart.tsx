"use client"

import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts"
import type { TrendPointResponse } from "@app/api-client/types"
import { Card, CardContent, CardHeader, CardTitle } from "@app/ui/card"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@app/ui/chart"
import {
  GRID,
  MARGIN,
  MONEY_Y_AXIS,
  X_AXIS,
} from "@/components/analytics/chart-parts"
import { formatMonth } from "./month"
import { toTrendPoints, type TrendPoint } from "./trend-points"

const config: ChartConfig = {
  income: { label: "Income", color: "var(--chart-income)" },
  expenses: { label: "Expenses", color: "var(--chart-expense)" },
}

/** The series drawn dashed, in the chart and in its legend alike. */
const DASHED = new Set(["expenses"])

/** Income and expenses over the six months to the reference month. */
export function TrendChart({ points }: { points: TrendPointResponse[] }) {
  const data = toTrendPoints(points)
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle>Income and expenses</CardTitle>
        <ul className="flex gap-4 text-xs text-muted-foreground">
          {Object.entries(config).map(([key, item]) => (
            <li key={key} className="flex items-center gap-1.5">
              {DASHED.has(key) ? (
                <span
                  aria-hidden
                  className="w-3 border-t-2 border-dashed"
                  style={{ borderColor: item.color }}
                />
              ) : (
                <span
                  aria-hidden
                  className="h-0.5 w-3 rounded-full"
                  style={{ backgroundColor: item.color }}
                />
              )}
              {item.label}
            </li>
          ))}
        </ul>
      </CardHeader>
      <CardContent>
        <ChartContainer config={config} className="aspect-[2/1] w-full">
          <LineChart data={data} margin={MARGIN}>
            <CartesianGrid {...GRID} />
            <XAxis {...X_AXIS} />
            <YAxis {...MONEY_Y_AXIS} />
            {/* recharts' default cursor, a bright band in dark mode (see chart-parts); TODO.md has adopting LINE_TOOLTIP's. */}
            <ChartTooltip
              content={({ active, payload }) => {
                // payload[i].payload is the hovered row: show its exact text, not the plotted float.
                const point = payload?.[0]?.payload as TrendPoint | undefined
                return (
                  <ChartTooltipContent
                    active={active}
                    payload={payload}
                    label={point ? formatMonth(point.month) : undefined}
                    formatter={(_, key) =>
                      key === "income" ? point?.incomeText : point?.expensesText
                    }
                  />
                )
              }}
            />
            <Line
              dataKey="income"
              type="monotone"
              stroke="var(--color-income)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              dataKey="expenses"
              type="monotone"
              stroke="var(--color-expenses)"
              strokeWidth={2}
              // The design system dashes expenses beside income, so colour is never the only cue.
              strokeDasharray="6 4"
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ChartContainer>
      </CardContent>
    </Card>
  )
}
