import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { renderHook } from "@testing-library/react"
import { ApiError } from "./errors"
import { useApiFetch, useApiRequest } from "./use-api-fetch"

// useApiFetch is a hook so it can read a fresh Clerk token per call. Only the
// token source is mocked; everything else here is the real mutator.
const { getToken, signOut } = vi.hoisted(() => ({
  getToken: vi.fn(),
  signOut: vi.fn(),
}))

vi.mock("@app/auth", () => ({ useAppAuth: () => ({ getToken, signOut }) }))

function jsonResponse(
  body: unknown,
  init: { status?: number; headers?: Record<string, string> } = {},
) {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status: init.status ?? 200,
    headers: { "content-type": "application/json", ...init.headers },
  })
}

/** The last RequestInit that reached fetch, for asserting on headers. */
function lastCall() {
  const mock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>
  const [url, init] = mock.mock.calls.at(-1) as [string, RequestInit]
  return { url, headers: new Headers(init.headers) }
}

function callApi() {
  return renderHook(() => useApiFetch()).result.current
}

/**
 * Await a call expected to reject and hand back the ApiError.
 *
 * `.catch((e) => e)` would type the result as `unknown` and fail `tsc --noEmit`
 * — test files are type-checked by the workspace type-check, same as source.
 */
async function rejection(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise
  } catch (caught) {
    expect(caught).toBeInstanceOf(ApiError)
    return caught as ApiError
  }
  throw new Error("expected the request to reject, but it resolved")
}

beforeEach(() => {
  getToken.mockReset()
  getToken.mockResolvedValue("tok-123")
  signOut.mockReset()
  signOut.mockResolvedValue(undefined)
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ ok: true })))
  process.env.NEXT_PUBLIC_API_URL = "http://localhost:8100"
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("base URL resolution", () => {
  it("prefixes a generated route with the configured base", async () => {
    await callApi()("/api/v1/me")
    expect(lastCall().url).toBe("http://localhost:8100/api/v1/me")
  })

  it("strips trailing slashes so routes do not double up", async () => {
    // A configured value ending in "/" would produce "//api/v1/...", which
    // presents as a confusing 404 rather than a config error.
    process.env.NEXT_PUBLIC_API_URL = "http://localhost:8100///"
    await callApi()("/api/v1/me")
    expect(lastCall().url).toBe("http://localhost:8100/api/v1/me")
  })

  it("passes an absolute URL through untouched", async () => {
    await callApi()("https://example.test/thing")
    expect(lastCall().url).toBe("https://example.test/thing")
  })

  it("throws a named error when the base URL is unset", async () => {
    delete process.env.NEXT_PUBLIC_API_URL
    await expect(callApi()("/api/v1/me")).rejects.toThrow(
      "@app/api-client: NEXT_PUBLIC_API_URL is not set",
    )
  })
})

describe("authorization header", () => {
  it("attaches the current token", async () => {
    await callApi()("/api/v1/me")
    expect(lastCall().headers.get("authorization")).toBe("Bearer tok-123")
  })

  it("omits the header when there is no token", async () => {
    getToken.mockResolvedValue(null)
    await callApi()("/api/v1/me")
    expect(lastCall().headers.has("authorization")).toBe(false)
  })

  it("does not overwrite a caller-supplied header", async () => {
    await callApi()("/api/v1/me", {
      headers: { Authorization: "Bearer caller" },
    })
    expect(lastCall().headers.get("authorization")).toBe("Bearer caller")
  })
})

describe("content type", () => {
  it("sets JSON for a plain body", async () => {
    await callApi()("/api/v1/me", {
      method: "POST",
      body: JSON.stringify({ a: 1 }),
    })
    expect(lastCall().headers.get("content-type")).toBe("application/json")
  })

  it("leaves FormData alone so the browser sets its own boundary", async () => {
    await callApi()("/api/v1/upload", {
      method: "POST",
      body: new FormData(),
    })
    expect(lastCall().headers.has("content-type")).toBe(false)
  })

  it("leaves Blob alone", async () => {
    await callApi()("/api/v1/upload", {
      method: "POST",
      body: new Blob(["x"]),
    })
    expect(lastCall().headers.has("content-type")).toBe(false)
  })

  it("sets nothing when there is no body", async () => {
    await callApi()("/api/v1/me")
    expect(lastCall().headers.has("content-type")).toBe(false)
  })
})

describe("responses", () => {
  it("parses a JSON body", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse({ id: 7 }))
    await expect(callApi()("/api/v1/me")).resolves.toEqual({ id: 7 })
  })

  it("returns undefined for 204", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(null, { status: 204 }),
    )
    await expect(callApi()("/api/v1/thing")).resolves.toBeUndefined()
  })

  it("returns undefined when content-length is 0", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response("", { status: 200, headers: { "content-length": "0" } }),
    )
    await expect(callApi()("/api/v1/thing")).resolves.toBeUndefined()
  })

  it("returns text for a non-JSON content type", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response("plain", {
        status: 200,
        headers: { "content-type": "text/plain" },
      }),
    )
    await expect(callApi()("/api/v1/thing")).resolves.toBe("plain")
  })
})

