export type SupplierRole = "primary" | "subcontractor"

export interface Supplier {
  id: string
  name: string
  vatNumber: string
  email: string
  role: SupplierRole
  createdAt: string
  updatedAt: string
}
