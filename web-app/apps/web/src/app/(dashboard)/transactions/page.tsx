import { TransactionsTable } from "@/components/transactions/transactions-table"

export default function TransactionsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Transactions</h1>
      <TransactionsTable />
    </div>
  )
}
