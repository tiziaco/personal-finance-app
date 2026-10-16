"use client"

import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts"
import { ChartContainer, ChartTooltip, type ChartConfig } from "@app/ui/chart"
import { BAR_TOOLTIP } from "./chart-tooltip"
import type { MonthOfYearPoint, WeekdayPoint } from "./seasonality-points"

const compact = new Intl.NumberFormat(undefined, {
  notation: "compact",
  maximumFractionDigits: 1,
})

const MARGIN = { left: 4, right: 8, top: 8 }

const TIP = "rounded-lg border bg-background px-2.5 py-1.5 text-xs shadow-xl"

const weekdayConfig: ChartConfig = {
  perDay: { label: "Average per day", color: "var(--chart-expense)" },
}

/** Average spend per day for each weekday, Monday first. */
export function WeekdayChart({ points }: { points: WeekdayPoint[] }) {
  return (
    <ChartContainer config={weekdayConfig} className="aspect-[2/1] w-full">
      <BarChart data={points} margin={MARGIN}>
        <CartesianGrid vertical={false} strokeDasharray="3 3" />
        <XAxis
          dataKey="name"
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          tickFormatter={(v: string) => v.slice(0, 3)}
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
            const p = payload?.[0]?.payload as WeekdayPoint | undefined
            if (!active || !p) return null
            return (
              <div className={TIP}>
                <p className="font-medium">{p.name}</p>
                <p className="tabular-nums text-muted-foreground">
                  {p.perDayText} average per day
                </p>
              </div>
            )
          }}
        />
        <Bar
          dataKey="perDay"
          fill="var(--color-perDay)"
          radius={[3, 3, 0, 0]}
          isAnimationActive={false}
        />
      </BarChart>
    </ChartContainer>
  )
}

const monthConfig: ChartConfig = {
  average: { label: "Average", color: "var(--chart-expense)" },
}

/** Average spend for each calendar month; a month with no history has no bar. */
export function MonthOfYearChart({ points }: { points: MonthOfYearPoint[] }) {
  return (
    <ChartContainer config={monthConfig} className="aspect-[2/1] w-full">
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
          tickFormatter={(v: number) => compact.format(v)}
        />
        <ChartTooltip
          {...BAR_TOOLTIP}
          content={({ active, payload }) => {
            const p = payload?.[0]?.payload as MonthOfYearPoint | undefined
            if (!active || !p) return null
            return (
              <div className={TIP}>
                <p className="font-medium">{p.label}</p>
                {p.years === 0 ? (
                  <p className="text-muted-foreground">no data yet</p>
                ) : (
                  <>
                    <p className="tabular-nums">{p.averageText}</p>
                    <p className="text-muted-foreground">{p.indexText}</p>
                    <p className="text-muted-foreground">
                      average of {p.years} {p.years === 1 ? "year" : "years"}
                    </p>
                  </>
                )}
              </div>
            )
          }}
        />
        <Bar
          dataKey="average"
          fill="var(--color-average)"
          radius={[3, 3, 0, 0]}
          isAnimationActive={false}
        />
      </BarChart>
    </ChartContainer>
  )
}
