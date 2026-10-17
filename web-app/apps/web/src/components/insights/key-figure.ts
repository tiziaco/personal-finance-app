import type { KeyFigureResponse } from "@app/api-client/types"
import { formatAmount, formatPercent } from "@/components/transactions/format"

function formatKeyPercent(value: string) {
  const n = Number(value)
  return Number.isFinite(n) ? formatPercent(n, { decimals: "adaptive" }) : null
}

/** A card's chip text: the figure in its kind's format, then the qualifier. */
export function formatKeyFigure(kf: KeyFigureResponse) {
  const figure =
    kf.kind === "amount"
      ? formatAmount(kf.value)
      : kf.kind === "percent"
        ? formatKeyPercent(kf.value)
        : kf.value
  return [figure, kf.qualifier].filter(Boolean).join(" ")
}
