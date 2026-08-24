export type DocumentStatus = "pending" | "uploaded" | "approved" | "rejected" | "expired"
export type DocumentType = "safety" | "administrative" | "procurement"

export interface Document {
  id: string
  supplierId: string
  orderId: string
  name: string
  type: DocumentType
  status: DocumentStatus
  fileUrl?: string
  expiresAt?: string
  comment?: string
  uploadedAt?: string
  reviewedAt?: string
  createdAt: string
  updatedAt: string
}
