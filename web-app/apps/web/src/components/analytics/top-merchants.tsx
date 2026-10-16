"use client"

import { useGetMerchantBreakdown } from "@app/api-client/endpoints/analytics"
import { Skeleton } from "@app/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@app/ui/table"

import { formatAmount } from "@/components/transactions/format"

import { formatPct } from "./format"
import { ANALYTICS_QUERY } from "./query"
import { Section } from "./section"

/** The merchants you spent most at; loads and fails on its own. */
export function TopMerchants({ months }: { months: number }) {
  const query = useGetMerchantBreakdown({ months, top_n: 10 }, ANALYTICS_QUERY)
  return (
    <Section
      title="Top merchants"
      query={query}
      what="your top merchants"
      skeleton={<Skeleton className="h-40 w-full" />}
      isEmpty={(data) => data.top_by_spend.length === 0}
      empty="No merchants in this period."
    >
      {(data) => (
        <>
          <Table className="hidden sm:table">
            <TableHeader>
              <TableRow>
                <TableHead>Merchant</TableHead>
                <TableHead className="text-right">Purchases</TableHead>
                <TableHead className="text-right">Total</TableHead>
                <TableHead className="text-right">Share</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.top_by_spend.map((m) => (
                <TableRow key={m.merchant}>
                  <TableCell>{m.merchant}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {m.count}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatAmount(m.total)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatPct(m.share_pct)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <ul className="flex flex-col gap-3 sm:hidden">
            {data.top_by_spend.map((m) => (
              <li key={m.merchant} className="flex justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate font-medium">{m.merchant}</p>
                  <p className="text-xs text-muted-foreground">
                    {m.count} purchases · {formatPct(m.share_pct)}
                  </p>
                </div>
                <span className="tabular-nums">{formatAmount(m.total)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </Section>
  )
}
