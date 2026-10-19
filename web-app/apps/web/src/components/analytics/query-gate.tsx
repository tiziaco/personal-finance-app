import type { ReactNode } from "react"

import { cn } from "@app/core/lib/utils"
import { Card, CardContent } from "@app/ui/card"

import { SectionError } from "@/components/dashboard/section-error"

/**
 * One request's loading, error and empty state. A skeleton while nothing has
 * loaded, one error card with a retry when nothing loaded and the request
 * failed, one empty card when the data holds nothing to show, and the
 * children otherwise. The empty card or the children are dimmed and aria-busy
 * while they come from the previous query's placeholder data. A failed background refetch keeps showing the data.
 */
export function QueryGate<T>({
  query,
  what,
  skeleton,
  isEmpty,
  empty,
  children,
}: {
  query: {
    data: T | undefined
    isError: boolean
    isPlaceholderData?: boolean
    refetch: () => unknown
  }
  what: string
  skeleton: ReactNode
  isEmpty: (data: T) => boolean
  empty: ReactNode | ((data: T) => ReactNode)
  children: (data: T) => ReactNode
}) {
  const { data, isError, isPlaceholderData, refetch } = query
  if (data === undefined) {
    return isError ? (
      <SectionError what={what} onRetry={() => void refetch()} />
    ) : (
      <>{skeleton}</>
    )
  }
  let content: ReactNode
  if (isEmpty(data)) {
    const node = typeof empty === "function" ? empty(data) : empty
    content = (
      <Card>
        <CardContent>
          {typeof node === "string" ? (
            <p className="text-sm text-muted-foreground">{node}</p>
          ) : (
            <div className="text-sm text-muted-foreground">{node}</div>
          )}
        </CardContent>
      </Card>
    )
  } else {
    content = children(data)
  }
  // Mirrors the tabs' own `flex flex-col gap-6` column, so the sections keep
  // their spacing whether or not this wrapper is there.
  return (
    <div
      aria-busy={isPlaceholderData === true}
      className={cn(
        "flex flex-col gap-6",
        isPlaceholderData && "opacity-60 transition-opacity",
      )}
    >
      {content}
    </div>
  )
}
