// A calendar day travels as an ISO "YYYY-MM-DD" string and is read as a local
// date. Never toISOString, which is UTC and can shift the day.

const ISO_DAY = /^(\d{4})-(\d{2})-(\d{2})$/

const pad = (n: number) => String(n).padStart(2, "0")

/** A Date's local calendar day as "YYYY-MM-DD". */
export const toIsoDay = (d: Date) =>
  `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`

/** Today, local. */
export const todayIsoDay = () => toIsoDay(new Date())

/**
 * "YYYY-MM-DD" → a local Date, or undefined when it is not a real day
 * ("2026-0", "2026-02-30"). Input from a URL reaches this, so it never throws.
 */
export function parseIsoDay(iso: string): Date | undefined {
  const match = ISO_DAY.exec(iso)
  if (!match) return undefined
  const [y, m, d] = match.slice(1).map(Number)
  const date = new Date(y, m - 1, d)
  return date.getFullYear() === y &&
    date.getMonth() === m - 1 &&
    date.getDate() === d
    ? date
    : undefined
}

export const isIsoDay = (iso: string) => parseIsoDay(iso) !== undefined

const dayFormat = new Intl.DateTimeFormat(undefined, {
  day: "numeric",
  month: "short",
  year: "numeric",
})

/** A Date as "3 Mar 2026", in the user's locale. */
export const formatDay = (d: Date) => dayFormat.format(d)
