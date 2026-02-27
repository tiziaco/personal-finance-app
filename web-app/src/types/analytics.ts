export interface AnalyticsResponse {
  /** Backend types as Dict[str, Any]; narrowed in Phase 2/4 */
  data: Record<string, unknown>
  /** ISO 8601 datetime string */
  generated_at: string
}

export interface DashboardResponse {
  spending: Record<string, unknown>
  categories: Record<string, unknown>
  recurring: Record<string, unknown>
  trends: Record<string, unknown>
  /** ISO 8601 datetime string */
  generated_at: string
}

export interface AnalyticsFilters {
  /** YYYY-MM-DD format */
  date_from?: string
  /** YYYY-MM-DD format */
  date_to?: string
}
