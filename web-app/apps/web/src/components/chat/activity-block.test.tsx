import { act, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { ActivityPart, ActivityState } from "@/lib/chat/activity"

import { ActivityBlock } from "./activity-block"

const tool = (
  over: Partial<Extract<ActivityPart, { kind: "tool" }>> = {},
): ActivityPart => ({
  kind: "tool",
  id: "t1",
  name: "spending_by_category",
  title: "Spending by category",
  status: "ok",
  display: {
    title: "Spending by category",
    period: "Sep 2026",
    summary: [
      { kind: "count", value: 14, label: "categories" },
      { kind: "total", value: "2184.00" },
    ],
    table: {
      columns: [
        { key: "name", label: "Category", kind: "text" },
        { key: "spent", label: "Spent", kind: "total" },
        { key: "net", label: "Net", kind: "net" },
        { key: "amount", label: "Amount", kind: "transaction" },
        { key: "share", label: "Share", kind: "share" },
        { key: "change", label: "Change", kind: "change" },
      ],
      rows: [
        {
          name: "Housing",
          spent: "950.00",
          net: "-12.50",
          amount: "-40.00",
          share: 43.5,
          change: 12.04,
        },
        {
          name: "Pets",
          spent: "30.00",
          net: "30.00",
          amount: "25.00",
          share: null,
          change: "new",
        },
        {
          name: "Travel",
          spent: "10.00",
          net: "0.00",
          amount: "0.00",
          share: 0.4,
          change: null,
        },
      ],
    },
  },
  ...over,
})

const state = (over: Partial<ActivityState> = {}): ActivityState => ({
  parts: [tool(), tool({ id: "t2", title: "Top merchants" })],
  startedAt: 1_000_000,
  endedAt: null,
  stopped: false,
  answerStarted: false,
  ...over,
})

afterEach(() => vi.useRealTimers())

describe("ActivityBlock", () => {
  it("shows the current step and a running timer while working", () => {
    vi.useFakeTimers({ now: 1_000_000 })
    render(
      <ActivityBlock
        activity={state({
          parts: [
            tool(),
            tool({
              id: "t2",
              title: "Top merchants",
              status: "running",
              display: null,
            }),
          ],
        })}
      />,
    )
    expect(screen.getByText("Looking up top merchants…")).toBeInTheDocument()
    expect(screen.getByText("0:00")).toBeInTheDocument()
    act(() => {
      vi.advanceTimersByTime(3000)
    })
    expect(screen.getByText("0:03")).toBeInTheDocument()
    // Open while working: the rows show.
    expect(screen.getByText("Spending by category")).toBeInTheDocument()
  })

  it("clears its interval once the activity has ended", () => {
    vi.useFakeTimers({ now: 1_000_000 })
    const clear = vi.spyOn(globalThis, "clearInterval")
    const { rerender } = render(<ActivityBlock activity={state()} />)
    rerender(<ActivityBlock activity={state({ endedAt: 1_002_000 })} />)
    expect(clear).toHaveBeenCalled()
    act(() => {
      vi.advanceTimersByTime(5000)
    })
    expect(screen.getByText("Worked for 2s · 2 lookups")).toBeInTheDocument()
  })

  it("collapses to 'Worked for 4s · 2 lookups' once the answer starts", () => {
    vi.useFakeTimers({ now: 1_000_000 })
    const { rerender } = render(<ActivityBlock activity={state()} />)
    act(() => {
      vi.advanceTimersByTime(4000)
    })
    rerender(<ActivityBlock activity={state({ answerStarted: true })} />)
    expect(screen.getByText("Worked for 4s · 2 lookups")).toBeInTheDocument()
    expect(screen.queryByText("Top merchants")).not.toBeInTheDocument()
    // The frozen duration does not keep growing.
    act(() => {
      vi.advanceTimersByTime(5000)
    })
    expect(screen.getByText("Worked for 4s · 2 lookups")).toBeInTheDocument()
  })

  it("opens a tool row to a table formatted as the analytics page formats it", async () => {
    const user = userEvent.setup()
    render(
      <ActivityBlock
        activity={state({ endedAt: 1_004_000, answerStarted: true })}
      />,
    )
    await user.click(screen.getByRole("button", { name: /Worked for 4s/ }))
    const row = screen.getAllByRole("button", {
      name: /Spending by category/,
    })[0]
    expect(row).toHaveAttribute("aria-expanded", "false")
    expect(row).toHaveTextContent("Sep 2026")
    expect(row).toHaveTextContent("14 categories · €2,184.00")
    await user.click(row)
    expect(row).toHaveAttribute("aria-expanded", "true")
    // A total unsigned; a net signed and coloured; a transaction signed, income coloured.
    expect(screen.getAllByText("€950.00")[0]).not.toHaveClass("text-negative")
    expect(screen.getAllByText("−€12.50")[0]).toHaveClass("text-negative")
    expect(screen.getAllByText("+€30.00")[0]).toHaveClass("text-positive")
    expect(screen.getAllByText("−€40.00")[0]).not.toHaveClass("text-negative")
    expect(screen.getAllByText("+€25.00")[0]).toHaveClass("text-positive")
    expect(screen.getAllByText("43.5%")[0]).toBeInTheDocument()
    expect(screen.getAllByText("–")[0]).toBeInTheDocument()
    // A change as the category ranking shows it: up in spending is bad; "new"; a dash with nothing to compare.
    const up = screen.getAllByText(/12\.0% more/)[0]
    expect(up).toHaveTextContent("▲ 12.0% more")
    expect(up).toHaveAttribute("data-tone", "bad")
    expect(screen.getAllByText("new")[0]).toBeInTheDocument()
    expect(screen.getAllByText("—")[0]).toBeInTheDocument()
  })

  it("words a summary's savings rate and weekend bias as the analytics page does", () => {
    render(
      <ActivityBlock
        activity={state({
          parts: [
            tool({
              display: {
                title: "Spending patterns",
                period: "Sep 2026",
                summary: [
                  { kind: "rate", value: -8.25, label: "savings rate" },
                  { kind: "share", value: 61.04, label: "top 5 share" },
                  {
                    kind: "weekendBias",
                    value: 12.5,
                    label: "weekend vs weekday, per day",
                  },
                ],
                table: null,
              },
            }),
          ],
        })}
      />,
    )
    const row = screen.getByRole("button", { name: /Spending by category/ })
    // formatPct, as the analytics page's Rate: one decimal, the locale's minus.
    expect(row).toHaveTextContent(
      "-8.3% · 61.0% · Weekend days cost you 12.5% more than weekdays",
    )
    expect(screen.getByText("-8.3%")).toHaveAttribute("data-tone", "bad")
  })

  it("reads 'Stopped after 3s' for a stopped exchange", () => {
    render(
      <ActivityBlock activity={state({ endedAt: 1_003_000, stopped: true })} />,
    )
    expect(screen.getByText("Stopped after 3s")).toBeInTheDocument()
  })

  it("from history reads '2 lookups' with no timer", () => {
    render(
      <ActivityBlock
        activity={state({ startedAt: null, answerStarted: true })}
      />,
    )
    expect(screen.getByText("2 lookups")).toBeInTheDocument()
    expect(screen.queryByText(/\d:\d\d/)).not.toBeInTheDocument()
  })

  it("from history reads 'Stopped · 1 lookup' when the server stopped it", () => {
    render(
      <ActivityBlock
        activity={state({
          parts: [tool()],
          startedAt: null,
          answerStarted: true,
          stopped: true,
        })}
      />,
    )
    expect(screen.getByText("Stopped · 1 lookup")).toBeInTheDocument()
  })

  it("renders tool rows only when there is no reasoning", async () => {
    const user = userEvent.setup()
    render(
      <ActivityBlock
        activity={state({ answerStarted: true, startedAt: null })}
      />,
    )
    await user.click(screen.getByRole("button", { name: "2 lookups" }))
    expect(screen.getAllByText("tool")).toHaveLength(2)
    expect(document.querySelector(".italic")).toBeNull()
  })

  it("shows reasoning as muted italic text", () => {
    render(
      <ActivityBlock
        activity={state({
          parts: [
            { kind: "reasoning", text: "Last month is September." },
            tool(),
          ],
        })}
      />,
    )
    expect(
      screen.getByText("Last month is September.").closest(".italic"),
    ).toHaveClass("text-muted-foreground")
  })

  it("renders reasoning as Markdown: bold without asterisks, paragraphs apart", () => {
    render(
      <ActivityBlock
        activity={state({
          parts: [
            {
              kind: "reasoning",
              text: "**Planning the lookup**\n\nI need September's spending.",
            },
            tool(),
          ],
        })}
      />,
    )
    expect(screen.queryByText(/\*\*/)).not.toBeInTheDocument()
    expect(screen.getByText("Planning the lookup").tagName).toBe("STRONG")
    expect(screen.getByText("I need September's spending.").tagName).toBe("P")
  })

  it("shows a failed lookup as failed, with no table", async () => {
    const user = userEvent.setup()
    render(
      <ActivityBlock
        activity={state({
          parts: [tool({ status: "error", display: null })],
          endedAt: 1_001_000,
          stopped: true,
        })}
      />,
    )
    await user.click(screen.getByRole("button", { name: /Stopped/ }))
    expect(screen.getByText("Couldn't load")).toBeInTheDocument()
    const row = screen.getByRole("button", { name: /Spending by category/ })
    await user.click(row)
    expect(row).toHaveAttribute("aria-expanded", "false")
    expect(screen.queryByRole("table")).not.toBeInTheDocument()
  })

  it("renders nothing without parts", () => {
    const { container } = render(
      <ActivityBlock activity={state({ parts: [] })} />,
    )
    expect(container).toBeEmptyDOMElement()
  })
})
