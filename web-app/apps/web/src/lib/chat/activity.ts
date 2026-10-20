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

/**
 * What the assistant did on the way to a reply. Timing is null for activity
 * rebuilt from history, which carries none.
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

/** The block of a reply reopened from history: no timing, already answered. */
export function fromHistory(activity: Activity): ActivityState {
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
    startedAt: null,
    endedAt: null,
    stopped: activity.stopped,
    answerStarted: true,
  }
}

/** The header's live label: the running tool if there is one, else "Thinking…". */
export function currentLabel(state: ActivityState): string {
  const running = state.parts.findLast(
    (part) => part.kind === "tool" && part.status === "running",
  )
  return running?.kind === "tool"
    ? `Looking up ${running.title.toLowerCase()}…`
    : "Thinking…"
}
