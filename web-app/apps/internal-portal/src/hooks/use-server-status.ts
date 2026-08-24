"use client"

import { useQuery } from "@tanstack/react-query"
import { useAuth } from "@clerk/nextjs"
import { fetchHealthStatus } from "../lib/api/health"
import type { HealthResponse } from "@rilevio/types"

export function useServerStatus() {
  const { getToken } = useAuth()

  const { data, isLoading, error } = useQuery<HealthResponse>({
    queryKey: ["health"],
    queryFn: async () => {
      const token = await getToken()
      return fetchHealthStatus(token)
    },
    refetchInterval: 30000,
    retry: false,
  })

  return { status: data, isLoading, error }
}