describe("errors", () => {
  it("throws ApiError carrying status, parsed body and request id", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      jsonResponse(
        { detail: "nope" },
        { status: 403, headers: { "x-request-id": "req-abc" } },
      ),
    )

    const error = await rejection(callApi()("/api/v1/me"))

    expect(error.status).toBe(403)
    expect(error.body).toEqual({ detail: "nope" })
    expect(error.requestId).toBe("req-abc")
  })

  it("uses the status as the message, never the server's reason phrase", async () => {
    // Server-authored text must never reach the UI. QueryProvider maps status
    // to curated copy; a leaked reason phrase would bypass that entirely.
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response("{}", { status: 500, statusText: "Internal Kaboom" }),
    )

    const error = await rejection(callApi()("/api/v1/me"))

    expect(error.message).toBe("HTTP 500")
    expect(error.message).not.toContain("Kaboom")
  })

  it("keeps a 503 body intact so callers can recover it", async () => {
    // useServerStatus depends on exactly this: the degraded readiness payload
    // arrives as ApiError.body, never as data.
    vi.mocked(globalThis.fetch).mockResolvedValue(
      jsonResponse({ status: "degraded" }, { status: 503 }),
    )

    const error = await rejection(callApi()("/api/v1/ready"))

    expect(error.body).toEqual({ status: "degraded" })
  })

  it("survives an unparseable error body", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response("<html>gateway</html>", {
        status: 502,
        headers: { "content-type": "application/json" },
      }),
    )

    const error = await rejection(callApi()("/api/v1/me"))

    expect(error.body).toBeNull()
    expect(error.requestId).toBeNull()
  })
})

describe("useApiRequest", () => {
  function request() {
    return renderHook(() => useApiRequest()).result.current
  }

  it("returns the response unread, with the bearer token sent", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("data: x\n\n", { status: 200 })),
    )
    const response = await request()("/api/v1/stream", {
      method: "POST",
      body: "{}",
    })
    expect(response.bodyUsed).toBe(false)
    expect(await response.text()).toBe("data: x\n\n")
    expect(lastCall().url).toBe("http://localhost:8100/api/v1/stream")
    expect(lastCall().headers.get("Authorization")).toBe("Bearer tok-123")
    expect(lastCall().headers.get("Content-Type")).toBe("application/json")
  })

  // Review Focus 4: a refused stream's body reads as the hooks' does.
  it("throws ApiError with the JSON error body parsed", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse({ detail: "slow down" }, { status: 429 }),
        ),
    )
    const error = await rejection(request()("/api/v1/stream"))
    expect(error.status).toBe(429)
    expect(error.body).toEqual({ detail: "slow down" })
  })
})

describe("a 401", () => {
  it("is retried once with a fresh token", async () => {
    getToken.mockResolvedValueOnce("stale").mockResolvedValueOnce("fresh")
    vi.mocked(globalThis.fetch)
      .mockResolvedValueOnce(jsonResponse({}, { status: 401 }))
      .mockResolvedValueOnce(jsonResponse({ ok: true }))

    await expect(callApi()("/api/v1/me")).resolves.toEqual({ ok: true })

    expect(getToken).toHaveBeenLastCalledWith({ forceRefresh: true })
    expect(lastCall().headers.get("Authorization")).toBe("Bearer fresh")
    expect(signOut).not.toHaveBeenCalled()
  })

  it("replays the request's body", async () => {
    vi.mocked(globalThis.fetch)
      .mockResolvedValueOnce(jsonResponse({}, { status: 401 }))
      .mockResolvedValueOnce(jsonResponse({ ok: true }))

    await callApi()("/api/v1/transactions", {
      method: "POST",
      body: '{"merchant":"x"}',
    })

    const bodies = vi
      .mocked(globalThis.fetch)
      .mock.calls.map(([, init]) => (init as RequestInit).body)
    expect(bodies).toEqual(['{"merchant":"x"}', '{"merchant":"x"}'])
  })

  // The session is over: ended in another tab, or never coming back.
  it("signs out when the retry is refused too, and still rejects", async () => {
    vi.mocked(globalThis.fetch).mockImplementation(async () =>
      jsonResponse({}, { status: 401 }),
    )

    const error = await rejection(callApi()("/api/v1/me"))

    expect(error.status).toBe(401)
    expect(globalThis.fetch).toHaveBeenCalledTimes(2)
    expect(signOut).toHaveBeenCalledOnce()
  })

  it("rejects with the ApiError even when signing out fails", async () => {
    signOut.mockRejectedValue(new Error("session already gone"))
    vi.mocked(globalThis.fetch).mockImplementation(async () =>
      jsonResponse({}, { status: 401 }),
    )

    const error = await rejection(callApi()("/api/v1/me"))
    expect(error.status).toBe(401)
  })
})

describe("other refusals", () => {
  it.each([403, 500])("%i is neither retried nor signs out", async (status) => {
    vi.mocked(globalThis.fetch).mockImplementation(async () =>
      jsonResponse({}, { status }),
    )

    await rejection(callApi()("/api/v1/me"))

    expect(globalThis.fetch).toHaveBeenCalledOnce()
    expect(getToken).toHaveBeenCalledOnce()
    expect(signOut).not.toHaveBeenCalled()
  })
})
