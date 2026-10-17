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

/**
 * A percent with a sign and a true minus ("+12%", "−5%"). `adaptive` keeps one
 * decimal below 10 ("+9.5%") and none from there up; `whole` always rounds to a
 * whole percent. A zero reads "+0%" unless `unsignedZero` drops the sign.
 */
export function formatPercent(
  value: number,
  {
    decimals,
    unsignedZero = false,
  }: { decimals: "adaptive" | "whole"; unsignedZero?: boolean },
) {
  if (decimals === "whole") {
    const rounded = Math.round(value)
    const sign = rounded > 0 ? "+" : rounded < 0 ? "−" : unsignedZero ? "" : "+"
    return `${sign}${Math.abs(rounded)}%`
  }
  // Decide the decimals from the rounded value: 9.96 is "10", not "10.0".
  const digits = Math.round(Math.abs(value)) >= 10 ? 0 : 1
  const text = Math.abs(value).toFixed(digits)
  const negative = value < 0 && Number(text) !== 0
  const sign = negative ? "−" : unsignedZero && Number(text) === 0 ? "" : "+"
  return `${sign}${text}%`
}
