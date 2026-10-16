import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen } from "@testing-library/react"
import {
  useGenerateInsights,
  useGetInsights,
} from "@app/api-client/endpoints/insights"
import { InsightsCallout } from "./insights-callout"

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

const refetch = vi.fn()

const card = (summary: string, severity: string, section = "spending") => ({
  section,
  severity,
  period: "month",
  summary,
  narrative: "n",
  key_figure: null,
  link: null,
})

const response = (status: string, cards: object[] = []) => ({
  status,
  generated_at: "2026-10-14T09:30:00Z",
  reference_month: "2026-09",
  month_to_date_through: "2026-10-14",
  insights: cards,
})

const insights = (data: object | undefined, state: object = {}) =>
  vi.mocked(useGetInsights).mockReturnValue({
    data,
    isError: false,
    refetch,
    ...state,
  } as unknown as ReturnType<typeof useGetInsights>)

beforeEach(() => {
  vi.clearAllMocks()
  vi.useFakeTimers({ toFake: ["Date"] })
  vi.setSystemTime(new Date("2026-10-16T12:00:00Z"))
})
afterEach(() => vi.useRealTimers())

describe("InsightsCallout", () => {
  it("shows the top three by severity", () => {
    insights(
      response("fresh", [
        card("Low one", "low"),
        card("Critical one", "critical", "anomalies"),
        card("Info one", "info"),
        card("High one", "high"),
        card("Medium one", "medium"),
      ]),
    )
    render(<InsightsCallout />)
    const summaries = screen
      .getAllByTestId("callout-summary")
      .map((e) => e.textContent)
    expect(summaries).toEqual(["Critical one", "High one", "Medium one"])
    expect(screen.getByText("Anomalies")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "View all" })).toHaveAttribute(
      "href",
      "/insights",
    )
  })

  it("tags a month-to-date insight with its month", () => {
    insights(
      response("fresh", [
        { ...card("Early", "high"), period: "month_to_date" },
      ]),
    )
    render(<InsightsCallout />)
    expect(screen.getByText(/so far$/)).toBeInTheDocument()
  })

  it("stale shows the note and a refresh link", () => {
    insights(response("stale", [card("Old", "high")]))
    render(<InsightsCallout />)
    expect(
      screen.getByText(
        "You've added or changed transactions since these were written.",
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: "Refresh insights" }),
    ).toHaveAttribute("href", "/insights")
    expect(screen.getByTestId("callout-cards")).toHaveClass("opacity-60")
  })

  it("stale from a new month says the month started", () => {
    insights({
      ...response("stale", [card("Old", "high")]),
      generated_at: "2026-09-30T23:30:00Z",
    })
    render(<InsightsCallout />)
    expect(
      screen.getByText("A new month has started since these were written."),
    ).toBeInTheDocument()
    expect(
      screen.queryByText(/You've added or changed transactions/),
    ).not.toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: "Refresh insights" }),
    ).toBeInTheDocument()
  })

  it("compares months in UTC, as the server does", () => {
    // 1 Oct 00:30 in UTC+2 is still 30 Sep in UTC: the month has started there, not here.
    vi.setSystemTime(new Date("2026-09-30T22:30:00Z"))
    insights({
      ...response("stale", [card("Old", "high")]),
      generated_at: "2026-09-30T10:00:00Z",
    })
    render(<InsightsCallout />)
    expect(
      screen.getByText(
        "You've added or changed transactions since these were written.",
      ),
    ).toBeInTheDocument()
  })

  it("fresh does not dim the cards", () => {
    insights(response("fresh", [card("New", "high")]))
    render(<InsightsCallout />)
    expect(screen.getByTestId("callout-cards")).not.toHaveClass("opacity-60")
  })

  it("none invites to open insights", () => {
    insights(response("none"))
    render(<InsightsCallout />)
    expect(
      screen.getByText("Your insights haven't been written yet."),
    ).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Open Insights" })).toHaveAttribute(
      "href",
      "/insights",
    )
  })

  it("fresh with nothing says so", () => {
    insights(response("fresh"))
    render(<InsightsCallout />)
    expect(
      screen.getByText("Nothing stands out this month."),
    ).toBeInTheDocument()
  })

  it("no_data renders nothing", () => {
    insights(response("no_data"))
    const { container } = render(<InsightsCallout />)
    expect(container).toBeEmptyDOMElement()
  })

  it("loads as a skeleton", () => {
    insights(undefined)
    render(<InsightsCallout />)
    expect(screen.getByTestId("callout-skeleton")).toBeInTheDocument()
  })

  it("an error offers a retry", () => {
    insights(undefined, { isError: true })
    render(<InsightsCallout />)
    expect(screen.getByText(/Couldn.t load your insights/)).toBeInTheDocument()
  })

  it("never generates", () => {
    insights(response("stale", [card("Old", "high")]))
    render(<InsightsCallout />)
    expect(useGenerateInsights).not.toHaveBeenCalled()
  })
})
