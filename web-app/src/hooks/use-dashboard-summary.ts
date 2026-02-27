'use client'

import { useAuth } from '@clerk/nextjs'
import { useQuery } from '@tanstack/react-query'
import { fetchDashboard } from '@/lib/api/analytics'
import type { DashboardResponse, AnalyticsFilters } from '@/types/analytics'

export function useDashboardSummary(filters: AnalyticsFilters = {}) {
  const { getToken } = useAuth()

  return useQuery<DashboardResponse>({
    queryKey: ['dashboard', filters],
    queryFn: async () => {
      const token = await getToken()
      return fetchDashboard(token, filters)
    },
    staleTime: 2 * 60 * 1000,   // 2 minutes — dashboard data is relatively stable
  })
}
