import type { ApiRequest } from "@app/api-client"
import type { ToolDisplay } from "@app/api-client/types"
import { z } from "zod"

/**
 * The display a finished tool call carries. Hand-written beside the events
 * (the generated client has the type, not a zod schema for it); checked
 * against the generated `ToolDisplay` so the two cannot drift.
 */
const ToolDisplaySchema = z.object({
  title: z.string(),
  period: z.string().nullable(),
  summary: z.array(
    z.object({
      kind: z.enum(["count", "money", "percent", "text"]),
      value: z.union([z.number(), z.string()]),
      label: z.string().nullish(),
    }),
  ),
  table: z
    .object({
      columns: z.array(
        z.object({
          key: z.string(),
          label: z.string(),
          kind: z.enum(["text", "money", "percent", "count", "date"]),
        }),
      ),
      rows: z.array(
        z.record(z.string(), z.union([z.string(), z.number(), z.null()])),
      ),
    })
    .nullable(),
}) satisfies z.ZodType<ToolDisplay>

/**
 * One event of POST /api/v1/chatbot/chat/{id}/stream.
 *
 * Mirrors the events in server/app/agents/chatbot/events.py (its docstring is
 * the wire description). It is the one hand-written API payload schema in the
 * app, and deliberately so: routes tagged "streaming" are excluded from
 * generation (orval.config.ts), so no generated type exists.
 */
const StreamEventSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("reasoning"), text: z.string() }),
  z.object({
    type: z.literal("tool_started"),
    id: z.string(),
    name: z.string(),
    title: z.string(),
  }),
  z.object({
    type: z.literal("tool_finished"),
    id: z.string(),
    ok: z.boolean(),
    display: ToolDisplaySchema.nullable(),
  }),
  z.object({ type: z.literal("text"), text: z.string() }),
  z.object({ type: z.literal("done"), stopped: z.boolean() }),
  z.object({ type: z.literal("error") }),
])
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
 * Send a message and yield its events as they arrive, `done` last.
 *
 * An `error` event is thrown as StreamFailedError (it carries no text to
 * surface), and so is a stream that ends without `done`. Aborting `signal`
 * closes the connection, and the server then stops the model call.
 */
export async function* streamChat({
  conversationId,
  message,
  request,
  signal,
}: StreamChatOptions): AsyncGenerator<StreamEvent> {
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
    if (event.type === "error") throw new StreamFailedError()
    yield event
    if (event.type === "done") return
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
