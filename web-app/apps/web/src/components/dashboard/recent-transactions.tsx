"use client"

import Link from "next/link"
import { useListTransactions } from "@app/api-client/endpoints/transactions"
import type { TransactionResponse } from "@app/api-client/types"
import { buttonVariants } from "@app/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@app/ui/card"
import { cn } from "@app/core/lib/utils"
import {
  transactionAmountClass,
  formatSignedAmount,
  formatDate,
} from "@/components/transactions/format"
import { CategoryTile } from "@/components/transactions/category-icon"
import { useCategories } from "@/components/transactions/use-categories"
import { RecentSkeleton } from "./dashboard-skeleton"
import { SectionError } from "./section-error"

const RECENT = { limit: 10 } as const

function Amount({ value }: { value: string }) {
  return (
    <span className={cn("tabular-nums", transactionAmountClass(value))}>
      {formatSignedAmount(value)}
    </span>
  )
}

/** The ten newest transactions: a table from md up, a list on a phone. */
export function RecentTransactions() {
  const query = useListTransactions(RECENT, {
    query: { meta: { silentError: true } },
  })
  const { label } = useCategories()

  // A failed background refetch keeps its data: the error replaces only an empty list.
  if (query.isError && !query.data) {
    return (
      <SectionError
        what="recent transactions"
        onRetry={() => void query.refetch()}
      />
    )
  }

  const items: TransactionResponse[] = query.data?.items ?? []
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle>Recent transactions</CardTitle>
        <Link
          href="/transactions"
          className={buttonVariants({ variant: "ghost", size: "sm" })}
        >
          View all
        </Link>
      </CardHeader>
      <CardContent>
        {query.isPending ? (
          <RecentSkeleton />
        ) : (
          <>
            <table className="hidden w-full text-sm md:table">
              <tbody>
                {items.map((t) => (
                  <tr key={t.id} className="border-b last:border-0">
                    <td className="py-2 pr-3 font-medium">
                      <div className="flex items-center gap-3">
                        <CategoryTile slug={t.category} />
                        <span className="min-w-0 truncate">{t.merchant}</span>
                      </div>
                    </td>
                    <td className="py-2 pr-3 text-muted-foreground">
                      {formatDate(t.date)}
                    </td>
                    <td className="py-2 pr-3 text-muted-foreground">
                      {label(t.category)}
                    </td>
                    <td className="py-2 text-right">
                      <Amount value={t.amount} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <ul className="space-y-3 md:hidden">
              {items.map((t) => (
                <li key={t.id} className="flex items-center gap-3">
                  <CategoryTile slug={t.category} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">{t.merchant}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatDate(t.date)} · {label(t.category)}
                    </p>
                  </div>
                  <Amount value={t.amount} />
                </li>
              ))}
            </ul>
          </>
        )}
      </CardContent>
    </Card>
  )
}
