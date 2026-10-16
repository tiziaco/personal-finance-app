import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import {
  getGenerateInsightsMutationKey,
  useGenerateInsights,
  useGetInsights,
} from "@app/api-client/endpoints/insights"
import { InsightsView } from "./insights-view"

vi.mock("@app/api-client/endpoints/insights", async (orig) => ({
  ...(await orig<typeof import("@app/api-client/endpoints/insights")>()),
  useGetInsights: vi.fn(),
  useGenerateInsights: vi.fn(),
}))
vi.mock("next/link", () => ({
  default: ({
    href,
    children,
  }: {
    href: string
    children: React.ReactNode
  }) => <a href={href}>{children}</a>,
}))

const mutate = vi.fn()
const refetch = vi.fn()

const CARD = {
  section: "spending",
  severity: "high",
  period: "month",
  summary: "Groceries rose",
  narrative: "You spent more on groceries.",
  key_figure: { kind: "percent", value: "20", qualifier: "vs August" },
  link: null,
}

const insights = (data: object | undefined, state: object = {}) =>
  vi.mocked(useGetInsights).mockReturnValue({
    data,
    isPending: !data,
    isError: false,
    refetch,
    ...state,
  } as unknown as ReturnType<typeof useGetInsights>)

const response = (status: string, cards: object[] = []) => ({
  status,
  generated_at: "2026-10-14T09:30:00Z",
  reference_month: "2026-09",
  month_to_date_through: "2026-10-14",
  insights: cards,
})

const generating = (state: object = {}) =>
  vi.mocked(useGenerateInsights).mockReturnValue({
    mutate,
    isPending: false,
    isError: false,
    ...state,
  } as unknown as ReturnType<typeof useGenerateInsights>)

const renderView = () =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <InsightsView />
    </QueryClientProvider>,
  )

beforeEach(() => {
  vi.clearAllMocks()
  generating()
})

