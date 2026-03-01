import Link from 'next/link'
import { Upload } from 'lucide-react'
import { buttonVariants } from '@/components/ui/button'

export function TransactionsEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-24 gap-6 text-center">
      <Upload className="h-16 w-16 text-muted-foreground/40" />
      <div className="space-y-2">
        <h3 className="text-lg font-semibold text-foreground">No transactions yet</h3>
        <p className="text-sm text-muted-foreground max-w-sm">
          Upload a CSV file to import your bank transactions and get started.
        </p>
      </div>
      <Link href="/upload" className={buttonVariants({ variant: 'default' })}>
        Upload a CSV file to get started
      </Link>
    </div>
  )
}
