export const DATE_FILTER_MODES = ["gte", "lte", "range"] as const
export type DateFilterMode = (typeof DATE_FILTER_MODES)[number]

export interface DateFilterValue {
  mode: DateFilterMode | null
  /** ISO YYYY-MM-DD, "" when empty */
  date1: string
  date2: string
}

export const EMPTY_DATE_FILTER: DateFilterValue = {
  mode: null,
  date1: "",
  date2: "",
}

/** The mode shows the "from" input. */
export const usesFrom = (mode: DateFilterMode | null) =>
  mode === "gte" || mode === "range"
/** The mode shows the "to" input. */
export const usesTo = (mode: DateFilterMode | null) =>
  mode === "lte" || mode === "range"

/**
 * Chip label for a date filter, or null when it isn't filtering. Use it for
 * both the chip and the "is this active?" check so they can't disagree.
 * A one-sided range reads as the bound that's set, matching what the server
 * filters on.
 */
export function dateFilterLabel(
  prefix: string,
  { mode, date1, date2 }: DateFilterValue,
): string | null {
  const from = date1 ? `${prefix} ≥ ${date1}` : null
  const to = date2 ? `${prefix} ≤ ${date2}` : null
  if (mode === "gte") return from
  if (mode === "lte") return to
  if (mode === "range")
    return date1 && date2 ? `${prefix} ${date1} – ${date2}` : (from ?? to)
  return null
}

export const isDateFilterActive = (value: DateFilterValue): boolean =>
  dateFilterLabel("", value) !== null
