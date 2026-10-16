import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import {
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
})
