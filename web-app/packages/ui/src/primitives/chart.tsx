"use client"

import * as React from "react"
import * as RechartsPrimitive from "recharts"
import { cn } from "@app/core/lib/utils"

/** Per-series label and colour, keyed by data key (a line) or by name (a pie slice). */
export type ChartConfig = Record<
  string,
  { label: React.ReactNode; color: string }
>

const ChartContext = React.createContext<{ config: ChartConfig } | null>(null)

function useChart() {
  const context = React.useContext(ChartContext)
  if (!context) {
    throw new Error("useChart must be used within a <ChartContainer />")
  }
  return context
}

/** Sizes a Recharts chart to its box and exposes each series colour as --color-<key>. */
function ChartContainer({
  config,
  className,
  style,
  children,
  ...props
}: React.ComponentProps<"div"> & {
  config: ChartConfig
  children: React.ComponentProps<
    typeof RechartsPrimitive.ResponsiveContainer
  >["children"]
}) {
  const colors = Object.fromEntries(
    Object.entries(config).map(([key, item]) => [`--color-${key}`, item.color]),
  )
  return (
    <ChartContext.Provider value={{ config }}>
      <div
        data-slot="chart"
        style={{ ...colors, ...style } as React.CSSProperties}
        className={cn(
          "flex justify-center text-xs [&_.recharts-cartesian-axis-tick_text]:fill-muted-foreground [&_.recharts-cartesian-grid_line]:stroke-border [&_.recharts-layer]:outline-hidden [&_.recharts-sector]:outline-hidden [&_.recharts-surface]:outline-hidden",
          className,
        )}
        {...props}
      >
        <RechartsPrimitive.ResponsiveContainer
          initialDimension={{ width: 320, height: 200 }}
        >
          {children}
        </RechartsPrimitive.ResponsiveContainer>
      </div>
    </ChartContext.Provider>
  )
}

const ChartTooltip = RechartsPrimitive.Tooltip

type TooltipItem = {
  name?: string | number
  dataKey?: unknown
  value?: unknown
  color?: string
}

/** Tooltip body: one row per series, labelled and coloured from the config; text in text tokens. */
function ChartTooltipContent({
  active,
  payload,
  label,
  formatter,
  labelFormatter,
  hideLabel = false,
  className,
}: {
  active?: boolean
  payload?: ReadonlyArray<TooltipItem>
  label?: unknown
  formatter?: (value: unknown, key: string) => React.ReactNode
  labelFormatter?: (label: unknown) => React.ReactNode
  hideLabel?: boolean
  className?: string
}) {
  const { config } = useChart()
  if (!active || !payload?.length) return null
  return (
    <div
      className={cn(
        "grid min-w-36 gap-1.5 rounded-lg border bg-popover px-2.5 py-1.5 text-xs text-popover-foreground shadow-md",
        className,
      )}
    >
      {!hideLabel && label != null && (
        <div className="font-medium">
          {labelFormatter ? labelFormatter(label) : String(label)}
        </div>
      )}
      {payload.map((item) => {
        const key = String(
          typeof item.dataKey === "string" && config[item.dataKey]
            ? item.dataKey
            : (item.name ?? ""),
        )
        const entry = config[key]
        return (
          <div key={key} className="flex items-center gap-2">
            <span
              aria-hidden
              className="size-2.5 shrink-0 rounded-[2px]"
              style={{ backgroundColor: entry?.color ?? item.color }}
            />
            <span className="text-muted-foreground">{entry?.label ?? key}</span>
            <span className="ml-auto font-medium tabular-nums">
              {formatter ? formatter(item.value, key) : String(item.value)}
            </span>
          </div>
        )
      })}
    </div>
  )
}

export { ChartContainer, ChartTooltip, ChartTooltipContent }
