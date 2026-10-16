import type { KeyFigureResponse } from "@app/api-client/types"
import { formatAmount } from "@/components/transactions/format"

function formatPercent(value: string) {
  const n = Number(value)
  if (!Number.isFinite(n)) return null
  // Decide the decimals from the rounded value: 9.96 is "10", not "10.0".
  const digits = Math.round(Math.abs(n)) >= 10 ? 0 : 1
  const text = Math.abs(n).toFixed(digits)
  const sign = n < 0 && Number(text) !== 0 ? "−" : "+"
  return `${sign}${text}%`
}

/** A card's chip text: the figure in its kind's format, then the qualifier. */
export function formatKeyFigure(kf: KeyFigureResponse) {
  const figure =
    kf.kind === "amount"
      ? formatAmount(kf.value)
      : kf.kind === "percent"
        ? formatPercent(kf.value)
        : kf.value
  return [figure, kf.qualifier].filter(Boolean).join(" ")
}
