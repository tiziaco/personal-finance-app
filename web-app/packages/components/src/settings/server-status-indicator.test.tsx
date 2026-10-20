import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { ServerStatusIndicator } from "./server-status-indicator"

function readiness(status: string) {
  return {
    status,
    version: "1.2.3",
    environment: "development",
    timestamp: "2026-09-16T12:00:00+00:00",
    components: {
      api: "healthy",
      database: { status: "healthy" },
      agents: { chatbot: { ready: true } },
    },
  }
}

/** The status dot carries its state in a Tailwind colour class. */
function dotClasses() {
  return document.querySelector("div.size-2.rounded-full")?.className ?? ""
}

describe("ServerStatusIndicator", () => {
  it("shows a loading placeholder", () => {
    render(<ServerStatusIndicator isLoading error={undefined} />)

    expect(screen.getByText("Loading...")).toBeInTheDocument()
  })

  it("is green and pinging when healthy", () => {
    render(
      <ServerStatusIndicator
        status={readiness("healthy")}
        isLoading={false}
        error={undefined}
      />,
    )

    expect(dotClasses()).toContain("bg-positive")
    expect(document.querySelector(".animate-ping")).not.toBeNull()
    expect(screen.getByText("v1.2.3")).toBeInTheDocument()
  })

  it("is yellow and still when degraded", () => {
    render(
      <ServerStatusIndicator
        status={readiness("degraded")}
        isLoading={false}
        error={undefined}
      />,
    )

    expect(dotClasses()).toContain("bg-(--warning-500)")
    expect(document.querySelector(".animate-ping")).toBeNull()
  })

  it("is red for any other status", () => {
    render(
      <ServerStatusIndicator
        status={readiness("unhealthy")}
        isLoading={false}
        error={undefined}
      />,
    )

    expect(dotClasses()).toContain("bg-negative")
  })

  it("is red with v0.0.0 when there is no status", () => {
    render(<ServerStatusIndicator isLoading={false} error={undefined} />)

    expect(dotClasses()).toContain("bg-negative")
    expect(screen.getByText("v0.0.0")).toBeInTheDocument()
  })

  it("is red when an error is present even beside a healthy payload", () => {
    // `error || !status` is tested first; useServerStatus clears the error
    // when it recovers a degraded body, or the dot would stay red.
    render(
      <ServerStatusIndicator
        status={readiness("healthy")}
        isLoading={false}
        error={new Error("boom")}
      />,
    )

    expect(dotClasses()).toContain("bg-negative")
  })

  it("no pulsing ring when a healthy status is stale behind an error", () => {
    render(
      <ServerStatusIndicator
        status={readiness("healthy")}
        isLoading={false}
        error={new Error("down")}
      />,
    )

    expect(dotClasses()).toContain("bg-negative")
    expect(document.querySelector(".animate-ping")).toBeNull()
  })

  it("has no hover card without showDetail", () => {
    render(
      <ServerStatusIndicator
        status={readiness("healthy")}
        isLoading={false}
        error={undefined}
      />,
    )

    expect(
      document.querySelector('[data-slot="hover-card-trigger"]'),
    ).toBeNull()
  })

  it("wraps the indicator in a hover card with showDetail", () => {
    render(
      <ServerStatusIndicator
        status={readiness("healthy")}
        isLoading={false}
        error={undefined}
        showDetail
      />,
    )

    expect(
      document.querySelector('[data-slot="hover-card-trigger"]'),
    ).not.toBeNull()
  })
})
