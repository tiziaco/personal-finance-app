import type { ChatMessage } from "@app/api-client/types"
import { describe, expect, it } from "vitest"

import { emptyActivity } from "./activity"
import {
  exchangeReducer,
  toThreadMessages,
  type Exchange,
  type ExchangeAction,
  type Send,
} from "./exchange"
import type { StreamEvent } from "./stream-chat"

const text = (t: string): StreamEvent => ({ type: "text", text: t })

const sendIn = (conversationId: string | null): Send => ({
  controller: new AbortController(),
  conversationId,
})

/** One reducer step that the test knows leaves an exchange open. */
const step = (state: Exchange | null, action: ExchangeAction) =>
  exchangeReducer(state, action) as Exchange

function started(send: Send, baseCount = 0): Exchange {
  return exchangeReducer(null, {
    type: "start",
    send,
    userText: "hi",
    baseCount,
    now: 0,
  }) as Exchange
}

describe("exchangeReducer", () => {
  it("start opens a running exchange, replacing any earlier one", () => {
    const first = started(sendIn("c1"))
    const second = sendIn("c1")
    const state = exchangeReducer(first, {
      type: "start",
      send: second,
      userText: "again",
      baseCount: 2,
      now: 7,
    })
    expect(state).toEqual({
      send: second,
      baseCount: 2,
      userText: "again",
      replyText: "",
      activity: emptyActivity(7),
      status: "running",
    })
  })

  it("an action from a send that is no longer the exchange's changes nothing", () => {
    const old = sendIn("c1")
    const state = started(sendIn("c1"))
    expect(
      exchangeReducer(state, {
        type: "event",
        send: old,
        event: text("x"),
        now: 0,
      }),
    ).toBe(state)
    expect(exchangeReducer(state, { type: "cleared", send: old })).toBe(state)
  })

  it("chunks append; stopped, failed and cleared end the exchange", () => {
    const send = sendIn("c1")
    let state = started(send)
    state = step(state, { type: "event", send, event: text("Hel"), now: 1 })
    state = step(state, { type: "event", send, event: text("lo"), now: 2 })
    expect(state.replyText).toBe("Hello")
    expect(exchangeReducer(state, { type: "stopped", send })?.status).toBe(
      "stopped",
    )
    expect(exchangeReducer(state, { type: "failed", send })?.status).toBe(
      "error",
    )
    expect(exchangeReducer(state, { type: "cleared", send })).toBeNull()
  })

  it("created swaps in the send that names the conversation", () => {
    const send = sendIn(null)
    const next = { ...send, conversationId: "c1" }
    const state = step(started(send), { type: "created", send, next })
    expect(state.send).toBe(next)
    // The pre-create send no longer owns the exchange.
    expect(
      exchangeReducer(state, { type: "event", send, event: text("x"), now: 0 }),
    ).toBe(state)
  })

  it("leaving drops another conversation's exchange, /chat included, and keeps its own", () => {
    const state = started(sendIn("c1"))
    expect(exchangeReducer(state, { type: "left", activeId: "c1" })).toBe(state)
    expect(exchangeReducer(state, { type: "left", activeId: "c2" })).toBeNull()
    expect(exchangeReducer(state, { type: "left", activeId: null })).toBeNull()
  })
})

describe("toThreadMessages", () => {
  const saved: ChatMessage[] = [
    { role: "user", content: "older", activity: null },
    {
      role: "assistant",
      content: "reply",
      activity: { parts: [{ type: "reasoning", text: "hm" }], stopped: false },
    },
    { role: "user", content: "hi", activity: null }, // the in-flight message, saved mid-stream
  ]

  it("slices the history at baseCount so a mid-stream refetch shows the user's message once", () => {
    const send = sendIn("c1")
    const exchange = { ...started(send, 2), replyText: "Hel" }
    const messages = toThreadMessages(saved, exchange, "c1", "c1")
    expect(messages.map((m) => m.content)).toEqual([
      "older",
      "reply",
      "hi",
      "Hel",
    ])
    expect(messages.at(-1)?.status).toEqual({ type: "running" })
  })

  it("marks a stopped reply cancelled and a failed one an error", () => {
    const exchange = started(sendIn("c1"), 3)
    const last = (status: Exchange["status"]) =>
      toThreadMessages(saved, { ...exchange, status }, "c1", "c1").at(-1)
        ?.status
    expect(last("stopped")).toEqual({ type: "incomplete", reason: "cancelled" })
    expect(last("error")).toEqual({ type: "incomplete", reason: "error" })
  })

  it("shows a created conversation's exchange on /chat until the URL catches up", () => {
    const exchange = started(sendIn("c1"))
    expect(toThreadMessages([], exchange, null, "c1")).toHaveLength(2)
  })

  it("hides another conversation's exchange and shows the history whole", () => {
    const exchange = started(sendIn("c1"), 1)
    expect(toThreadMessages(saved, exchange, "c2", "c2")).toHaveLength(3)
  })

  it("puts history activity in metadata.custom.activity", () => {
    const messages = toThreadMessages(saved, null, "c1", "c1")
    expect(messages[0].metadata).toBeUndefined()
    expect(messages[1].metadata?.custom?.activity).toMatchObject({
      parts: [{ kind: "reasoning", text: "hm" }],
      startedAt: null,
      answerStarted: true,
    })
  })

  it("carries the in-flight activity, advanced by events", () => {
    const send = sendIn("c1")
    const exchange = step(started(send), {
      type: "event",
      send,
      event: { type: "reasoning", text: "thinking" },
      now: 5,
    })
    const last = toThreadMessages([], exchange, "c1", "c1").at(-1)
    expect(last?.metadata?.custom?.activity).toMatchObject({
      parts: [{ kind: "reasoning", text: "thinking" }],
      startedAt: 0,
    })
  })
})
