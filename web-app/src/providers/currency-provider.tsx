"use client"

import { createContext, useContext, useState, useEffect, type ReactNode } from "react"

export type Currency = "EUR" | "USD" | "GBP" | "CHF"

const CURRENCY_KEY = "pf_currency"
const DEFAULT_CURRENCY: Currency = "EUR"

const LOCALE_MAP: Record<Currency, string> = {
  EUR: "de-DE",
  USD: "en-US",
  GBP: "en-GB",
  CHF: "de-CH",
}

interface CurrencyContextValue {
  currency: Currency
  setCurrency: (c: Currency) => void
  formatAmount: (value: number | string) => string
}

const CurrencyContext = createContext<CurrencyContextValue>({
  currency: DEFAULT_CURRENCY,
  setCurrency: () => {},
  formatAmount: (v) => String(v),
})

export function CurrencyProvider({ children }: { children: ReactNode }) {
  const [currency, setCurrencyState] = useState<Currency>(DEFAULT_CURRENCY)

  // Read from localStorage after mount — avoids SSR hydration mismatch (same pattern as DateFormatProvider)
  useEffect(() => {
    const stored = localStorage.getItem(CURRENCY_KEY) as Currency | null
    if (stored && (["EUR", "USD", "GBP", "CHF"] as Currency[]).includes(stored)) {
      setCurrencyState(stored)
    }
  }, [])

  const setCurrency = (c: Currency) => {
    setCurrencyState(c)
    localStorage.setItem(CURRENCY_KEY, c)
  }

  const formatAmount = (value: number | string): string => {
    const num = typeof value === "string" ? parseFloat(value) : value
    if (isNaN(num)) return "—"
    return new Intl.NumberFormat(LOCALE_MAP[currency], {
      style: "currency",
      currency,
    }).format(num)
  }

  return (
    <CurrencyContext.Provider value={{ currency, setCurrency, formatAmount }}>
      {children}
    </CurrencyContext.Provider>
  )
}

export function useCurrency() {
  return useContext(CurrencyContext)
}