describe("InsightsView", () => {
  it("generates once on arrival when stale", () => {
    insights(response("stale", [CARD]))
    const { rerender } = renderView()
    rerender(
      <QueryClientProvider client={new QueryClient()}>
        <InsightsView />
      </QueryClientProvider>,
    )
    expect(mutate).toHaveBeenCalledTimes(1)
    expect(screen.getByText("Groceries rose")).toBeInTheDocument()
  })

  it("generates on arrival when never generated", () => {
    insights(response("none"))
    renderView()
    expect(mutate).toHaveBeenCalledTimes(1)
  })

  it("does not generate when fresh", () => {
    insights(response("fresh", [CARD]))
    renderView()
    expect(mutate).not.toHaveBeenCalled()
    expect(screen.getByText("Groceries rose")).toBeInTheDocument()
  })

  it("shows the upload empty state for no_data and never generates", () => {
    insights(response("no_data"))
    renderView()
    expect(mutate).not.toHaveBeenCalled()
    expect(screen.getByRole("link", { name: "Upload a CSV" })).toHaveAttribute(
      "href",
      "/transactions",
    )
  })

  it("a failed auto-generate shows Retry and does not loop", async () => {
    insights(response("none"))
    generating({ isError: true })
    renderView()
    expect(mutate).toHaveBeenCalledTimes(1)
    await userEvent.click(screen.getByRole("button", { name: "Retry" }))
    expect(mutate).toHaveBeenCalledTimes(2)
  })

  it("keeps previous cards when regenerate fails", () => {
    insights(response("fresh", [CARD]))
    generating({ isError: true })
    renderView()
    expect(screen.getByText("Groceries rose")).toBeInTheDocument()
    expect(
      screen.getByText("Couldn't regenerate insights."),
    ).toBeInTheDocument()
  })

  it("regenerates on click and disables the button while pending", async () => {
    insights(response("fresh", [CARD]))
    const { unmount } = renderView()
    await userEvent.click(screen.getByRole("button", { name: "Regenerate" }))
    expect(mutate).toHaveBeenCalledTimes(1)
    unmount()
    generating({ isPending: true })
    renderView()
    expect(screen.getByRole("button", { name: "Generating…" })).toBeDisabled()
  })

  it("shows Nothing stands out for a fresh empty set", () => {
    insights(response("fresh"))
    renderView()
    expect(
      screen.getByText("Nothing stands out this month."),
    ).toBeInTheDocument()
  })

  it("generates again once when the set goes stale after an earlier run settled", () => {
    const client = new QueryClient()
    const wrap = () => (
      <QueryClientProvider client={client}>
        <InsightsView />
      </QueryClientProvider>
    )
    insights(response("fresh", [CARD]))
    const { rerender } = render(wrap())
    expect(mutate).not.toHaveBeenCalled()
    insights({
      ...response("stale", [CARD]),
      generated_at: "2026-10-14T09:30:00Z",
    })
    rerender(wrap())
    rerender(wrap())
    expect(mutate).toHaveBeenCalledTimes(1)
    // Not stuck: the run is not pending, so Regenerate is usable.
    expect(screen.getByRole("button", { name: "Regenerate" })).toBeEnabled()
  })

  it("does not loop when the run for a later staleness fails", () => {
    const client = new QueryClient()
    const wrap = () => (
      <QueryClientProvider client={client}>
        <InsightsView />
      </QueryClientProvider>
    )
    insights(response("fresh", [CARD]))
    const { rerender } = render(wrap())
    insights(response("stale", [CARD]))
    generating({ isError: true })
    rerender(wrap())
    rerender(wrap())
    rerender(wrap())
    expect(mutate).toHaveBeenCalledTimes(1)
    expect(screen.getByRole("button", { name: "Regenerate" })).toBeEnabled()
    expect(
      screen.getByText("Couldn't regenerate insights."),
    ).toBeInTheDocument()
  })

  it("keeps its failures out of the toast and keys the run", () => {
    insights(response("fresh", [CARD]))
    renderView()
    expect(useGenerateInsights).toHaveBeenCalledWith(
      expect.objectContaining({
        mutation: expect.objectContaining({
          mutationKey: getGenerateInsightsMutationKey(),
          meta: { silentError: true },
        }),
      }),
    )
  })

  it("a remount while a run is in flight starts no second run", async () => {
    const client = new QueryClient()
    // The run an earlier mount of the page started, still waiting on the model.
    let finish: (value: unknown) => void = () => {}
    const gate = new Promise((resolve) => (finish = resolve))
    const pending = client
      .getMutationCache()
      .build(client, {
        mutationKey: getGenerateInsightsMutationKey(),
        mutationFn: () => gate,
      })
      .execute(undefined)
    await waitFor(() => expect(client.isMutating()).toBe(1))
    insights(response("stale", [CARD]))
    render(
      <QueryClientProvider client={client}>
        <InsightsView />
      </QueryClientProvider>,
    )
    expect(mutate).not.toHaveBeenCalled()
    expect(screen.getByRole("button", { name: "Generating…" })).toBeDisabled()
    finish(undefined)
    await pending
  })

  it("when that earlier run fails, the remounted page makes its own one attempt", async () => {
    const client = new QueryClient()
    let fail: (reason: unknown) => void = () => {}
    const gate = new Promise((_, reject) => (fail = reject))
    const pending = client
      .getMutationCache()
      .build(client, {
        mutationKey: getGenerateInsightsMutationKey(),
        mutationFn: () => gate,
      })
      .execute(undefined)
    await waitFor(() => expect(client.isMutating()).toBe(1))
    insights(response("none"))
    render(
      <QueryClientProvider client={client}>
        <InsightsView />
      </QueryClientProvider>,
    )
    expect(mutate).not.toHaveBeenCalled()
    fail(new Error("503"))
    await expect(pending).rejects.toThrow("503")
    await waitFor(() => expect(mutate).toHaveBeenCalledTimes(1))
  })
})
