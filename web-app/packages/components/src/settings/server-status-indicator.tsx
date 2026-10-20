"use client"

import { cn } from "@app/core/lib/utils"
import {
  HoverCard,
  HoverCardTrigger,
  HoverCardContent,
} from "@app/ui/hover-card"
import { Badge } from "@app/ui/badge"

/** Structural mirror of @app/api-client's GetReadinessResponse. Declared here
    rather than imported: this package must not depend on the API client. */
interface ServerStatus {
  status?: string
  version?: string
  environment?: string
  timestamp?: string
  components?: {
    api?: string
    database?: { status?: string }
    agents?: { chatbot?: { ready?: boolean } }
  }
}

interface ServerStatusIndicatorProps {
  status?: ServerStatus
  isLoading: boolean
  error: unknown
  /** Show the hover-card breakdown. Hoisted from a module-load env read so
      the component renders both branches under test. */
  showDetail?: boolean
}

export function ServerStatusIndicator({
  status,
  isLoading,
  error,
  showDetail = false,
}: ServerStatusIndicatorProps) {
  if (isLoading) {
    return (
      <div className="flex items-center gap-2 px-3 py-2">
        <div className="size-2 rounded-full bg-muted-foreground/20 animate-pulse" />
        <span className="text-xs text-muted-foreground font-mono">
          Loading...
        </span>
      </div>
    )
  }

  // One reading drives both the colour and the ring, so they cannot disagree.
  const health = error || !status ? "down" : status.status
  const statusColor =
    health === "healthy"
      ? "bg-positive"
      : health === "degraded"
        ? "bg-(--warning-500)"
        : "bg-negative"

  const statusIndicator = (
    <div className="flex items-center gap-2 px-3 py-2 cursor-default">
      <div className="relative">
        <div
          className={cn("size-2 rounded-full transition-colors", statusColor)}
        />
        {health === "healthy" && (
          <div
            className={cn(
              "absolute inset-0 size-2 rounded-full animate-ping",
              statusColor,
              "opacity-75",
            )}
          />
        )}
      </div>
      <span className="text-xs text-muted-foreground font-mono">
        v{status?.version || "0.0.0"}
      </span>
    </div>
  )

  if (!showDetail) {
    return statusIndicator
  }

  return (
    <HoverCard>
      <HoverCardTrigger>{statusIndicator}</HoverCardTrigger>
      <HoverCardContent side="top" align="start" className="w-64">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold">Server status</span>
            <Badge
              variant="secondary"
              className="text-[10px] px-1.5 py-0 h-4 font-mono"
            >
              {status?.environment || "unknown"}
            </Badge>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">API</span>
              <div className="flex items-center gap-1.5">
                <div
                  className={cn(
                    "size-1.5 rounded-full",
                    status?.components?.api === "healthy"
                      ? "bg-positive"
                      : "bg-negative",
                  )}
                />
                <span className="text-xs capitalize">
                  {status?.components?.api || "unknown"}
                </span>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Database</span>
              <div className="flex items-center gap-1.5">
                <div
                  className={cn(
                    "size-1.5 rounded-full",
                    status?.components?.database?.status === "healthy"
                      ? "bg-positive"
                      : "bg-negative",
                  )}
                />
                <span className="text-xs capitalize">
                  {status?.components?.database?.status || "unknown"}
                </span>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">
                Chatbot Agent
              </span>
              <div className="flex items-center gap-1.5">
                <div
                  className={cn(
                    "size-1.5 rounded-full",
                    status?.components?.agents?.chatbot?.ready
                      ? "bg-positive"
                      : "bg-negative",
                  )}
                />
                <span className="text-xs">
                  {status?.components?.agents?.chatbot?.ready
                    ? "Ready"
                    : "Not ready"}
                </span>
              </div>
            </div>
          </div>
          {status?.timestamp && (
            <div className="pt-2 border-t">
              <span className="text-[10px] text-muted-foreground font-mono">
                Updated {new Date(status.timestamp).toLocaleTimeString()}
              </span>
            </div>
          )}
        </div>
      </HoverCardContent>
    </HoverCard>
  )
}
