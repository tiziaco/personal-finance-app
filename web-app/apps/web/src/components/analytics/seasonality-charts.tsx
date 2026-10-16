"use client"

import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts"
import { ChartContainer, ChartTooltip, type ChartConfig } from "@app/ui/chart"
import {
  BAR_TOOLTIP,
  GRID,
  MARGIN,
  MONEY_Y_AXIS,
  TooltipBox,
  X_AXIS,
} from "./chart-parts"
import type { MonthOfYearPoint, WeekdayPoint } from "./seasonality-points"

const weekdayConfig: ChartConfig = {
  perDay: { label: "Average per day", color: "var(--chart-expense)" },
}

/** Average spend per day for each weekday, Monday first. */
export function WeekdayChart({ points }: { points: WeekdayPoint[] }) {
  return (
    <ChartContainer config={weekdayConfig} className="aspect-[2/1] w-full">
      <BarChart data={points} margin={MARGIN}>
        <CartesianGrid {...GRID} />
        <XAxis {...X_AXIS} />
        <YAxis {...MONEY_Y_AXIS} />
        <ChartTooltip
          {...BAR_TOOLTIP}
          content={({ active, payload }) => {
            const p = payload?.[0]?.payload as WeekdayPoint | undefined
            if (!active || !p) return null
            return (
              <TooltipBox>
                <p className="font-medium">{p.name}</p>
                <p className="tabular-nums text-muted-foreground">
                  {p.perDayText} average per day
                </p>
              </TooltipBox>
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
        <CartesianGrid {...GRID} />
        <XAxis {...X_AXIS} />
        <YAxis {...MONEY_Y_AXIS} />
        <ChartTooltip
          {...BAR_TOOLTIP}
          content={({ active, payload }) => {
            const p = payload?.[0]?.payload as MonthOfYearPoint | undefined
            if (!active || !p) return null
            return (
              <TooltipBox>
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
              </TooltipBox>
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
