"use client"

import { useCallback, useMemo, useSyncExternalStore } from "react"
import type { VisibilityState } from "@tanstack/react-table"

const CHANGE_EVENT = "table-columns-change"
const NO_DEFAULTS: VisibilityState = {}

function subscribe(onChange: () => void) {
  window.addEventListener("storage", onChange)
  window.addEventListener(CHANGE_EVENT, onChange)
  return () => {
    window.removeEventListener("storage", onChange)
    window.removeEventListener(CHANGE_EVENT, onChange)
  }
}

/**
 * Column-visibility adapter backed by localStorage. Spread the result into a table:
 *   const visibility = useStoredColumnVisibility("products", DEFAULTS);
 *   <ClientDataTable {...visibility} />
 * `defaults` must be a stable reference (hoist it to a module constant).
 * The server render and first client render use the defaults, so hydration matches.
 * For per-user server persistence, keep the same shape and save in the setter
 * (debounced) instead of writing to localStorage.
 */
export function useStoredColumnVisibility(
  key: string,
  defaults: VisibilityState = NO_DEFAULTS,
) {
  const storageKey = `table-columns:${key}`

  const raw = useSyncExternalStore(
    subscribe,
    () => {
      try {
        return window.localStorage.getItem(storageKey)
      } catch {
        return null
      }
    },
    () => null,
  )

  const columnVisibility = useMemo<VisibilityState>(() => {
    if (!raw) return defaults
    try {
      return { ...defaults, ...(JSON.parse(raw) as VisibilityState) }
    } catch {
      return defaults
    }
  }, [raw, defaults])

  const onColumnVisibilityChange = useCallback(
    (next: VisibilityState) => {
      try {
        window.localStorage.setItem(storageKey, JSON.stringify(next))
      } catch {
        // storage full or blocked: the choice is not persisted
      }
      window.dispatchEvent(new Event(CHANGE_EVENT))
    },
    [storageKey],
  )

  return { columnVisibility, onColumnVisibilityChange }
}
