import type { ApiRequest } from "@app/api-client"
import { z } from "zod"

/**
 * One event of POST /api/v1/chatbot/chat/{id}/stream.
 *
 * Mirrors `StreamResponse` in server/app/modules/conversation/schemas.py. It is
 * the one hand-written API payload schema in the app, and deliberately so:
 * routes tagged "streaming" are excluded from generation (orval.config.ts), and
 * the route's OpenAPI entry is held fixed (WS7), so no generated type exists.
 */
const StreamEventSchema = z.object({ content: z.string(), done: z.boolean() })
export type StreamEvent = z.infer<typeof StreamEventSchema>

/** The stream reported a failure, ended early, or sent something unreadable. */
export class StreamFailedError extends Error {
  constructor(message = "The chat stream failed") {
    super(message)
    this.name = "StreamFailedError"
  }
}

export type StreamChatOptions = {
  conversationId: string
  message: string
  /** useApiRequest's: it adds the session's token, and throws ApiError for a refused stream before anything is read. */
  request: ApiRequest
  signal: AbortSignal
}

/**
 * Send a message and yield the reply as it is written.
 *
 * The server reports a failure as a final event with `done: true` and
 * non-empty content (the shape is fixed), so that is thrown as
 * StreamFailedError; its text is never surfaced. Aborting `signal` closes the
 * connection, and the server then stops the model call.
 */
export async function* streamChat({
  conversationId,
  message,
  request,
  signal,
}: StreamChatOptions): AsyncGenerator<string> {
  const response = await request(
    `/api/v1/chatbot/chat/${conversationId}/stream`,
    {
      method: "POST",
      headers: { Accept: "text/event-stream" },
      body: JSON.stringify({ message }),
      signal,
    },
  )
  if (!response.body) throw new StreamFailedError("The response has no body")

  for await (const event of readEvents(response.body)) {
    if (event.done) {
      if (event.content !== "") throw new StreamFailedError()
      return
    }
    if (event.content) yield event.content
  }
  throw new StreamFailedError("The stream ended before it was done")
}

/** Parse server-sent events: frames end at a blank line; `:` lines are comments. */
export async function* readEvents(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<StreamEvent> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) return
      buffer += decoder.decode(value, { stream: true })
      let boundary = buffer.indexOf("\n\n")
      while (boundary !== -1) {
        const frame = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        const data = frame
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).replace(/^ /, ""))
          .join("\n")
        if (data) yield parseEvent(data)
        boundary = buffer.indexOf("\n\n")
      }
    }
  } finally {
    reader.cancel().catch(() => {})
  }
}

function parseEvent(data: string): StreamEvent {
  try {
    return StreamEventSchema.parse(JSON.parse(data))
  } catch {
    throw new StreamFailedError("The stream sent an unreadable event")
  }
}
