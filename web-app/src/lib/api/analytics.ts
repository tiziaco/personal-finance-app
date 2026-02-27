import type { AnalyticsResponse, DashboardResponse, AnalyticsFilters } from '@/types/analytics'
import { apiRequest } from './client'

function buildAnalyticsQuery(filters: object = {}): string {
  const params = new URLSearchParams()
  Object.entries(filters as Record<string, unknown>).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      params.set(key, String(value))
    }
  })
  const q = params.toString()
  return q ? `?${q}` : ''
}

export async function fetchDashboard(
  token: string | null,
  filters: AnalyticsFilters = {}
): Promise<DashboardResponse> {
  return apiRequest<DashboardResponse>(`/api/v1/analytics/dashboard${buildAnalyticsQuery(filters)}`, token)
}

export async function fetchSpendingAnalytics(
  token: string | null,
  filters: AnalyticsFilters = {}
): Promise<AnalyticsResponse> {
  return apiRequest<AnalyticsResponse>(`/api/v1/analytics/spending${buildAnalyticsQuery(filters)}`, token)
}

export async function fetchCategoriesAnalytics(
  token: string | null,
  filters: AnalyticsFilters & { top_n?: number } = {}
): Promise<AnalyticsResponse> {
  return apiRequest<AnalyticsResponse>(`/api/v1/analytics/categories${buildAnalyticsQuery(filters)}`, token)
}

export async function fetchMerchantsAnalytics(
  token: string | null,
  filters: AnalyticsFilters & { top_n?: number } = {}
): Promise<AnalyticsResponse> {
  return apiRequest<AnalyticsResponse>(`/api/v1/analytics/merchants${buildAnalyticsQuery(filters)}`, token)
}

export async function fetchRecurringAnalytics(
  token: string | null,
  filters: AnalyticsFilters = {}
): Promise<AnalyticsResponse> {
  return apiRequest<AnalyticsResponse>(`/api/v1/analytics/recurring${buildAnalyticsQuery(filters)}`, token)
}

export async function fetchBehaviorAnalytics(
  token: string | null,
  filters: AnalyticsFilters = {}
): Promise<AnalyticsResponse> {
  return apiRequest<AnalyticsResponse>(`/api/v1/analytics/behavior${buildAnalyticsQuery(filters)}`, token)
}

export async function fetchAnomaliesAnalytics(
  token: string | null,
  filters: AnalyticsFilters & { std_threshold?: number; rolling_window?: number } = {}
): Promise<AnalyticsResponse> {
  return apiRequest<AnalyticsResponse>(`/api/v1/analytics/anomalies${buildAnalyticsQuery(filters)}`, token)
}
