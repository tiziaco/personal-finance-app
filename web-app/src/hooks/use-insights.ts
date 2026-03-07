'use client'

import { useAuth } from '@clerk/nextjs'
import { useQuery } from '@tanstack/react-query'
import { fetchInsights } from '@/lib/api/insights'
import type { InsightsResponse } from '@/types/insights'

export function useInsights() {
  const { getToken } = useAuth()

  return useQuery<InsightsResponse>({
    queryKey: ['insights'],
    queryFn: async () => {
      const token = await getToken()
      return fetchInsights(token)
    },
    staleTime: 10 * 60 * 1000,    // 10 min — insights are expensive (30s generation time)
    gcTime: 30 * 60 * 1000,       // 30 min — keep in cache while navigating away
  })
}
