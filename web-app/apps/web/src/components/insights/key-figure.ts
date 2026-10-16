import type { KeyFigureResponse } from "@app/api-client/types"
import { formatAmount } from "@/components/transactions/format"

function formatPercent(value: string) {
  const n = Number(value)
  const digits = Math.abs(n) >= 10 ? 0 : 1
  const sign = n < 0 ? "−" : "+"
  return `${sign}${Math.abs(n).toFixed(digits)}%`
}

/** A card's chip text: the figure in its kind's format, then the qualifier. */
export function formatKeyFigure(kf: KeyFigureResponse) {
  const figure =
    kf.kind === "amount"
      ? formatAmount(kf.value)
      : kf.kind === "percent"
        ? formatPercent(kf.value)
        : kf.value
  return kf.qualifier ? `${figure} ${kf.qualifier}` : figure
}
