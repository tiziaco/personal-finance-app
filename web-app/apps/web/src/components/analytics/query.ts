import { keepPreviousData } from "@tanstack/react-query"

import { ANALYTICS_STALE_TIME } from "./stale-time"

/**
 * Query options every analytics request shares: cached for a while, errors
 * shown by the section, and the previous period's figures kept (dimmed by
 * QueryGate) while a new period loads.
 */
export const ANALYTICS_QUERY = {
  query: {
    staleTime: ANALYTICS_STALE_TIME,
    placeholderData: keepPreviousData,
    meta: { silentError: true },
  },
} as const
