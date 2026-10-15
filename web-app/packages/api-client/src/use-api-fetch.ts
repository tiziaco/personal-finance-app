"use client"

import { useCallback } from "react"
import { useAppAuth } from "@app/auth"

import { ApiError } from "./errors"

/**
 * The error type orval wires into every generated hook's `TError`.
 *
 * orval looks for the literal text `export type ErrorType` in this file and,
 * finding it, emits `ErrorType<...>` in place of the error type it would
 * otherwise derive from the spec's declared error response. Without it every
 * hook advertises an error it cannot produce — `useGetMe().error` typed as
 * HTTPValidationError, `useGetReadiness().error` as ReadinessResponse — while
 * the mutator below only ever throws ApiError.
 *
 * The body parameter is accepted and deliberately ignored. Nothing validates
 * the payload against the declared error schema, so `ApiError.body` stays
 * `unknown`: narrowing it here would relocate the lie rather than remove it.
 */
export type ErrorType<_Body = unknown> = ApiError

function resolveBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_URL
  if (!url) {
    throw new Error("@app/api-client: NEXT_PUBLIC_API_URL is not set")
  }
  // Generated routes always start with "/", so a configured value ending in one
  // would produce "//api/v1/...", which presents as a confusing 404.
  return url.replace(/\/+$/, "")
}

async function parseErrorBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? ""
  try {
    if (contentType.includes("application/json")) return await response.json()
    return await response.text()
  } catch {
    return null
  }
}

/** A request through the API's transport, with the session's token bound. */
export type ApiRequest = (url: string, init?: RequestInit) => Promise<Response>

/**
 * One request to the API: the base URL, the bearer token, a JSON content type
 * for a plain body, and an ApiError for any non-2xx. The response comes back
 * unread, so a streamed body can be consumed as it arrives.
 */
async function apiRequest(
  url: string,
  init: RequestInit | undefined,
  token: string | null,
): Promise<Response> {
  const fullUrl = /^https?:\/\//i.test(url) ? url : `${resolveBaseUrl()}${url}`
  const headers = new Headers(init?.headers)

  if (token && !headers.has("authorization")) {
    headers.set("Authorization", `Bearer ${token}`)
  }

  // Only set a JSON content type for plain bodies. Never for FormData — the
  // browser must set its own multipart boundary — nor for Blob or ArrayBuffer.
  const body = init?.body
  if (
    body != null &&
    !headers.has("content-type") &&
    !(body instanceof FormData) &&
    !(body instanceof Blob) &&
    !(body instanceof ArrayBuffer)
  ) {
    headers.set("Content-Type", "application/json")
  }

  const response = await fetch(fullUrl, { ...init, headers })
  if (!response.ok) {
    // Deliberately not response.statusText: the reason phrase is server-supplied
    // text, and server error text must never reach the UI. status, body and
    // requestId still carry everything needed to debug.
    throw new ApiError(
      `HTTP ${response.status}`,
      response.status,
      await parseErrorBody(response),
      response.headers.get("x-request-id"),
    )
  }
  return response
}

const isUnauthorized = (error: unknown) =>
  error instanceof ApiError && error.status === 401

/**
 * The API's transport with the current session's token, read on every call.
 * For a caller that reads the body itself: the chat stream. Everything else
 * uses a generated hook, which goes through useApiFetch.
 *
 * A 401 is an auth event, not an error to show. The request goes once more
 * with a token fetched fresh. The server ran no handler, so replaying even a
 * POST is safe. A second 401 means the session is over, and signOut() ends it
 * and loads the sign-in page. The server keeps 401 for bad credentials alone,
 * so an outage never signs anyone out. The ApiError still reaches the caller.
 */
export function useApiRequest(): ApiRequest {
  const { getToken, signOut } = useAppAuth()
  return useCallback(
    async (url, init) => {
      try {
        return await apiRequest(url, init, await getToken())
      } catch (error) {
        if (!isUnauthorized(error)) throw error
      }
      try {
        return await apiRequest(
          url,
          init,
          await getToken({ forceRefresh: true }),
        )
      } catch (error) {
        // signOut is single-flight: many requests refused at once sign out once.
        // It navigates even when ending the session fails, so its rejection is moot.
        if (isUnauthorized(error)) void signOut().catch(() => {})
        throw error
      }
    },
    [getToken, signOut],
  )
}

/**
 * The mutator every generated endpoint routes through.
 *
 * It is a hook, not a module-level singleton, and that is deliberate. A
 * module-scope client would be shared across concurrent requests in a Next.js
 * server process — one tenant's token serving another tenant's request — and
 * would freeze the first render's getToken closure. As a hook it reads the
 * current token on every call, needs no provider of its own, and makes the
 * provider ordering in the root layout irrelevant.
 *
 * orval recognises the `use` prefix and calls this inside each generated hook.
 */
export function useApiFetch() {
  const request = useApiRequest()

  return useCallback(
    async <T>(url: string, init?: RequestInit): Promise<T> => {
      const response = await request(url, init)

      if (response.status === 204) return undefined as T
      if (response.headers.get("content-length") === "0") return undefined as T

      const contentType = response.headers.get("content-type") ?? ""
      if (contentType.includes("application/json"))
        return (await response.json()) as T

      return (await response.text()) as unknown as T
    },
    [request],
  )
}
