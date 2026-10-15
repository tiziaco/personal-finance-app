import { describe, expect, it } from "vitest"
import { ApiError } from "@app/api-client"
import {
  EXPIRED,
  UNAVAILABLE,
  checkFile,
  confirmErrorMessage,
  fileErrorMessage,
  isConfirmInlineError,
  isExpired,
  isUploadInlineError,
} from "./import-errors"

const apiError = (status: number, reason?: string) =>
  new ApiError(
    `HTTP ${status}`,
    status,
    { error: "X", details: reason ? { reason } : {} },
    null,
  )

describe("import errors", () => {
  it("refuses a non-csv name or a file over 5 MB before sending", () => {
    expect(checkFile(new File(["a"], "notes.txt"))).toBe("Choose a .csv file.")
    expect(checkFile(new File(["a"], "KONTO.CSV"))).toBeUndefined()
    const big = new File(["a"], "big.csv")
    Object.defineProperty(big, "size", { value: 5 * 1024 * 1024 + 1 })
    expect(checkFile(big)).toBe("The file is larger than 5 MB.")
  })

  it("words a refused file by its reason, never the server's text", () => {
    expect(fileErrorMessage(apiError(422, "too_many_rows"))).toBe(
      "The file has more than 3,000 rows. Split it and import each part.",
    )
    expect(fileErrorMessage(apiError(422, "malformed"))).toBe(
      "The file isn't a well-formed CSV. Check its quotes and line endings.",
    )
    expect(fileErrorMessage(apiError(422, "something_new"))).toBe(
      "This file can't be read as a bank export.",
    )
    expect(fileErrorMessage(apiError(500))).toBeUndefined()
    expect(isUploadInlineError(apiError(422))).toBe(true)
    expect(isUploadInlineError(apiError(429))).toBe(false)
  })

  it("words a failed confirm", () => {
    expect(confirmErrorMessage(apiError(503))).toBe(UNAVAILABLE)
    expect(confirmErrorMessage(apiError(422, "missing_required"))).toBe(
      "This mapping can't be used. Check the columns and try again.",
    )
    expect(confirmErrorMessage(apiError(500))).toBeUndefined()
    expect(isExpired(apiError(404))).toBe(true)
    expect(EXPIRED).toBe("This upload has expired. Choose the file again.")
    expect(
      [404, 422, 503].map((s) => isConfirmInlineError(apiError(s))),
    ).toEqual([true, true, true])
    expect(isConfirmInlineError(apiError(500))).toBe(false)
  })
})
