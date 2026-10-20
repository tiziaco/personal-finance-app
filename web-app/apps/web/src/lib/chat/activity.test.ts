import { describe, expect, it } from "vitest"

import {
  activityReducer,
  runningLookup,
  emptyActivity,
  fromHistory,
} from "./activity"
import type { StreamEvent } from "./stream-chat"

const run = (events: StreamEvent[], start = 1000) =>
  events.reduce(
    (state, event, i) => activityReducer(state, event, start + i),
    emptyActivity(start),
  )

const display = {
  title: "Spending by category",
  period: "Sep 2026",
  summary: [{ kind: "count" as const, value: 14, label: "categories" }],
  table: null,
}

describe("activityReducer", () => {
  it("appends reasoning deltas into one part", () => {
    const state = run([
      { type: "reasoning", text: "Let me " },
      { type: "reasoning", text: "check." },
    ])
    expect(state.parts).toEqual([{ kind: "reasoning", text: "Let me check." }])
  })

  it("starts a new reasoning part after a tool row", () => {
    const state = run([
      { type: "reasoning", text: "a" },
      { type: "tool_started", id: "t1", name: "n", title: "T" },
      { type: "reasoning", text: "b" },
    ])
    expect(state.parts.map((p) => p.kind)).toEqual([
      "reasoning",
      "tool",
      "reasoning",
    ])
  })

  it("marks a tool ok with its display on tool_finished", () => {
    const state = run([
      { type: "tool_started", id: "t1", name: "spending", title: "Spending" },
      { type: "tool_started", id: "t2", name: "other", title: "Other" },
      { type: "tool_finished", id: "t2", ok: false, display: null },
      { type: "tool_finished", id: "t1", ok: true, display },
    ])
    expect(state.parts).toMatchObject([
      { id: "t1", status: "ok", display },
      { id: "t2", status: "error", display: null },
    ])
  })

  it("ignores a tool_finished with no tool_started", () => {
    const before = emptyActivity(0)
    const after = activityReducer(
      before,
      { type: "tool_finished", id: "x", ok: true, display },
      1,
    )
    expect(after.parts).toEqual([])
  })

  it("sets answerStarted on the first text event", () => {
    expect(run([{ type: "reasoning", text: "a" }]).answerStarted).toBe(false)
    expect(run([{ type: "text", text: "Hi" }]).answerStarted).toBe(true)
  })

  it("keeps stopped from done and stamps endedAt", () => {
    const state = run([{ type: "done", stopped: true }], 1000)
    expect(state.stopped).toBe(true)
    expect(state.endedAt).toBe(1000)
    expect(run([{ type: "done", stopped: false }]).stopped).toBe(false)
  })
})

describe("fromHistory", () => {
  it("rebuilds parts without timing, answered, tools by ok", () => {
    const state = fromHistory({
      stopped: true,
      parts: [
        { type: "reasoning", text: "hm" },
        { type: "tool", id: "t1", name: "n", title: "T", ok: true, display },
        {
          type: "tool",
          id: "t2",
          name: "n",
          title: "U",
          ok: false,
          display: null,
        },
      ],
    })
    expect(state).toEqual({
      parts: [
        { kind: "reasoning", text: "hm" },
        {
          kind: "tool",
          id: "t1",
          name: "n",
          title: "T",
          status: "ok",
          display,
        },
        {
          kind: "tool",
          id: "t2",
          name: "n",
          title: "U",
          status: "error",
          display: null,
        },
      ],
      startedAt: null,
      endedAt: null,
      stopped: true,
      answerStarted: true,
    })
  })
})

describe("runningLookup", () => {
  it("is none until a tool runs, then the running tool, then none again", () => {
    expect(runningLookup(emptyActivity(0))).toBeUndefined()
    const running = run([
      {
        type: "tool_started",
        id: "t1",
        name: "n",
        title: "Spending by category",
      },
    ])
    expect(runningLookup(running)).toMatchObject({
      id: "t1",
      title: "Spending by category",
    })
    const finished = activityReducer(
      running,
      { type: "tool_finished", id: "t1", ok: true, display },
      5,
    )
    expect(runningLookup(finished)).toBeUndefined()
  })
})

describe("fromHistory with the timing of a reply finished on this visit", () => {
  it("keeps the times, so the header still reads 'Worked for'", () => {
    const activity = fromHistory(
      { parts: [], stopped: false },
      { startedAt: 1000, endedAt: 5000 },
    )
    expect(activity).toMatchObject({ startedAt: 1000, endedAt: 5000 })
  })
})
