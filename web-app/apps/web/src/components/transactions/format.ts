import { formatDay, parseIsoDay } from "@app/core/lib/dates"

const eur = new Intl.NumberFormat(undefined, {
  style: "currency",
  currency: "EUR",
})

/**
 * EUR for display. Intl formats a decimal string exactly (no float rounding)
 * in engines that support string input; the cast is only for the DOM lib's types.
 */
export const formatAmount = (amount: string) =>
  eur.format(amount as unknown as number)

export const isExpense = (amount: string) =>
  amount.trim().startsWith("-") && /[1-9]/.test(amount)

/** Money out red, money in green. */
export const amountClass = (amount: string) =>
  isExpense(amount)
    ? "text-destructive"
    : "text-emerald-600 dark:text-emerald-400"

/** ISO YYYY-MM-DD → "3 Mar 2026", read as a local calendar date; "" if not a day. */
export function formatDate(iso: string) {
  const day = parseIsoDay(iso)
  return day ? formatDay(day) : ""
}

export const LOW_CONFIDENCE = 0.7
export const isLowConfidence = (confidence: number) =>
  confidence < LOW_CONFIDENCE
