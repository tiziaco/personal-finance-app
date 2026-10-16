import type { ReactNode } from "react"

import { Card, CardContent, CardHeader, CardTitle } from "@app/ui/card"

/** One titled card of a tab. Loading, error and empty belong to `QueryGate`. */
export function Section({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}
