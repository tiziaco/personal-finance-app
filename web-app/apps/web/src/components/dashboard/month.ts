/** "2026-09" → "September 2026" (long) or "Sep" (short), in the user's locale; anything else unchanged. */
export function formatMonth(key: string, month: "long" | "short" = "long") {
  const match = /^(\d{4})-(\d{2})$/.exec(key)
  if (!match) return key
  const date = new Date(Number(match[1]), Number(match[2]) - 1, 1)
  return new Intl.DateTimeFormat(undefined, {
    month,
    year: month === "long" ? "numeric" : undefined,
  }).format(date)
}
