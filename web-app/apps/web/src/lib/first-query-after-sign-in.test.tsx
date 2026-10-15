import { useQuery } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { useApiFetch } from "@app/api-client"
import { QueryProvider } from "@app/api-client/query-provider"
import { AuthProvider } from "@app/auth"

// BUGS.md, "The first page load after sign-in fires its queries without a token".
// The real AuthProvider, QueryProvider and mutator; only Clerk is mocked, in the
// state it is in straight after sign-in: loaded, with no session installed yet.
const clerk = vi.hoisted(() => ({
  isSignedIn: false,
  token: null as string | null,
}))

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    isLoaded: true,
    isSignedIn: clerk.isSignedIn,
    getToken: async () => clerk.token,
    signOut: async () => {},
  }),
  useUser: () => ({ user: null }),
}))

function Me() {
  const fetcher = useApiFetch()
  const { data } = useQuery({
    queryKey: ["me"],
    queryFn: () => fetcher<{ id: string }>("/api/v1/auth/me"),
  })
  return <p>{data?.id ?? "loading"}</p>
}

function App() {
  return (
    <AuthProvider>
      <QueryProvider>
        <Me />
      </QueryProvider>
    </AuthProvider>
  )
}

beforeEach(() => {
  clerk.isSignedIn = false
  clerk.token = null
  process.env.NEXT_PUBLIC_API_URL = "http://localhost:8100"
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(JSON.stringify({ id: "u1" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
    ),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

it("holds the first query until the session is active, then sends it with the token", async () => {
  const { rerender } = render(<App />)
  await new Promise((resolve) => setTimeout(resolve, 20))
  expect(globalThis.fetch).not.toHaveBeenCalled()

  clerk.isSignedIn = true
  clerk.token = "jwt-after-sign-in"
  rerender(<App />)

  await screen.findByText("u1")
  expect(globalThis.fetch).toHaveBeenCalledOnce()
  const [, init] = vi.mocked(globalThis.fetch).mock.calls[0]
  expect(new Headers(init?.headers).get("Authorization")).toBe(
    "Bearer jwt-after-sign-in",
  )
})
