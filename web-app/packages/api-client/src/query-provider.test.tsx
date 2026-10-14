import { useMutation } from "@tanstack/react-query"
import { render, waitFor } from "@testing-library/react"
import { useEffect } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ApiError } from "./errors"
import { QueryProvider } from "./query-provider"

const { toastForError } = vi.hoisted(() => ({ toastForError: vi.fn() }))

vi.mock("./toast-for-error", () => ({ toastForError }))

function FailingMutation({ meta }: { meta?: Record<string, unknown> }) {
  const { mutate } = useMutation({
    mutationFn: async () => {
      throw new ApiError("HTTP 500", 500, null, null)
    },
    meta,
  })
  useEffect(() => mutate(), [mutate])
  return null
}

describe("QueryProvider — mutation errors", () => {
  beforeEach(() => toastForError.mockClear())

  it("toasts a failed mutation", async () => {
    render(
      <QueryProvider>
        <FailingMutation />
      </QueryProvider>,
    )
    await waitFor(() => expect(toastForError).toHaveBeenCalledOnce())
  })

  // A request the user didn't make (a generated title) has no one waiting on it.
  it("does not toast a mutation that opts out with silentError", async () => {
    render(
      <QueryProvider>
        <FailingMutation meta={{ silentError: true }} />
        <FailingMutation />
      </QueryProvider>,
    )
    await waitFor(() => expect(toastForError).toHaveBeenCalledOnce())
    await new Promise((r) => setTimeout(r, 20))
    expect(toastForError).toHaveBeenCalledOnce()
  })
})
