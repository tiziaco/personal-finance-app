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

const isIncome = (amount: string) =>
  !amount.trim().startsWith("-") && /[1-9]/.test(amount)

/**
 * One transaction's amount, signed: "−€84.20", "+€3,200.00". A true minus and
 * no space; the rest (symbol side, separators) is the locale's. Intl writes a
 * hyphen-minus, so the absolute value is formatted and the sign prefixed. A
 * zero carries no sign.
 */
export function formatSignedAmount(amount: string, locale?: string) {
  const text = amount.trim()
  const negative = text.startsWith("-")
  const absolute = text.replace(/^[-+]/, "")
  const formatter = locale
    ? new Intl.NumberFormat(locale, { style: "currency", currency: "EUR" })
    : eur
  const body = formatter.format(absolute as unknown as number)
  if (!/[1-9]/.test(text)) return body
  return `${negative ? "−" : "+"}${body}`
}

/** Money in green; money out in the normal text colour. */
export const transactionAmountClass = (amount: string) =>
  isIncome(amount) ? "text-positive" : ""

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
