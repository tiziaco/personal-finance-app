import type { ReactNode } from "react"
import { formatMonth } from "@/components/dashboard/month"
import type { MonthPoint } from "./month-points"

/**
 * Shared recharts props for the analytics charts, spread onto the component
 * (`<CartesianGrid {...GRID} />`).
 */
export const MARGIN = { left: 4, right: 8, top: 8 }

export const GRID = { vertical: false, strokeDasharray: "3 3" } as const

export const X_AXIS = {
  dataKey: "label",
  tickLine: false,
  axisLine: false,
  tickMargin: 8,
} as const

const compact = new Intl.NumberFormat(undefined, {
  notation: "compact",
  maximumFractionDigits: 1,
})

export const MONEY_Y_AXIS = {
  tickLine: false,
  axisLine: false,
  width: 48,
  tickFormatter: (v: number) => compact.format(v),
} as const

export const PCT_Y_AXIS = {
  tickLine: false,
  axisLine: false,
  width: 48,
  tickFormatter: (v: number) => `${v}%`,
} as const

/**
 * Shared Tooltip props for the analytics charts.
 *
 * - The hover cursor takes a theme token; recharts' default is a fixed light
 *   grey, a bright band in dark mode.
 * - `filterNull: false` keeps a null value in the payload, so a month with
 *   no figure still gets a tooltip reading "—" (or "no data yet") instead of
 *   none at all.
 */
export const BAR_TOOLTIP = {
  cursor: { fill: "var(--muted)" },
  filterNull: false,
} as const

export const LINE_TOOLTIP = {
  cursor: { stroke: "var(--border)" },
  filterNull: false,
} as const

/** A partial month is drawn lighter. */
export const partialOpacity = (p: { partial: boolean }): 0.4 | 1 =>
  p.partial ? 0.4 : 1

/** "Oct 2026", with " (so far)" or " (partial)" for a partial month. */
export function monthTooltipLabel(
  p: MonthPoint | undefined,
): string | undefined {
  if (!p) return undefined
  return `${formatMonth(p.month)}${p.partialLabel ? ` (${p.partialLabel})` : ""}`
}

/** The point under the cursor, from a recharts tooltip payload. */
export function pointOf<T>(
  payload?: readonly { payload?: unknown }[],
): T | undefined {
  return payload?.[0]?.payload as T | undefined
}

/** The box of a hand-built tooltip, in the look of the primitive's own. */
export function TooltipBox({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-lg border bg-popover px-2.5 py-1.5 text-xs text-popover-foreground shadow-md">
      {children}
    </div>
  )
}
