import type { CategorySliceResponse } from "@app/api-client/types"
import { formatAmount } from "@/components/transactions/format"

export type CategorySlice = {
  key: string
  name: string
  amount: number
  display: string
  share: number
  fill: string
}

/** The server's top five plus Other, ready to draw: numbers for geometry, exact text for labels. */
export function toCategorySlices(
  slices: CategorySliceResponse[],
  label: (slug: string) => string,
): CategorySlice[] {
  return slices.map((slice, i) => {
    const category = slice.category
    return {
      key: category ?? "other",
      name: category === null ? "Other" : label(category),
      amount: Number(slice.amount),
      display: formatAmount(slice.amount),
      share: slice.share_pct,
      fill: category === null ? "var(--chart-6)" : `var(--chart-${i + 1})`,
    }
  })
}
