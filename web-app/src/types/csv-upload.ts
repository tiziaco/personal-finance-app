export interface CSVUploadProposalResponse {
  mapping_id: string
  proposed_mapping: Record<string, string>
  sample_rows: Record<string, unknown>[]
  available_fields: string[]
  column_null_rates: Record<string, number>
}

export interface CSVConfirmRequest {
  confirmed_mapping: Record<string, string>
}

export interface CSVUploadResponse {
  imported: number
  skipped: number
  errors: string[]
}
