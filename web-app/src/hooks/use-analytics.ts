'use client'

import { useAuth } from '@clerk/nextjs'
import { useQuery } from '@tanstack/react-query'
import {
  fetchSpendingAnalytics,
  fetchCategoriesAnalytics,
  fetchMerchantsAnalytics,
  fetchRecurringAnalytics,
  fetchBehaviorAnalytics,
  fetchAnomaliesAnalytics,
} from '@/lib/api/analytics'
import type { AnalyticsResponse, AnalyticsFilters } from '@/types/analytics'

const ANALYTICS_STALE_TIME = 5 * 60 * 1000  // 5 minutes — analytics are expensive to compute

export function useSpendingAnalytics(filters: AnalyticsFilters = {}, enabled = true) {
  const { getToken } = useAuth()
  return useQuery<AnalyticsResponse>({
    queryKey: ['analytics', 'spending', filters],
    queryFn: async () => {
      const token = await getToken()
      return fetchSpendingAnalytics(token, filters)
    },
    enabled,
    staleTime: ANALYTICS_STALE_TIME,
  })
}

export function useCategoriesAnalytics(
  filters: AnalyticsFilters & { top_n?: number } = {},
  enabled = true
) {
  const { getToken } = useAuth()
  return useQuery<AnalyticsResponse>({
    queryKey: ['analytics', 'categories', filters],
    queryFn: async () => {
      const token = await getToken()
      return fetchCategoriesAnalytics(token, filters)
    },
    enabled,
    staleTime: ANALYTICS_STALE_TIME,
  })
}

export function useMerchantsAnalytics(
  filters: AnalyticsFilters & { top_n?: number } = {},
  enabled = true
) {
  const { getToken } = useAuth()
  return useQuery<AnalyticsResponse>({
    queryKey: ['analytics', 'merchants', filters],
    queryFn: async () => {
      const token = await getToken()
      return fetchMerchantsAnalytics(token, filters)
    },
    enabled,
    staleTime: ANALYTICS_STALE_TIME,
  })
}

export function useRecurringAnalytics(filters: AnalyticsFilters = {}, enabled = true) {
  const { getToken } = useAuth()
  return useQuery<AnalyticsResponse>({
    queryKey: ['analytics', 'recurring', filters],
    queryFn: async () => {
      const token = await getToken()
      return fetchRecurringAnalytics(token, filters)
    },
    enabled,
    staleTime: ANALYTICS_STALE_TIME,
  })
}

export function useBehaviorAnalytics(filters: AnalyticsFilters = {}, enabled = true) {
  const { getToken } = useAuth()
  return useQuery<AnalyticsResponse>({
    queryKey: ['analytics', 'behavior', filters],
    queryFn: async () => {
      const token = await getToken()
      return fetchBehaviorAnalytics(token, filters)
    },
    enabled,
    staleTime: ANALYTICS_STALE_TIME,
  })
}

export function useAnomaliesAnalytics(
  filters: AnalyticsFilters & { std_threshold?: number; rolling_window?: number } = {},
  enabled = true
) {
  const { getToken } = useAuth()
  return useQuery<AnalyticsResponse>({
    queryKey: ['analytics', 'anomalies', filters],
    queryFn: async () => {
      const token = await getToken()
      return fetchAnomaliesAnalytics(token, filters)
    },
    enabled,
    staleTime: ANALYTICS_STALE_TIME,
  })
}
