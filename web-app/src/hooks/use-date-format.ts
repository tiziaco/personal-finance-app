"use client"

import { useDateFormat } from "@/providers/date-format-provider"
import { formatDate } from "@/lib/format"

/**
 * Returns a locale-bound formatDate function using the user's date format preference.
 * Use this hook in client components instead of calling formatDate() directly.
 *
 * Example:
 *   const formatDateLocalized = useFormatDate()
 *   formatDateLocalized("2026-02-27") // → "27.02.2026" (default) or user's chosen format
 */
export function useFormatDate() {
  const { dateFormat } = useDateFormat()
  return (value: string) => formatDate(value, dateFormat)
}
