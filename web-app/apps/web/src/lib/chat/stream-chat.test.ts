import { afterEach, describe, expect, it, vi } from "vitest"
import { ApiError } from "@app/api-client"

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

function mockFetch(response: Response) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(response)
}

function run(signal = new AbortController().signal) {
  return collect(
    streamChat({ conversationId: "c1", message: "hi", token: "tok", signal }),
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
  it("posts the message with the bearer token and yields the chunks", async () => {
    const spy = mockFetch(
      new Response(bodyOf(frame("Hel") + frame("lo") + frame("", true))),
    )
    await expect(run()).resolves.toEqual(["Hel", "lo"])

    const [url, init] = spy.mock.calls[0]
    expect(String(url)).toMatch(/\/api\/v1\/chatbot\/chat\/c1\/stream$/)
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer tok")
    expect(init?.body).toBe(JSON.stringify({ message: "hi" }))
  })

  it("throws ApiError with the status on a non-2xx response", async () => {
    mockFetch(new Response("slow down", { status: 429 }))
    await expect(run()).rejects.toMatchObject({
      name: "ApiError",
      status: 429,
    })
    await expect(run()).rejects.toBeInstanceOf(ApiError)
  })

  it("treats a final event carrying content as a failure", async () => {
    mockFetch(
      new Response(
        bodyOf(frame("partial") + frame("An error occurred.", true)),
      ),
    )
    await expect(run()).rejects.toBeInstanceOf(StreamFailedError)
  })

  // Review Focus 2: a dropped connection must not leave the UI "running".
  it("treats a stream that ends without done as a failure", async () => {
    mockFetch(new Response(bodyOf(frame("partial"))))
    await expect(run()).rejects.toBeInstanceOf(StreamFailedError)
  })

  it("treats a malformed event as a failure", async () => {
    mockFetch(new Response(bodyOf('data: {"nope": 1}\n\n')))
    await expect(run()).rejects.toBeInstanceOf(StreamFailedError)
  })

  it("stops reading when aborted", async () => {
    const controller = new AbortController()
    vi.spyOn(globalThis, "fetch").mockImplementation(
      (_url, init) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () =>
            reject(new DOMException("aborted", "AbortError")),
          )
        }),
    )
    const pending = run(controller.signal)
    controller.abort()
    await expect(pending).rejects.toMatchObject({ name: "AbortError" })
  })
})
