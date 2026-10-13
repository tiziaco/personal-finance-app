const AMOUNT = /^([+-]?)(\d{1,10})(?:[.,](\d{1,2}))?$/

/**
 * A typed amount as the API's decimal string: a comma or a dot for the
 * decimals, at most two places and ten integer digits (NUMERIC(12,2)).
 * Never parsed to a float. Returns null when it is not an amount.
 */
export function parseAmount(input: string): string | null {
  const match = AMOUNT.exec(input.trim())
  if (!match) return null
  const [, sign, whole, cents = ""] = match
  return `${sign === "-" ? "-" : ""}${whole}.${cents.padEnd(2, "0")}`
}
