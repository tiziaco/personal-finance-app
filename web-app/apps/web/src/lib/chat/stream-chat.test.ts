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

const frame = (content: string, done = false) =>
  `data: ${JSON.stringify({ content, done })}\n\n`

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
    const whole = frame("Hello")
    const events = await collect(
      readEvents(bodyOf(whole.slice(0, 7), whole.slice(7))),
    )
    expect(events).toEqual([{ content: "Hello", done: false }])
  })

  it("splits several frames in one chunk", async () => {
    const events = await collect(readEvents(bodyOf(frame("a") + frame("b"))))
    expect(events.map((e) => e.content)).toEqual(["a", "b"])
  })

  it("ignores comment lines such as sse-starlette's ping", async () => {
    const events = await collect(
      readEvents(bodyOf(": ping - 2026-10-13\n\n" + frame("a"))),
    )
    expect(events).toEqual([{ content: "a", done: false }])
  })
})

describe("streamChat", () => {
  it("posts the message to the conversation's stream and yields the chunks", async () => {
    const request = respondWith(
      new Response(bodyOf(frame("Hel") + frame("lo") + frame("", true))),
    )
    await expect(run(request)).resolves.toEqual(["Hel", "lo"])
    expect(request).toHaveBeenCalledWith(
      "/api/v1/chatbot/chat/c1/stream",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ message: "hi" }),
      }),
    )
  })

  it("lets a refused stream's ApiError through", async () => {
    const request = vi.fn<ApiRequest>(async () => {
      throw new ApiError("HTTP 429", 429, null, null)
    })
    await expect(run(request)).rejects.toMatchObject({ status: 429 })
  })

  it("treats a final event carrying content as a failure", async () => {
    const request = respondWith(
      new Response(
        bodyOf(frame("partial") + frame("An error occurred.", true)),
      ),
    )
    await expect(run(request)).rejects.toBeInstanceOf(StreamFailedError)
  })

  // Review Focus 2: a dropped connection must not leave the UI "running".
  it("treats a stream that ends without done as a failure", async () => {
    const request = respondWith(new Response(bodyOf(frame("partial"))))
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
