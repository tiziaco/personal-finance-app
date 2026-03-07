"use client"

import { createContext, useContext, useState, useEffect, type ReactNode } from "react"

export type DateFormat = "de-DE" | "en-US" | "sv-SE"

const DATE_FORMAT_KEY = "pf_date_format"
const DEFAULT_FORMAT: DateFormat = "de-DE"

interface DateFormatContextValue {
  dateFormat: DateFormat
  setDateFormat: (format: DateFormat) => void
}

const DateFormatContext = createContext<DateFormatContextValue>({
  dateFormat: DEFAULT_FORMAT,
  setDateFormat: () => {},
})

export function DateFormatProvider({ children }: { children: ReactNode }) {
  const [dateFormat, setDateFormatState] = useState<DateFormat>(DEFAULT_FORMAT)

  // Read from localStorage after mount — avoids SSR hydration mismatch
  useEffect(() => {
    const stored = localStorage.getItem(DATE_FORMAT_KEY) as DateFormat | null
    if (stored && (stored === "de-DE" || stored === "en-US" || stored === "sv-SE")) {
      setDateFormatState(stored)
    }
  }, [])

  const setDateFormat = (format: DateFormat) => {
    setDateFormatState(format)
    localStorage.setItem(DATE_FORMAT_KEY, format)
  }

  return (
    <DateFormatContext.Provider value={{ dateFormat, setDateFormat }}>
      {children}
    </DateFormatContext.Provider>
  )
}

export function useDateFormat() {
  return useContext(DateFormatContext)
}
