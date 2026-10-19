import { fireEvent, render, screen } from "@testing-library/react"
import type { ReactNode } from "react"
import { describe, expect, it, vi } from "vitest"

import { QueryGate } from "./query-gate"
import { Section } from "./section"

type Query = {
  data: string[] | undefined
  isError: boolean
  isPlaceholderData?: boolean
  refetch: () => unknown
}

function renderGate(
  query: Query,
  empty?: ReactNode | ((d: string[]) => ReactNode),
) {
  return render(
    <QueryGate
      query={query}
      what="things"
      skeleton={<div>loading</div>}
      isEmpty={(d) => d.length === 0}
      empty={empty ?? "Nothing here."}
    >
      {(d) => <div>{d.join(",")}</div>}
    </QueryGate>,
  )
}

describe("Section", () => {
  it("shows its title and children", () => {
    render(
      <Section title="Things">
        <div>body</div>
      </Section>,
    )
    expect(screen.getByText("Things")).toBeTruthy()
    expect(screen.getByText("body")).toBeTruthy()
  })
})

describe("QueryGate", () => {
  it("shows the skeleton while loading", () => {
    renderGate({ data: undefined, isError: false, refetch: vi.fn() })
    expect(screen.getByText("loading")).toBeTruthy()
  })

  it("shows one error and one retry when nothing loaded", () => {
    const refetch = vi.fn()
    renderGate({ data: undefined, isError: true, refetch })
    expect(screen.getAllByText(/Couldn't load things/)).toHaveLength(1)
    expect(screen.getAllByRole("button", { name: "Retry" })).toHaveLength(1)
    expect(screen.queryByText("loading")).toBeNull()
  })

  it("calls refetch on retry", () => {
    const refetch = vi.fn()
    renderGate({ data: undefined, isError: true, refetch })
    fireEvent.click(screen.getByRole("button", { name: "Retry" }))
    expect(refetch).toHaveBeenCalled()
  })

  it("keeps data when a refetch fails", () => {
    renderGate({ data: ["a", "b"], isError: true, refetch: vi.fn() })
    expect(screen.getByText("a,b")).toBeTruthy()
    expect(screen.queryByText(/Couldn't load/)).toBeNull()
  })

  it("shows the empty node once when empty", () => {
    renderGate({ data: [], isError: false, refetch: vi.fn() })
    expect(screen.getAllByText("Nothing here.")).toHaveLength(1)
  })

  it("gives the data to a function empty", () => {
    renderGate(
      { data: [], isError: false, refetch: vi.fn() },
      (d) => `Got ${d.length} things.`,
    )
    expect(screen.getByText("Got 0 things.")).toBeTruthy()
  })

  it("dims and marks busy while placeholder data shows", () => {
    renderGate({
      data: ["a"],
      isError: false,
      isPlaceholderData: true,
      refetch: vi.fn(),
    })
    const wrapper = screen.getByText("a").parentElement
    expect(wrapper?.getAttribute("aria-busy")).toBe("true")
    expect(wrapper?.className).toContain("opacity-60")
  })

  it("is not busy or dimmed once the data is real", () => {
    renderGate({
      data: ["a"],
      isError: false,
      isPlaceholderData: false,
      refetch: vi.fn(),
    })
    const wrapper = screen.getByText("a").parentElement
    expect(wrapper?.getAttribute("aria-busy")).toBe("false")
    expect(wrapper?.className).not.toContain("opacity-60")
  })

  it("a first load still shows the skeleton", () => {
    renderGate({
      data: undefined,
      isError: false,
      isPlaceholderData: false,
      refetch: vi.fn(),
    })
    expect(screen.getByText("loading")).toBeTruthy()
  })
})
