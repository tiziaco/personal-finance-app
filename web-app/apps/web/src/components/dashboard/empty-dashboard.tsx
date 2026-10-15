import Link from "next/link"
import { buttonVariants } from "@app/ui/button"
import { Card, CardContent } from "@app/ui/card"

export function EmptyDashboard() {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
        <p className="font-medium">No transactions yet</p>
        <p className="text-sm text-muted-foreground">
          Add or import transactions to see your overview.
        </p>
        <Link href="/transactions" className={buttonVariants()}>
          Go to transactions
        </Link>
      </CardContent>
    </Card>
  )
}
