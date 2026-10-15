import { describe, expect, it } from "vitest"
import { ApiError } from "@app/api-client"
import { FileProblem } from "@app/api-client/types"
import {
  checkFile,
  confirmProblem,
  isConfirmInlineError,
  isUploadInlineError,
  problemMessage,
  uploadProblem,
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
    expect(checkFile(new File(["a"], "notes.txt"))).toBe("not_csv")
    expect(checkFile(new File(["a"], "KONTO.CSV"))).toBeUndefined()
    const big = new File(["a"], "big.csv")
    Object.defineProperty(big, "size", { value: 5 * 1024 * 1024 + 1 })
    expect(checkFile(big)).toBe("too_large")
  })

  it("reads a refused file's reason, and an unknown one as unreadable", () => {
    expect(uploadProblem(apiError(422, "too_many_rows"))).toBe("too_many_rows")
    expect(uploadProblem(apiError(422, "something_new"))).toBe("unreadable")
    expect(uploadProblem(apiError(422))).toBe("unreadable")
    expect(uploadProblem(apiError(500))).toBeUndefined()
    expect(isUploadInlineError(apiError(422))).toBe(true)
    expect(isUploadInlineError(apiError(429))).toBe(false)
  })

  it("reads a failed confirm", () => {
    expect(confirmProblem(apiError(404))).toBe("expired")
    expect(confirmProblem(apiError(503))).toBe("unavailable")
    expect(confirmProblem(apiError(422, "missing_required"))).toBe(
      "bad_mapping",
    )
    expect(confirmProblem(apiError(500))).toBeUndefined()
    expect(
      [404, 422, 503].map((s) => isConfirmInlineError(apiError(s))),
    ).toEqual([true, true, true])
    expect(isConfirmInlineError(apiError(500))).toBe(false)
  })

  it("words every problem itself, never with the server's text", () => {
    expect(problemMessage("malformed")).toBe(
      "The file isn't a well-formed CSV. Check its quotes and line endings.",
    )
    expect(problemMessage("expired")).toBe(
      "This upload has expired. Choose the file again.",
    )
    for (const problem of Object.values(FileProblem)) {
      expect(problemMessage(problem)).toMatch(/\.$/)
    }
  })
})
