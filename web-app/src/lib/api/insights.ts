import type { InsightsResponse } from '@/types/insights'
import { apiRequest } from './client'

export async function fetchInsights(token: string | null): Promise<InsightsResponse> {
  return apiRequest<InsightsResponse>('/api/v1/insights', token)
}
