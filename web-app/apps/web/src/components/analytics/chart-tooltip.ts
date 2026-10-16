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
