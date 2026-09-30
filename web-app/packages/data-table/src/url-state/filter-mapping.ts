import {
  usesFrom,
  usesTo,
  type DateFilterMode,
  type DateFilterValue,
} from "./date-filter"

/**
 * Shape helpers for the to<Domain>Filters / from<Domain>Filters mappers in a
 * list's params file. Each list keeps its own keys and mapper bodies; only
 * this arithmetic is shared.
 */

export { compactQuery } from "../table/list-query"

/** First element of a single-select array, or null. A 0 id is a real selection. */
export const toSingle = <T>(a: T[]): T | null => (a.length > 0 ? a[0] : null)

/** Wraps a single id into an array, or []. A 0 id is a real selection. */
export const toMulti = <T>(v: T | null | undefined): T[] =>
  v != null ? [v] : []

/**
 * A date bound, only when the current mode uses that slot. Stops a leftover
 * value (date2 after switching range → gte) from filtering once its input is
 * hidden.
 */
export const dateVal = (d: DateFilterValue, which: 1 | 2): string | null => {
  const active = which === 1 ? usesFrom(d.mode) : usesTo(d.mode)
  const raw = which === 1 ? d.date1 : d.date2
  return active && raw ? raw : null
}

/** Infers a mode for old links that carry dates without a *_mode key. The explicit key wins. */
export const dateMode = (
  d1?: string | null,
  d2?: string | null,
): DateFilterMode | null => {
  if (d1 && d2) return "range"
  if (d1) return "gte"
  if (d2) return "lte"
  return null
}
