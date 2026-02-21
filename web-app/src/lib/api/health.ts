import type { HealthResponse } from '@/types/health'

export async function fetchHealthStatus(token: string | null): Promise<HealthResponse> {
  const url = `${process.env.NEXT_PUBLIC_API_URL}/ready`
  
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  }
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  
  const response = await fetch(url, {
    method: 'GET',
    headers,
    cache: 'no-store',
  })
  
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`)
  }
  
  return response.json()
}
