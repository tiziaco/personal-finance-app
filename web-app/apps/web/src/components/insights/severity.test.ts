import { describe, it, expect } from "vitest"
import type { InsightResponse } from "@app/api-client/types"
import { SEVERITY_ORDER, sortBySeverity } from "./severity"

const make = (summary: string, severity: InsightResponse["severity"]) =>
  ({
    summary,
    severity,
    narrative: "",
    period: "month",
    section: "spending",
  }) as InsightResponse

describe("sortBySeverity", () => {
  it("orders high to info", () => {
    expect(SEVERITY_ORDER).toEqual([
      "critical",
      "high",
      "medium",
      "low",
      "info",
    ])
    const sorted = sortBySeverity([
      make("a", "info"),
      make("b", "critical"),
      make("c", "medium"),
      make("d", "high"),
      make("e", "low"),
    ])
    expect(sorted.map((i) => i.summary)).toEqual(["b", "d", "c", "e", "a"])
  })

  it("is stable within a severity and does not mutate its input", () => {
    const input = [
      make("a", "low"),
      make("b", "high"),
      make("c", "low"),
      make("d", "high"),
    ]
    const sorted = sortBySeverity(input)
    expect(sorted.map((i) => i.summary)).toEqual(["b", "d", "a", "c"])
    expect(input.map((i) => i.summary)).toEqual(["a", "b", "c", "d"])
  })
})
