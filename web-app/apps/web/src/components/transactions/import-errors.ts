import { ApiError } from "@app/api-client"
import { FileProblem, type FileRefusal } from "@app/api-client/types"

export const MAX_FILE_BYTES = 5 * 1024 * 1024

/** What the dialog shows inline: a file refusal's reason, or one of its own problems. */
export type ImportProblem =
  FileProblem | "unreadable" | "expired" | "unavailable" | "bad_mapping"

/** Every problem worded here: the web never shows server text. */
const MESSAGES: Record<ImportProblem, string> = {
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
  unreadable: "This file can't be read as a bank export.",
  expired: "This upload has expired. Choose the file again.",
  unavailable:
    "Categorisation isn't available right now. Your file is kept for 30 minutes, so try again.",
  bad_mapping: "This mapping can't be used. Check the columns and try again.",
}

export const problemMessage = (problem: ImportProblem) => MESSAGES[problem]

const status = (error: unknown) =>
  error instanceof ApiError ? error.status : undefined

/** A refusal's reason when it is one this build knows. Nothing validates an error body, so it is checked here. */
function fileProblem(error: unknown): FileProblem | undefined {
  if (!(error instanceof ApiError)) return undefined
  const reason: unknown = (error.body as Partial<FileRefusal> | null)?.details
    ?.reason
  return Object.values(FileProblem).find((problem) => problem === reason)
}

/** Why a file is refused before it is sent, or undefined. */
export function checkFile(file: File): FileProblem | undefined {
  if (!file.name.toLowerCase().endsWith(".csv")) return FileProblem.not_csv
  if (file.size > MAX_FILE_BYTES) return FileProblem.too_large
  return undefined
}

export const isUploadInlineError = (error: unknown) => status(error) === 422
export const isConfirmInlineError = (error: unknown) =>
  [404, 422, 503].includes(status(error) ?? 0)

/** A failed upload's problem; undefined when QueryProvider's toast covers it. */
export function uploadProblem(error: unknown): ImportProblem | undefined {
  if (!isUploadInlineError(error)) return undefined
  return fileProblem(error) ?? "unreadable"
}

/** A failed confirm's problem; undefined when QueryProvider's toast covers it. */
export function confirmProblem(error: unknown): ImportProblem | undefined {
  if (status(error) === 404) return "expired"
  if (status(error) === 503) return "unavailable"
  if (status(error) === 422) return "bad_mapping"
  return undefined
}
