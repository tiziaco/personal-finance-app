import { changeTone, formatPct, type Tone } from "./format"

/** Text colour for a tone; shared so other tone-bearing text matches a Change. */
export const TONE_CLASS: Record<Tone, string> = {
  good: "text-emerald-600 dark:text-emerald-400",
  bad: "text-destructive",
  neutral: "text-muted-foreground",
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
  up: string
  down: string
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
