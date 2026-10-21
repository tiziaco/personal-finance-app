import { afterEach, describe, expect, it, vi } from "vitest"
import { ApiError, type ApiRequest } from "@app/api-client"

import { readEvents, streamChat, StreamFailedError } from "./stream-chat"

function bodyOf(...chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  })
}

const frame = (event: object) => `data: ${JSON.stringify(event)}\n\n`
const text = (t: string) => frame({ type: "text", text: t })
const done = (stopped = false) => frame({ type: "done", stopped })

async function collect<T>(gen: AsyncGenerator<T>): Promise<T[]> {
  const out: T[] = []
  for await (const item of gen) out.push(item)
  return out
}

function respondWith(response: Response) {
  return vi.fn<ApiRequest>(async () => response)
}

function run(request: ApiRequest, signal = new AbortController().signal) {
  return collect(
    streamChat({ conversationId: "c1", message: "hi", request, signal }),
  )
}

afterEach(() => vi.restoreAllMocks())

describe("readEvents", () => {
  it("joins a frame split across chunks", async () => {
    const whole = text("Hello")
    const events = await collect(
      readEvents(bodyOf(whole.slice(0, 7), whole.slice(7))),
    )
    expect(events).toEqual([{ type: "text", text: "Hello" }])
  })

  it("splits several frames in one chunk", async () => {
    const events = await collect(readEvents(bodyOf(text("a") + text("b"))))
    expect(events).toEqual([
      { type: "text", text: "a" },
      { type: "text", text: "b" },
    ])
  })

  it("ignores comment lines such as sse-starlette's ping", async () => {
    const events = await collect(
      readEvents(bodyOf(": ping - 2026-10-13\n\n" + text("a"))),
    )
    expect(events).toEqual([{ type: "text", text: "a" }])
  })
})

describe("streamChat", () => {
  it("posts the message to the conversation's stream and yields every event, done last", async () => {
    const tool = { type: "tool_started", id: "t1", name: "n", title: "T" }
    const request = respondWith(
      new Response(
        bodyOf(
          frame({ type: "reasoning", text: "hm" }) +
            frame(tool) +
            text("Hel") +
            text("lo") +
            done(true),
        ),
      ),
    )
    await expect(run(request)).resolves.toEqual([
      { type: "reasoning", text: "hm" },
      tool,
      { type: "text", text: "Hel" },
      { type: "text", text: "lo" },
      { type: "done", stopped: true },
    ])
    expect(request).toHaveBeenCalledWith(
      "/api/v1/chatbot/chat/c1/stream",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ message: "hi" }),
      }),
    )
  })

  it("parses a tool_finished with its display", async () => {
    const display = {
      title: "T",
      period: null,
      summary: [{ kind: "total", value: "12.50", label: null }],
      table: {
        columns: [{ key: "a", label: "A", kind: "text" }],
        rows: [{ a: "x" }],
      },
    }
    const event = { type: "tool_finished", id: "t1", ok: true, display }
    const request = respondWith(new Response(bodyOf(frame(event) + done())))
    await expect(run(request)).resolves.toEqual([
      event,
      { type: "done", stopped: false },
    ])
  })

  it("lets a refused stream's ApiError through", async () => {
    const request = vi.fn<ApiRequest>(async () => {
      throw new ApiError("HTTP 429", 429, null, null)
    })
    await expect(run(request)).rejects.toMatchObject({ status: 429 })
  })

  it("throws StreamFailedError on an error event", async () => {
    const request = respondWith(
      new Response(bodyOf(text("partial") + frame({ type: "error" }))),
    )
    await expect(run(request)).rejects.toBeInstanceOf(StreamFailedError)
  })

  // Review Focus 2: a dropped connection must not leave the UI "running".
  it("treats a stream that ends without done as a failure", async () => {
    const request = respondWith(new Response(bodyOf(text("partial"))))
    await expect(run(request)).rejects.toBeInstanceOf(StreamFailedError)
  })

  it("treats a malformed event as a failure", async () => {
    const request = respondWith(new Response(bodyOf('data: {"nope": 1}\n\n')))
    await expect(run(request)).rejects.toBeInstanceOf(StreamFailedError)
  })

  it("stops reading when aborted", async () => {
    const controller = new AbortController()
    const request = vi.fn<ApiRequest>(
      (_url, init) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () =>
            reject(new DOMException("aborted", "AbortError")),
          )
        }),
    )
    const pending = run(request, controller.signal)
    controller.abort()
    await expect(pending).rejects.toMatchObject({ name: "AbortError" })
  })
})
