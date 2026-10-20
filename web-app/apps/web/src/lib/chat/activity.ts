import type { Activity, ToolDisplay } from "@app/api-client/types"

import type { StreamEvent } from "./stream-chat"

export type ActivityPart =
  | { kind: "reasoning"; text: string }
  | {
      kind: "tool"
      id: string
      name: string
      title: string
      status: "running" | "ok" | "error"
      display: ToolDisplay | null
    }

/** When a reply's activity started and ended, in epoch milliseconds. */
export type Timing = { startedAt: number; endedAt: number }

/**
 * What the assistant did on the way to a reply. Timing is null for activity
 * rebuilt from history, which carries none, unless the reply finished on this
 * visit to the conversation.
 */
export type ActivityState = {
  parts: ActivityPart[]
  startedAt: number | null
  endedAt: number | null
  stopped: boolean
  /** The first text arrived: the block collapses itself. */
  answerStarted: boolean
}

export function emptyActivity(now: number): ActivityState {
  return {
    parts: [],
    startedAt: now,
    endedAt: null,
    stopped: false,
    answerStarted: false,
  }
}

export function activityReducer(
  state: ActivityState,
  event: StreamEvent,
  now: number,
): ActivityState {
  switch (event.type) {
    case "reasoning": {
      const last = state.parts.at(-1)
      if (last?.kind === "reasoning") {
        return {
          ...state,
          parts: [
            ...state.parts.slice(0, -1),
            { kind: "reasoning", text: last.text + event.text },
          ],
        }
      }
      return {
        ...state,
        parts: [...state.parts, { kind: "reasoning", text: event.text }],
      }
    }
    case "tool_started":
      return {
        ...state,
        parts: [
          ...state.parts,
          {
            kind: "tool",
            id: event.id,
            name: event.name,
            title: event.title,
            status: "running",
            display: null,
          },
        ],
      }
    case "tool_finished":
      // A finish with no start should not happen; it changes nothing.
      return {
        ...state,
        parts: state.parts.map((part) =>
          part.kind === "tool" && part.id === event.id
            ? {
                ...part,
                status: event.ok ? "ok" : "error",
                display: event.display,
              }
            : part,
        ),
      }
    case "text":
      return state.answerStarted ? state : { ...state, answerStarted: true }
    case "done":
      return { ...state, stopped: event.stopped, endedAt: now }
    case "error":
      return state
  }
}

/**
 * The block of a saved reply, already answered: no timing when reopened, or the
 * timing it streamed with when it finished on this visit.
 */
export function fromHistory(
  activity: Activity,
  timing?: Timing,
): ActivityState {
  return {
    parts: activity.parts.map((part): ActivityPart =>
      part.type === "reasoning"
        ? { kind: "reasoning", text: part.text }
        : {
            kind: "tool",
            id: part.id,
            name: part.name,
            title: part.title,
            status: part.ok ? "ok" : "error",
            display: part.display,
          },
    ),
    startedAt: timing?.startedAt ?? null,
    endedAt: timing?.endedAt ?? null,
    stopped: activity.stopped,
    answerStarted: true,
  }
}

/** The lookup the header names while working: the latest one still running, if any. */
export function runningLookup(
  state: ActivityState,
): Extract<ActivityPart, { kind: "tool" }> | undefined {
  return state.parts.findLast(
    (part): part is Extract<ActivityPart, { kind: "tool" }> =>
      part.kind === "tool" && part.status === "running",
  )
}
