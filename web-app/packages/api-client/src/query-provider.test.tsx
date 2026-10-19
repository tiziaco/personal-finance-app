import { useMutation, useQuery } from "@tanstack/react-query"
import { render, waitFor } from "@testing-library/react"
import { useEffect } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ApiError } from "./errors"
import type { AppMeta } from "./query-meta"
import { QueryProvider } from "./query-provider"

const { toastForError } = vi.hoisted(() => ({ toastForError: vi.fn() }))

vi.mock("./toast-for-error", () => ({ toastForError }))

function FailingMutation({ meta }: { meta?: AppMeta }) {
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

function FailingQuery({ status, meta }: { status: number; meta?: AppMeta }) {
  useQuery({
    queryKey: ["failing", status],
    queryFn: async () => {
      throw new ApiError(`HTTP ${status}`, status, null, null)
    },
    meta,
    retry: false,
  })
  return null
}

describe("QueryProvider — query errors", () => {
  beforeEach(() => toastForError.mockClear())

  it("toasts a query that has never resolved", async () => {
    render(
      <QueryProvider>
        <FailingQuery status={500} />
      </QueryProvider>,
    )
    await waitFor(() => expect(toastForError).toHaveBeenCalledOnce())
  })

  // The chat page shows a 404 as its not-found screen; every other error
  // must still toast.
  it("a silentError predicate silences only the errors it matches", async () => {
    const notFound = (e: unknown) => e instanceof ApiError && e.status === 404
    render(
      <QueryProvider>
        <FailingQuery status={404} meta={{ silentError: notFound }} />
        <FailingQuery status={500} meta={{ silentError: notFound }} />
      </QueryProvider>,
    )
    await waitFor(() => expect(toastForError).toHaveBeenCalledOnce())
    await new Promise((r) => setTimeout(r, 20))
    expect(toastForError).toHaveBeenCalledOnce()
    expect(toastForError.mock.calls[0][0]).toMatchObject({ status: 500 })
  })
})

// These use the provider's own retry rule, so no `retry: false`. TanStack's
// default retry delay is 1s for the first retry; waitFor timeouts sit above it.
function CountingQuery({ queryFn }: { queryFn: () => Promise<unknown> }) {
  useQuery({ queryKey: ["counting"], queryFn })
  return null
}

function RefetchingQuery({
  queryFn,
  onRefetch,
}: {
  queryFn: () => Promise<unknown>
  onRefetch: (refetch: () => Promise<unknown>) => void
}) {
  const { refetch } = useQuery({ queryKey: ["refetching"], queryFn })
  useEffect(() => onRefetch(refetch), [refetch, onRefetch])
  return null
}

describe("QueryProvider — retry rule", () => {
  beforeEach(() => toastForError.mockClear())

  it("does not retry a 4xx", async () => {
    const queryFn = vi
      .fn()
      .mockRejectedValue(new ApiError("HTTP 404", 404, null, null))
    render(
      <QueryProvider>
        <CountingQuery queryFn={queryFn} />
      </QueryProvider>,
    )
    await waitFor(() => expect(toastForError).toHaveBeenCalledOnce())
    // Longer than the retry delay: a retry would have fired by now.
    await new Promise((r) => setTimeout(r, 1500))
    expect(queryFn).toHaveBeenCalledTimes(1)
  })

  it("retries a 5xx once", async () => {
    const queryFn = vi
      .fn()
      .mockRejectedValue(new ApiError("HTTP 500", 500, null, null))
    render(
      <QueryProvider>
        <CountingQuery queryFn={queryFn} />
      </QueryProvider>,
    )
    await waitFor(() => expect(toastForError).toHaveBeenCalledOnce(), {
      timeout: 3000,
    })
    expect(queryFn).toHaveBeenCalledTimes(2)
  })

  it("a failed refetch behind data already shown does not toast", async () => {
    const queryFn = vi
      .fn()
      .mockResolvedValueOnce("data")
      .mockRejectedValue(new ApiError("HTTP 500", 500, null, null))
    let refetch: (() => Promise<unknown>) | undefined
    render(
      <QueryProvider>
        <RefetchingQuery queryFn={queryFn} onRefetch={(r) => (refetch = r)} />
      </QueryProvider>,
    )
    await waitFor(() => expect(queryFn).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(refetch).toBeDefined())

    await refetch!()
    // The refetch retried once (1s delay), then failed.
    expect(queryFn).toHaveBeenCalledTimes(3)
    expect(toastForError).not.toHaveBeenCalled()
  })
})
