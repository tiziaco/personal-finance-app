/**
 * Format a financial amount using EUR/de-DE locale by default.
 * Accepts string amounts (Python Decimal serialized as JSON string) or numbers.
 * Parses at render time — never store the parsed float value.
 *
 * STATE.md decision: EUR (de-DE locale) is the default currency format throughout the app.
 */
export function formatCurrency(
  value: number | string,
  currency = 'EUR',
  locale = 'de-DE'
): string {
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(num)) return '—'
  return new Intl.NumberFormat(locale, { style: 'currency', currency }).format(num)
}

/**
 * Format an ISO 8601 date string for display using de-DE locale by default.
 * Example: "2026-02-27" → "27.02.2026"
 */
export function formatDate(
  value: string,
  locale = 'de-DE',
  options: Intl.DateTimeFormatOptions = { day: '2-digit', month: '2-digit', year: 'numeric' }
): string {
  if (!value) return '—'
  const date = new Date(value)
  if (isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(locale, options).format(date)
}

/**
 * Format a percentage value with 1 decimal place.
 * Example: 0.1234 → "12.3%" or pass a pre-scaled value like 45.6 → "45.6%"
 */
export function formatPercent(value: number, alreadyScaled = true): string {
  if (isNaN(value)) return '—'
  const scaled = alreadyScaled ? value : value * 100
  return `${scaled.toFixed(1)}%`
}
