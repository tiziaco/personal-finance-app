import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, within } from "@testing-library/react"
import { useGetBehaviour } from "@app/api-client/endpoints/analytics"
import type { BehaviourResponse } from "@app/api-client/types"
import { formatAmount } from "@/components/transactions/format"
import { SeasonalityTab } from "./seasonality-tab"
import { formatPeriod } from "./format"

vi.mock("@app/api-client/endpoints/analytics", async (orig) => ({
  ...(await orig<typeof import("@app/api-client/endpoints/analytics")>()),
  useGetBehaviour: vi.fn(),
}))
// jsdom can't lay out SVG.
vi.mock("./seasonality-charts", () => ({
  WeekdayChart: ({ points }: { points: unknown[] }) => (
    <div data-testid="weekday-chart">{points.length} points</div>
  ),
  MonthOfYearChart: ({ points }: { points: unknown[] }) => (
    <div data-testid="month-chart">{points.length} points</div>
  ),
}))

const refetch = vi.fn()
const NAMES = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
]

const BEHAVIOUR = {
  date_from: "2024-03-01",
  date_to: "2026-09-30",
  by_weekday: NAMES.map((name, i) => ({
    weekday: i,
    name,
    total: "300.00",
    count: 10,
    days: 20,
    per_day: "15.00",
    average: "30.00",
    share_pct: 14.3,
  })),
  weekday: { days: 100, per_day: "20.00", total: "2000.00" },
  weekend: { days: 40, per_day: "24.60", total: "984.00" },
  weekend_bias_pct: 23,
  seasonality: Array.from({ length: 12 }, (_, i) => ({
    month: i + 1,
    average_spend: "100.00",
    index: 100,
    years: 2,
  })),
  stability: [],
  stable_share_pct: 0,
  moderate_share_pct: 0,
  volatile_share_pct: 0,
  expense_change_pct: null,
} as BehaviourResponse

const behaviour = (state: object) =>
  vi.mocked(useGetBehaviour).mockReturnValue({
    data: undefined,
    isError: false,
    refetch,
    ...state,
  } as unknown as ReturnType<typeof useGetBehaviour>)

beforeEach(() => {
  vi.clearAllMocks()
  behaviour({ data: BEHAVIOUR })
})

const card = (title: string) =>
  screen.getByText(title).closest('[data-slot="card"]') as HTMLElement

describe("SeasonalityTab", () => {
  it("captions the span", () => {
    render(<SeasonalityTab />)
    const caption = screen.getByText(/^Based on/)
    expect(caption.textContent).toBe(
      `Based on ${formatPeriod("2024-03-01", "2026-09-30")}`,
    )
  })

  it("compares weekdays and weekend", () => {
    const { unmount } = render(<SeasonalityTab />)
    const part = within(card("Weekdays vs weekend"))
    expect(part.getByText(formatAmount("20.00"))).toBeInTheDocument()
    expect(part.getByText(formatAmount("24.60"))).toBeInTheDocument()
    expect(part.getAllByText("per day")).toHaveLength(2)
    expect(
      screen.getByText("Weekend days cost you 23.0% more than weekdays"),
    ).toBeInTheDocument()
    unmount()

    behaviour({ data: { ...BEHAVIOUR, weekend_bias_pct: -10 } })
    const second = render(<SeasonalityTab />)
    expect(
      screen.getByText("Weekend days cost you 10.0% less than weekdays"),
    ).toBeInTheDocument()
    second.unmount()

    behaviour({ data: { ...BEHAVIOUR, weekend_bias_pct: 0 } })
    const third = render(<SeasonalityTab />)
    expect(
      screen.getByText("Weekend and weekday days cost the same"),
    ).toBeInTheDocument()
    third.unmount()

    behaviour({ data: { ...BEHAVIOUR, weekend_bias_pct: null } })
    render(<SeasonalityTab />)
    expect(screen.queryByText(/Weekend days cost/)).toBeNull()
    expect(screen.queryByText(/cost the same/)).toBeNull()
  })

  it("says a finished month is needed when no month has years", () => {
    behaviour({
      data: {
        ...BEHAVIOUR,
        seasonality: BEHAVIOUR.seasonality.map((m) => ({ ...m, years: 0 })),
      },
    })
    render(<SeasonalityTab />)
    expect(
      within(card("Average spend by month of year")).getByText(
        "Needs at least one finished month.",
      ),
    ).toBeInTheDocument()
    expect(screen.queryByTestId("month-chart")).toBeNull()
  })

  it("draws the month chart when one month has years", () => {
    behaviour({
      data: {
        ...BEHAVIOUR,
        seasonality: BEHAVIOUR.seasonality.map((m, i) => ({
          ...m,
          years: i === 0 ? 1 : 0,
        })),
      },
    })
    render(<SeasonalityTab />)
    expect(screen.getByTestId("month-chart")).toBeInTheDocument()
    expect(screen.queryByText("Needs at least one finished month.")).toBeNull()
  })

  it("shows the weekday table and both charts", () => {
    render(<SeasonalityTab />)
    expect(screen.getByTestId("weekday-chart")).toHaveTextContent("7 points")
    expect(screen.getByTestId("month-chart")).toHaveTextContent("12 points")
    expect(
      within(card("Average spend per day, by day of week")).getAllByText(
        "Monday",
      ).length,
    ).toBeGreaterThan(0)
  })

  it("labels every figure as an average", () => {
    render(<SeasonalityTab />)
    expect(
      screen.getByText("Average spend by month of year"),
    ).toBeInTheDocument()
    const list = card("Average spend per day, by day of week").querySelector(
      "ul",
    ) as HTMLElement
    expect(list).toHaveTextContent(`${formatAmount("15.00")} per day`)
    expect(list).toHaveTextContent("10 purchases")
  })

  it("does not pluralise one purchase", () => {
    behaviour({
      data: {
        ...BEHAVIOUR,
        by_weekday: BEHAVIOUR.by_weekday.map((d) => ({ ...d, count: 1 })),
      },
    })
    render(<SeasonalityTab />)
    expect(screen.queryByText(/1 purchases/)).toBeNull()
    expect(screen.getAllByText(/1 purchase ·/).length).toBeGreaterThan(0)
  })

  it("calls behaviour with no params", () => {
    render(<SeasonalityTab />)
    expect(vi.mocked(useGetBehaviour).mock.calls[0][0]).toBeUndefined()
  })

  it("shows the empty state", () => {
    behaviour({ data: { ...BEHAVIOUR, date_from: null, date_to: null } })
    render(<SeasonalityTab />)
    expect(screen.getAllByText("No spending yet.")).toHaveLength(1)
    expect(screen.queryByText(/^Based on/)).toBeNull()
  })

  it("keeps showing data when a refetch fails", () => {
    behaviour({ data: BEHAVIOUR, isError: true })
    render(<SeasonalityTab />)
    expect(screen.getByTestId("weekday-chart")).toBeInTheDocument()
  })
})
