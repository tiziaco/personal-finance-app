import type {
  TransactionListResponse,
  TransactionResponse,
  TransactionFilters,
  BatchUpdateRequest,
  BatchUpdateResponse,
  BatchDeleteRequest,
  BatchDeleteResponse,
  CreateTransactionRequest,
  TransactionUpdateRequest,
} from '@/types/transaction'
import type {
  CSVUploadProposalResponse,
  CSVUploadResponse,
} from '@/types/csv-upload'
import { apiRequest } from './client'

export async function uploadCSV(
  token: string | null,
  file: File
): Promise<CSVUploadProposalResponse> {
  const formData = new FormData()
  formData.append('file', file)
  return apiRequest<CSVUploadProposalResponse>(
    '/api/v1/transactions/upload',
    token,
    {
      method: 'POST',
      body: formData,
    }
  )
}

export async function confirmCSVUpload(
  token: string | null,
  mappingId: string,
  confirmedMapping: Record<string, string>
): Promise<CSVUploadResponse> {
  return apiRequest<CSVUploadResponse>(
    `/api/v1/transactions/upload/${mappingId}/confirm`,
    token,
    {
      method: 'POST',
      body: JSON.stringify({ confirmed_mapping: confirmedMapping }),
    }
  )
}

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
  data: TransactionUpdateRequest
): Promise<TransactionResponse> {
  return apiRequest<TransactionResponse>(`/api/v1/transactions/${id}`, token, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function createTransaction(
  token: string | null,
  data: CreateTransactionRequest
): Promise<TransactionResponse> {
  return apiRequest<TransactionResponse>('/api/v1/transactions', token, {
    method: 'POST',
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
