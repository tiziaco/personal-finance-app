"use client"

import { useMemo } from "react"
import { useListTransactionCategories } from "@app/api-client/endpoints/transactions"

/**
 * The category list from the server, fetched once per session. `label` falls
 * back to the slug until it arrives, and for a slug the list no longer has.
 */
export function useCategories() {
  const { data } = useListTransactionCategories({
    query: { staleTime: Infinity },
  })
  return useMemo(() => {
    const categories = data ?? []
    const labels = new Map<string, string>(
      categories.map((c) => [c.value, c.label]),
    )
    return { categories, label: (slug: string) => labels.get(slug) ?? slug }
  }, [data])
}
