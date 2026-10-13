import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, waitFor } from "@testing-library/react"
import { useMutation } from "@tanstack/react-query"
import { toast } from "sonner"
import { QueryProvider } from "./query-provider"
import { ApiError } from "./errors"

vi.mock("sonner", () => ({ toast: { error: vi.fn() } }))

const failWith = (status: number) => () =>
  Promise.reject(new ApiError("failed", status, null, null))

describe("QueryProvider mutation toasts", () => {
  beforeEach(() => vi.mocked(toast.error).mockClear())

  it("toasts a failed mutation", async () => {
    const { result } = renderHook(
      () => useMutation({ mutationFn: failWith(409) }),
      { wrapper: QueryProvider },
    )
    result.current.mutate()
    await waitFor(() => expect(toast.error).toHaveBeenCalledTimes(1))
  })

  it("stays silent for a status the mutation handles itself", async () => {
    const { result } = renderHook(
      () =>
        useMutation({
          mutationFn: failWith(409),
          meta: { silentStatuses: [409] },
        }),
      { wrapper: QueryProvider },
    )
    result.current.mutate()
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(toast.error).not.toHaveBeenCalled()
  })

  it("still toasts other statuses", async () => {
    const { result } = renderHook(
      () =>
        useMutation({
          mutationFn: failWith(500),
          meta: { silentStatuses: [409] },
        }),
      { wrapper: QueryProvider },
    )
    result.current.mutate()
    await waitFor(() => expect(toast.error).toHaveBeenCalledTimes(1))
  })
})
