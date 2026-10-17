import { ANALYTICS_STALE_TIME } from "@/components/dashboard/home-dashboard"

/** Query options every analytics request shares: cached for a while, errors shown by the section. */
export const ANALYTICS_QUERY = {
  query: { staleTime: ANALYTICS_STALE_TIME, meta: { silentError: true } },
} as const
