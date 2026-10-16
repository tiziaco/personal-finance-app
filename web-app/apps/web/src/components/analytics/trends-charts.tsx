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
import { formatMonth } from "@/components/dashboard/month"
import { TONE_FILL } from "./change"
import { changeTone, formatPct } from "./format"
import type { TrendsPoint } from "./trends-points"

const compact = new Intl.NumberFormat(undefined, {
  notation: "compact",
  maximumFractionDigits: 1,
})

const MARGIN = { left: 4, right: 8, top: 8 }

const monthLabel = (point?: TrendsPoint) =>
  point
    ? `${formatMonth(point.month)}${point.partial ? " (so far)" : ""}`
    : undefined

const pointOf = (payload?: readonly { payload?: unknown }[]) =>
  payload?.[0]?.payload as TrendsPoint | undefined

const spendingConfig: ChartConfig = {
  expenses: { label: "Expenses", color: "var(--chart-expense)" },
  rollingAvg: { label: "3-month average", color: "var(--chart-income)" },
}

/** Expense bars per month (a partial month lighter) with the 3-month average as a line that breaks at gaps. */
export function SpendingTrendChart({ points }: { points: TrendsPoint[] }) {
  return (
    <ChartContainer config={spendingConfig} className="aspect-[2/1] w-full">
      <ComposedChart data={points} margin={MARGIN}>
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
          content={({ active, payload }) => (
            <ChartTooltipContent
              active={active}
              payload={payload}
              label={monthLabel(pointOf(payload))}
              formatter={(value, name) => (
                <span className="flex w-full justify-between gap-4">
                  <span className="text-muted-foreground">
                    {spendingConfig[String(name)]?.label ?? name}
                  </span>
                  <span className="font-mono tabular-nums">
                    {value === null || value === undefined
                      ? "—"
                      : formatAmount(String(value))}
                  </span>
                </span>
              )}
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
            <Cell key={p.month} fillOpacity={p.partial ? 0.4 : 1} />
          ))}
        </Bar>
        <Line
          dataKey="rollingAvg"
          type="monotone"
          stroke="var(--color-rollingAvg)"
          strokeWidth={2}
          dot={false}
          connectNulls={false}
          isAnimationActive={false}
        />
      </ComposedChart>
    </ChartContainer>
  )
}

const changeConfig: ChartConfig = {
  change: { label: "Change in expenses", color: "var(--chart-expense)" },
}

/** The change in expenses on the month before, around a zero line; more spending is bad. */
export function MonthChangeChart({ points }: { points: TrendsPoint[] }) {
  return (
    <ChartContainer config={changeConfig} className="aspect-[2/1] w-full">
      <BarChart data={points} margin={MARGIN}>
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
          tickFormatter={(v: number) => `${v}%`}
        />
        <ReferenceLine y={0} className="stroke-muted-foreground" />
        <ChartTooltip
          content={({ active, payload }) => {
            const point = pointOf(payload)
            if (!active || !point) return null
            return (
              <div className="rounded-lg border bg-background px-2.5 py-1.5 text-xs shadow-xl">
                <p className="font-medium">{monthLabel(point)}</p>
                <p className="tabular-nums text-muted-foreground">
                  {point.change === null ? "—" : formatPct(point.change)}
                </p>
              </div>
            )
          }}
        />
        <Bar dataKey="change" radius={[3, 3, 0, 0]} isAnimationActive={false}>
          {points.map((p) => (
            <Cell
              key={p.month}
              className={TONE_FILL[changeTone(p.change, "spend")]}
              fillOpacity={p.partial ? 0.4 : 1}
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
export function SavingsRateChart({ points }: { points: TrendsPoint[] }) {
  return (
    <ChartContainer config={rateConfig} className="aspect-[2/1] w-full">
      <LineChart data={points} margin={MARGIN}>
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
          tickFormatter={(v: number) => `${v}%`}
        />
        <ReferenceLine y={0} className="stroke-muted-foreground" />
        <ChartTooltip
          content={({ active, payload }) => {
            const point = pointOf(payload)
            if (!active || !point) return null
            return (
              <div className="rounded-lg border bg-background px-2.5 py-1.5 text-xs shadow-xl">
                <p className="font-medium">{monthLabel(point)}</p>
                <p className="tabular-nums text-muted-foreground">
                  {point.savingsRate === null
                    ? "—"
                    : formatPct(point.savingsRate)}
                </p>
              </div>
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
