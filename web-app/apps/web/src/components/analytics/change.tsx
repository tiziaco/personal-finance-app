import type { ReactNode } from "react"

import { changeTone, formatPct, type Tone } from "./format"

/** Text colour for a tone; shared so other tone-bearing text matches a Change. */
export const TONE_CLASS: Record<Tone, string> = {
  good: "text-positive",
  bad: "text-negative",
  neutral: "text-muted-foreground",
}

/** Fill for a chart shape in a tone; mirrors TONE_CLASS, since a fill needs a fill class. */
export const TONE_FILL: Record<Tone, string> = {
  good: "fill-positive",
  bad: "fill-negative",
  neutral: "fill-muted-foreground",
}

/** A savings rate in words, bad when spending beat income; a dash when there is none. */
export function SavingsHeadline({ pct }: { pct: number | null }) {
  if (pct === null) return <span>—</span>
  // A rate that displays as 0.0% reads as kept, neutral — never "spent 0.0% more".
  const zero = formatPct(pct) === formatPct(0)
  const tone = zero ? "neutral" : changeTone(pct, "income")
  return (
    <span data-tone={tone} className={TONE_CLASS[tone]}>
      {zero || pct >= 0
        ? `Kept ${formatPct(pct)} of income`
        : `Spent ${formatPct(Math.abs(pct))} more than income`}
    </span>
  )
}

/** A percent change as an arrow and words, coloured good or bad, never by direction alone. */
export function Change({
  pct,
  kind,
  up,
  down,
  empty = "—",
}: {
  pct: number | null
  kind: "spend" | "income"
  up: ReactNode
  down: ReactNode
  empty?: string
}) {
  const tone = changeTone(pct, kind)
  return (
    <span data-tone={tone} className={TONE_CLASS[tone]}>
      {pct === null ? (
        empty
      ) : pct === 0 ? (
        "no change"
      ) : (
        <>
          <span aria-hidden>{pct > 0 ? "▲" : "▼"}</span>{" "}
          {formatPct(Math.abs(pct))} {pct > 0 ? up : down}
        </>
      )}
    </span>
  )
}
