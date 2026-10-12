"use client"

import { useServerStatus } from "@app/api-client/use-server-status"
import { ServerStatusIndicator } from "@app/components/settings/server-status-indicator"
import { isDevelopment } from "@app/core/lib/env"

export function ServerHealthIndicator() {
  const { status, isLoading, error } = useServerStatus()
  return (
    <ServerStatusIndicator
      status={status}
      isLoading={isLoading}
      error={error}
      showDetail={isDevelopment}
    />
  )
}
