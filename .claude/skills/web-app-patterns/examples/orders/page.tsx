// apps/web/src/app/(dashboard)/orders/page.tsx — a Server Component
import { OrdersTable } from "@/components/orders/orders-table"

function OrdersPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Orders</h1>
      <OrdersTable />
    </div>
  )
}

export default OrdersPage
