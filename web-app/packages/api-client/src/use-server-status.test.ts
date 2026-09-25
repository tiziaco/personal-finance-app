import { renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ApiError } from "./errors"
import { useServerStatus } from "./use-server-status"

// Only the generated query hook is mocked. ApiError and the generated Zod
// validator stay real: the contract is that a 503 body survives
// GetReadinessResponse.safeParse.
const { useGetReadiness } = vi.hoisted(() => ({ useGetReadiness: vi.fn() }))

vi.mock("./generated/endpoints/system", () => ({ useGetReadiness }))

function readiness(
  overrides: { status?: "healthy" | "degraded"; version?: string } = {},
) {
  return {
    components: {
      agents_healthy: true,
      api: "healthy" as const,
      database: {
        connection_pool: {
          checked_in: 1,
          checked_out: 0,
          overflow: 0,
          size: 5,
          total: 5,
        },
        status: "healthy" as const,
      },
    },
    environment: "development" as const,
    status: overrides.status ?? ("healthy" as const),
    timestamp: "2026-09-16T12:00:00+00:00",
    version: overrides.version ?? "1.2.3",
  }
}

function mockQuery(value: {
  data?: unknown
  isLoading?: boolean
  error?: unknown
}) {
  useGetReadiness.mockReturnValue({
    data: value.data,
    isLoading: value.isLoading ?? false,
    error: value.error,
  })
}

function status() {
  return renderHook(() => useServerStatus()).result.current
}

beforeEach(() => {
  useGetReadiness.mockReset()
})

describe("useServerStatus", () => {
  it("passes a successful payload straight through", () => {
    const payload = readiness()
    mockQuery({ data: payload })

    expect(status().status).toEqual(payload)
    expect(status().error).toBeUndefined()
  })

  it("recovers the degraded payload from a 503 body and clears the error", () => {
    mockQuery({
      error: new ApiError(
        "HTTP 503",
        503,
        readiness({ status: "degraded", version: "9.9.9" }),
        "req-1",
      ),
    })

    const result = status()
    expect(result.status).toMatchObject({
      status: "degraded",
      version: "9.9.9",
    })
    expect(result.error).toBeUndefined()
  })

  it("prefers the recovered body over stale cached data", () => {
    mockQuery({
      data: readiness({ status: "healthy", version: "1.0.0" }),
      error: new ApiError(
        "HTTP 503",
        503,
        readiness({ status: "degraded", version: "2.0.0" }),
        "req-2",
      ),
    })

    expect(status().status).toMatchObject({
      status: "degraded",
      version: "2.0.0",
    })
  })

  it("keeps the error when a 503 body is not a readiness payload", () => {
    const error = new ApiError(
      "HTTP 503",
      503,
      "<html>Bad Gateway</html>",
      "req-3",
    )
    mockQuery({ error })

    const result = status()
    expect(result.status).toBeUndefined()
    expect(result.error).toBe(error)
  })

  it("keeps the error for any other status, next to stale data", () => {
    const stale = readiness()
    const error = new ApiError("HTTP 500", 500, { detail: "boom" }, "req-4")
    mockQuery({ data: stale, error })

    const result = status()
    expect(result.status).toEqual(stale)
    expect(result.error).toBe(error)
  })

  it("keeps an error that is not an ApiError", () => {
    const error = new TypeError("Failed to fetch")
    mockQuery({ error })

    expect(status().error).toBe(error)
  })

  it("forwards the loading flag", () => {
    mockQuery({ isLoading: true })

    expect(status().isLoading).toBe(true)
  })
})
