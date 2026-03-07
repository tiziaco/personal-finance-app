// Note: There is NO /categories API endpoint.
// Categories are a static TypeScript enum — this hook returns them without any API call.

import { CATEGORY_OPTIONS } from '@/types/transaction'
import type { CategoryEnum } from '@/types/transaction'

export function useCategories(): {
  data: CategoryEnum[]
  isLoading: false
  isError: false
} {
  return { data: CATEGORY_OPTIONS, isLoading: false, isError: false }
}
