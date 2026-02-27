import type {
  TransactionListResponse,
  TransactionResponse,
  TransactionFilters,
  BatchUpdateRequest,
  BatchUpdateResponse,
  BatchDeleteRequest,
  BatchDeleteResponse,
} from '@/types/transaction'
import { apiRequest } from './client'

export async function fetchTransactions(
  token: string | null,
  filters: TransactionFilters = {}
): Promise<TransactionListResponse> {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      params.set(key, String(value))
    }
  })
  const query = params.toString()
  return apiRequest<TransactionListResponse>(
    `/api/v1/transactions${query ? `?${query}` : ''}`,
    token
  )
}

export async function updateTransaction(
  token: string | null,
  id: number,
  data: Partial<Pick<TransactionResponse, 'category'>>
): Promise<TransactionResponse> {
  return apiRequest<TransactionResponse>(`/api/v1/transactions/${id}`, token, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function batchUpdateTransactions(
  token: string | null,
  body: BatchUpdateRequest
): Promise<BatchUpdateResponse> {
  return apiRequest<BatchUpdateResponse>('/api/v1/transactions/batch', token, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

export async function batchDeleteTransactions(
  token: string | null,
  body: BatchDeleteRequest
): Promise<BatchDeleteResponse> {
  return apiRequest<BatchDeleteResponse>('/api/v1/transactions/batch', token, {
    method: 'DELETE',
    body: JSON.stringify(body),
  })
}
