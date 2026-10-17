"use client"

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  LineChart,
  ReferenceLine,
  XAxis,
  YAxis,
} from "recharts"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@app/ui/chart"
import { formatAmount } from "@/components/transactions/format"
import { TONE_FILL } from "./change"
import { ChartLegend } from "./chart-legend"
import {
  BAR_TOOLTIP,
  GRID,
  LINE_TOOLTIP,
  MARGIN,
  MONEY_Y_AXIS,
  PCT_Y_AXIS,
  TooltipBox,
  X_AXIS,
  monthTooltipLabel,
  partialOpacity,
  pointOf,
} from "./chart-parts"
import { changeTone, formatPct } from "./format"
import type { MonthPoint } from "./month-points"

const spendingConfig: ChartConfig = {
  expenses: { label: "Expenses", color: "var(--chart-expense)" },
  rollingAvg: { label: "3-month average", color: "var(--muted-foreground)" },
}

/** Expense bars per month (a partial month lighter) with the 3-month average as a line that breaks at gaps. */
export function SpendingTrendChart({ points }: { points: MonthPoint[] }) {
  return (
    <div className="flex flex-col gap-3">
      <ChartLegend config={spendingConfig} />
      <ChartContainer config={spendingConfig} className="aspect-[2/1] w-full">
        {/* A ComposedChart draws a line cursor, so it takes LINE_TOOLTIP (a bar cursor's fill would not apply). */}
        <ComposedChart data={points} margin={MARGIN}>
          <CartesianGrid {...GRID} />
          <XAxis {...X_AXIS} />
          <YAxis {...MONEY_Y_AXIS} />
          <ChartTooltip
            {...LINE_TOOLTIP}
            content={({ active, payload }) => (
              <ChartTooltipContent
                active={active}
                payload={payload}
                label={monthTooltipLabel(pointOf<MonthPoint>(payload))}
                formatter={(value) =>
                  value === null || value === undefined
                    ? "—"
                    : formatAmount(String(value))
                }
              />
            )}
          />
          <Bar
            dataKey="expenses"
            fill="var(--color-expenses)"
            radius={[3, 3, 0, 0]}
            isAnimationActive={false}
          >
            {points.map((p) => (
              <Cell key={p.month} fillOpacity={partialOpacity(p)} />
            ))}
          </Bar>
          <Line
            dataKey="rollingAvg"
            type="monotone"
            stroke="var(--color-rollingAvg)"
            strokeWidth={2}
            strokeDasharray="5 3"
            dot={false}
            connectNulls={false}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ChartContainer>
    </div>
  )
}

const changeConfig: ChartConfig = {
  change: { label: "Change in expenses", color: "var(--chart-expense)" },
}

/** The change in expenses on the month before, around a zero line; more spending is bad. */
export function MonthChangeChart({ points }: { points: MonthPoint[] }) {
  return (
    <ChartContainer config={changeConfig} className="aspect-[2/1] w-full">
      <BarChart data={points} margin={MARGIN}>
        <CartesianGrid {...GRID} />
        <XAxis {...X_AXIS} />
        <YAxis {...PCT_Y_AXIS} />
        <ReferenceLine y={0} className="stroke-muted-foreground" />
        <ChartTooltip
          {...BAR_TOOLTIP}
          content={({ active, payload }) => {
            const point = pointOf<MonthPoint>(payload)
            if (!active || !point) return null
            return (
              <TooltipBox>
                <p className="font-medium">{monthTooltipLabel(point)}</p>
                <p className="tabular-nums text-muted-foreground">
                  {point.change === null ? "—" : formatPct(point.change)}
                </p>
              </TooltipBox>
            )
          }}
        />
        <Bar dataKey="change" radius={[3, 3, 0, 0]} isAnimationActive={false}>
          {points.map((p) => (
            <Cell
              key={p.month}
              className={TONE_FILL[changeTone(p.change, "spend")]}
              fillOpacity={partialOpacity(p)}
            />
          ))}
        </Bar>
      </BarChart>
    </ChartContainer>
  )
}

const rateConfig: ChartConfig = {
  savingsRate: { label: "Savings rate", color: "var(--chart-income)" },
}

/** The savings rate per month as a line that breaks where there is no income. */
export function SavingsRateChart({ points }: { points: MonthPoint[] }) {
  return (
    <ChartContainer config={rateConfig} className="aspect-[2/1] w-full">
      <LineChart data={points} margin={MARGIN}>
        <CartesianGrid {...GRID} />
        <XAxis {...X_AXIS} />
        <YAxis {...PCT_Y_AXIS} />
        <ReferenceLine y={0} className="stroke-muted-foreground" />
        <ChartTooltip
          {...LINE_TOOLTIP}
          content={({ active, payload }) => {
            const point = pointOf<MonthPoint>(payload)
            if (!active || !point) return null
            return (
              <TooltipBox>
                <p className="font-medium">{monthTooltipLabel(point)}</p>
                <p className="tabular-nums text-muted-foreground">
                  {point.savingsRate === null
                    ? "—"
                    : formatPct(point.savingsRate)}
                </p>
              </TooltipBox>
            )
          }}
        />
        <Line
          dataKey="savingsRate"
          type="monotone"
          stroke="var(--color-savingsRate)"
          strokeWidth={2}
          dot={{ r: 3 }}
          connectNulls={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ChartContainer>
  )
}
