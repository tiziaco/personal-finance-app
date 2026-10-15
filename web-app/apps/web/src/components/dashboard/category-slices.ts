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
    const other = slice.category === null
    return {
      key: other ? "other" : slice.category!,
      name: other ? "Other" : label(slice.category!),
      amount: Number(slice.amount),
      display: formatAmount(slice.amount),
      share: slice.share_pct,
      fill: other ? "var(--chart-6)" : `var(--chart-${i + 1})`,
    }
  })
}
