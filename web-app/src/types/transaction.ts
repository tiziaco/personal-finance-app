export type CategoryEnum =
  | 'Income'
  | 'Transportation'
  | 'Salary'
  | 'Household & Utilities'
  | 'Tax & Fines'
  | 'Miscellaneous'
  | 'Food & Groceries'
  | 'Food Delivery'
  | 'ATM'
  | 'Insurances'
  | 'Shopping'
  | 'Bars & Restaurants'
  | 'Education'
  | 'Family & Friends'
  | 'Donations & Charity'
  | 'Healthcare & Drug Stores'
  | 'Leisure & Entertainment'
  | 'Media & Electronics'
  | 'Savings & Investments'
  | 'Travel & Holidays'

export const CATEGORY_OPTIONS: CategoryEnum[] = [
  'Income',
  'Transportation',
  'Salary',
  'Household & Utilities',
  'Tax & Fines',
  'Miscellaneous',
  'Food & Groceries',
  'Food Delivery',
  'ATM',
  'Insurances',
  'Shopping',
  'Bars & Restaurants',
  'Education',
  'Family & Friends',
  'Donations & Charity',
  'Healthcare & Drug Stores',
  'Leisure & Entertainment',
  'Media & Electronics',
  'Savings & Investments',
  'Travel & Holidays',
]

export interface TransactionResponse {
  id: number
  user_id: string
  /** ISO 8601 date string — do NOT use Date type */
  date: string
  merchant: string
  /** CRITICAL: Decimal serializes as string in JSON — must NOT be number */
  amount: string
  description: string | null
  original_category: string | null
  category: CategoryEnum
  confidence_score: number
  is_recurring: boolean
  /** ISO 8601 datetime string */
  created_at: string
  /** ISO 8601 datetime string */
  updated_at: string
}

export interface TransactionListResponse {
  items: TransactionResponse[]
  total: number
  offset: number
  limit: number
}

export interface TransactionFilters {
  date_from?: string
  date_to?: string
  category?: CategoryEnum
  merchant?: string
  amount_min?: string
  amount_max?: string
  is_recurring?: boolean
  sort_by?: 'date' | 'amount' | 'merchant'
  sort_order?: 'asc' | 'desc'
  offset?: number
  limit?: number
}

export interface BatchUpdateItem {
  id: number
  category?: CategoryEnum
}

/** Maximum 100 items per request */
export interface BatchUpdateRequest {
  items: BatchUpdateItem[]
}

export interface BatchUpdateResponse {
  updated: number
}

/** Maximum 100 ids per request */
export interface BatchDeleteRequest {
  ids: number[]
}

export interface BatchDeleteResponse {
  deleted: number
}

export interface CreateTransactionRequest {
  /** ISO 8601 date string, e.g. '2024-01-15' */
  date: string
  merchant: string
  /** Decimal as string — e.g. '-42.50' for expense, '1200.00' for income */
  amount: string
  category: CategoryEnum
  description?: string
  is_recurring?: boolean
}

export interface TransactionUpdateRequest {
  date?: string
  merchant?: string
  /** CRITICAL: Decimal as string — e.g. '-42.50' for expense, '1200.00' for income; must NOT be number */
  amount?: string
  /** null not supported for clearing — backend uses exclude_none=True */
  description?: string
  category?: CategoryEnum
  is_recurring?: boolean
}
