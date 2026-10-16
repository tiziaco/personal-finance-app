import type { ReactNode } from "react"

import { Card, CardContent, CardHeader, CardTitle } from "@app/ui/card"

import { SectionError } from "@/components/dashboard/section-error"

/**
 * One titled section of a tab. Skeleton while nothing has loaded, an error with
 * a retry when nothing loaded and the request failed, and once data exists a
 * failed background refetch keeps showing it.
 */
export function Section<T>({
  title,
  query,
  what,
  skeleton,
  isEmpty,
  empty,
  children,
}: {
  title: string
  query: { data: T | undefined; isError: boolean; refetch: () => unknown }
  what: string
  skeleton: ReactNode
  isEmpty: (data: T) => boolean
  empty: string
  children: (data: T) => ReactNode
}) {
  const { data, isError, refetch } = query
  if (data === undefined && isError) {
    return <SectionError what={what} onRetry={() => void refetch()} />
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {data === undefined ? (
          skeleton
        ) : isEmpty(data) ? (
          <p className="text-sm text-muted-foreground">{empty}</p>
        ) : (
          children(data)
        )}
      </CardContent>
    </Card>
  )
}
