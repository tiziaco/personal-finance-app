export interface AnalyticsResponse {
  /** Backend types as Dict[str, Any]; narrowed in Phase 2/4 */
  data: Record<string, unknown>
  /** ISO 8601 datetime string */
  generated_at: string
}

// DashboardResponse.spending — from get_spending_summary()
export interface DashboardSpendingStat {
  month: string           // "2026-02" format
  total_expense: number
  total_income: number
  net: number
}

export interface DashboardSpending {
  overview: {
    stats: DashboardSpendingStat[]
    income_vs_expenses: Record<string, unknown>[]
  }
  recent_trend: {
    last_3_months: DashboardSpendingStat[]
    burn_rate: Record<string, unknown>[]
  }
  date_range: { start: string | null; end: string | null; total_days: number }
}

// DashboardResponse.categories — from get_category_insights()
export interface DashboardCategoryItem {
  category: string
  total_amount: number
  transaction_count: number
  percentage: number
}

export interface DashboardCategories {
  top_categories: DashboardCategoryItem[]
  frequency_vs_impact: Record<string, unknown>[]
  confidence_weighted: Record<string, unknown>[]
  category_trends: {
    top_growing: Record<string, unknown>[]
    top_declining: Record<string, unknown>[]
  }
}

// DashboardResponse.recurring — from get_recurring_insights()
export interface DashboardRecurring {
  recurring_summary: Record<string, unknown>[]
  monthly_recurring_costs: Array<{ merchant: string; estimated_monthly_cost: number }>
  recurring_by_category: Record<string, unknown>[]
  hidden_subscriptions: Record<string, unknown>[]
  insights: {
    total_recurring_percentage: number
    total_hidden_subscriptions: number
    top_recurring_merchant: string | null
  }
}

// DashboardResponse.trends — from get_trend_insights()
export interface DashboardTrendPoint {
  month: string           // "2026-02" format
  total_expense: number
  total_income: number
  expense_mom_growth: number | null
}

export interface DashboardTrends {
  monthly_trend: DashboardTrendPoint[]
  year_comparison: Record<string, unknown>[]
  burn_rate: Record<string, unknown>[]
  top_growing: Record<string, unknown>[]
  top_declining: Record<string, unknown>[]
  insights: { latest_mom_growth: number | null }
}

export interface DashboardResponse {
  spending: DashboardSpending
  categories: DashboardCategories
  recurring: DashboardRecurring
  trends: DashboardTrends
  /** ISO 8601 datetime string */
  generated_at: string
}

export interface AnalyticsFilters {
  /** YYYY-MM-DD format */
  date_from?: string
  /** YYYY-MM-DD format */
  date_to?: string
}
