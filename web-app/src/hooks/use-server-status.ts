"use client"

import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@clerk/nextjs'
import { fetchHealthStatus } from '@/lib/api/health'
import type { HealthResponse } from '@/types/health'

export function useServerStatus() {
  const { getToken } = useAuth()

  const { data, isLoading, error } = useQuery<HealthResponse>({
    queryKey: ['health'],
    queryFn: async () => {
      const token = await getToken()
      return fetchHealthStatus(token)
    },
    refetchInterval: 30000, // Poll every 30 seconds (2 per minute, well under 20/minute rate limit)
    retry: false, // Don't retry to avoid hammering a failing server
  })

  return {
    status: data,
    isLoading,
    error,
  }
}
