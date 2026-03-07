"use client"

import { useCurrency } from "@/providers/currency-provider"

/**
 * Returns a bound formatAmount function from CurrencyProvider.
 * Shadow-import pattern: drop-in replacement for formatCurrency from @/lib/format.
 * Usage: const formatCurrency = useFormatCurrency()
 */
export function useFormatCurrency() {
  const { formatAmount } = useCurrency()
  return formatAmount
}
