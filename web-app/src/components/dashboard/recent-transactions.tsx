'use client'

import Link from 'next/link'
import { useTransactions } from '@/hooks/use-transactions'
import { TableSkeleton } from '@/components/shared/skeletons/table-skeleton'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { buttonVariants } from '@/components/ui/button'
import { formatCurrency } from '@/lib/format'
import { useFormatDate } from '@/hooks/use-date-format'
import { cn } from '@/lib/utils'

export function RecentTransactions() {
  const formatDate = useFormatDate()
  const { data, isLoading } = useTransactions({ sort_by: 'date', sort_order: 'desc', limit: 10 }, 0)

  if (isLoading) return <TableSkeleton rows={10} columns={4} />

  if (!data?.items.length) {
    return (
      <Card>
        <CardHeader><CardTitle>Recent Transactions</CardTitle></CardHeader>
        <CardContent className="flex flex-col items-center justify-center py-8 gap-3">
          <p className="text-sm text-muted-foreground">No transactions yet</p>
          <Link
            href="/upload"
            className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}
          >
            Upload CSV
          </Link>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Recent Transactions</CardTitle>
        <Link
          href="/transactions"
          className={cn(buttonVariants({ variant: 'ghost', size: 'sm' }))}
        >
          View All →
        </Link>
      </CardHeader>
      <CardContent>
        {data.items.map((item) => (
          <div key={item.id} className="flex justify-between items-center py-2 border-b last:border-0">
            <div className="flex-1 min-w-0 mr-4">
              <p className="font-medium truncate">{item.merchant}</p>
              <p className="text-xs text-muted-foreground">{formatDate(item.date)}</p>
            </div>
            <Badge variant="outline" className="mr-4 shrink-0">{item.category}</Badge>
            <span className="font-semibold shrink-0">{formatCurrency(item.amount)}</span>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
