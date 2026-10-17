import type { ReactNode } from "react"

import { Card, CardContent } from "@app/ui/card"

import { SectionError } from "@/components/dashboard/section-error"

/**
 * One request's loading, error and empty state. A skeleton while nothing has
 * loaded, one error card with a retry when nothing loaded and the request
 * failed, one empty card when the data holds nothing to show, and the
 * children otherwise. A failed background refetch keeps showing the data.
 */
export function QueryGate<T>({
  query,
  what,
  skeleton,
  isEmpty,
  empty,
  children,
}: {
  query: { data: T | undefined; isError: boolean; refetch: () => unknown }
  what: string
  skeleton: ReactNode
  isEmpty: (data: T) => boolean
  empty: ReactNode | ((data: T) => ReactNode)
  children: (data: T) => ReactNode
}) {
  const { data, isError, refetch } = query
  if (data === undefined) {
    return isError ? (
      <SectionError what={what} onRetry={() => void refetch()} />
    ) : (
      <>{skeleton}</>
    )
  }
  if (isEmpty(data)) {
    const node = typeof empty === "function" ? empty(data) : empty
    return (
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
  }
  return <>{children(data)}</>
}
