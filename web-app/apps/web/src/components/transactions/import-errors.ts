import { ApiError } from "@app/api-client"

export const MAX_FILE_BYTES = 5 * 1024 * 1024
export const EXPIRED = "This upload has expired. Choose the file again."
export const UNAVAILABLE =
  "Categorisation isn't available right now. Your file is kept for 30 minutes, so try again."
const BAD_MAPPING =
  "This mapping can't be used. Check the columns and try again."
const UNREADABLE = "This file can't be read as a bank export."

/** The server's refusal reasons, worded here: the web never shows server text. */
const FILE_REASONS: Record<string, string> = {
  not_csv: "Choose a .csv file.",
  too_large: "The file is larger than 5 MB.",
  empty: "The file is empty.",
  malformed:
    "The file isn't a well-formed CSV. Check its quotes and line endings.",
  no_header: "The file needs a header row and at least two columns.",
  unnamed_column: "Every column needs a name in the header row.",
  duplicate_column: "Two columns have the same name.",
  no_rows: "The file has a header but no rows.",
  too_many_rows:
    "The file has more than 3,000 rows. Split it and import each part.",
}

const status = (error: unknown) =>
  error instanceof ApiError ? error.status : undefined

function reason(error: unknown): string | undefined {
  if (!(error instanceof ApiError)) return undefined
  const details = (error.body as { details?: { reason?: unknown } } | null)
    ?.details
  return typeof details?.reason === "string" ? details.reason : undefined
}

/** Why a file is refused before it is sent, or undefined. */
export function checkFile(file: File): string | undefined {
  if (!file.name.toLowerCase().endsWith(".csv")) return FILE_REASONS.not_csv
  if (file.size > MAX_FILE_BYTES) return FILE_REASONS.too_large
  return undefined
}

export const isUploadInlineError = (error: unknown) => status(error) === 422
export const isConfirmInlineError = (error: unknown) =>
  [404, 422, 503].includes(status(error) ?? 0)
export const isExpired = (error: unknown) => status(error) === 404

/** The inline message for a failed upload; undefined when QueryProvider's toast covers it. */
export function fileErrorMessage(error: unknown): string | undefined {
  if (!isUploadInlineError(error)) return undefined
  return FILE_REASONS[reason(error) ?? ""] ?? UNREADABLE
}

/** The inline message for a failed confirm (a 404 goes back to choosing a file instead). */
export function confirmErrorMessage(error: unknown): string | undefined {
  if (status(error) === 503) return UNAVAILABLE
  if (status(error) === 422) return BAD_MAPPING
  return undefined
}
