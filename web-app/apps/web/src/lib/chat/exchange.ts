import type { ThreadMessageLike } from "@assistant-ui/react"
import type { ChatMessage } from "@app/api-client/types"

import {
  activityReducer,
  emptyActivity,
  fromHistory,
  type ActivityState,
  type Timing,
} from "./activity"
import type { StreamEvent } from "./stream-chat"

/**
 * One send. Stop aborts its controller; `conversationId` is the conversation
 * it belongs to, null while a send from /chat creates it. Immutable: once the
 * conversation exists, the send is replaced by a copy naming it (the
 * `created` action), and identity is what says which send is current.
 */
export type Send = {
  readonly controller: AbortController
  readonly conversationId: string | null
}

/**
 * The exchange being sent, kept beside the saved history until the server has
 * it. It opens before the first await of a send, so the user's message shows
 * and the composer is in its running state (a second send is refused) while
 * the conversation is created or the history refetched.
 *
 * `baseCount` is how many history messages preceded it: the history query can
 * refetch mid-stream (it gains the user's message as soon as the graph
 * starts), and slicing at baseCount is what keeps that message from showing
 * twice.
 */
export type Exchange = {
  send: Send
  baseCount: number
  userText: string
  replyText: string
  activity: ActivityState
  status: "running" | "stopped" | "error"
}

export type ExchangeAction =
  | {
      type: "start"
      send: Send
      userText: string
      baseCount: number
      now: number
    }
  | { type: "created"; send: Send; next: Send }
  | { type: "rebased"; send: Send; baseCount: number }
  | { type: "event"; send: Send; event: StreamEvent; now: number }
  | { type: "stopped"; send: Send; now: number }
  | { type: "failed"; send: Send; now: number }
  | { type: "cleared"; send: Send }
  | { type: "left"; activeId: string | null }

/**
 * A user stop or a failed stream sends no `done`, so the block would keep
 * timing and its running lookups keep spinning. Close it: the lookups that
 * never finished read as failed, and the header reads as stopped when the
 * user stopped it. A failure keeps the neutral timing: the reply's own error
 * line says what went wrong.
 */
function closeActivity(
  activity: ActivityState,
  now: number,
  stopped: boolean,
): ActivityState {
  return {
    ...activity,
    stopped,
    endedAt: activity.endedAt ?? now,
    parts: activity.parts.map((part) =>
      part.kind === "tool" && part.status === "running"
        ? { ...part, status: "error" }
        : part,
    ),
  }
}

export function exchangeReducer(
  state: Exchange | null,
  action: ExchangeAction,
): Exchange | null {
  if (action.type === "start") {
    return {
      send: action.send,
      baseCount: action.baseCount,
      userText: action.userText,
      replyText: "",
      activity: emptyActivity(action.now),
      status: "running",
    }
  }
  // Leaving drops the exchange of any other conversation, /chat included. Not
  // the rendering rule (showsExchange): /chat shows a first send's exchange
  // while its URL catches up, but going to /chat from a conversation leaves it.
  if (action.type === "left") {
    return state && state.send.conversationId !== action.activeId ? null : state
  }
  // Every other action comes from a send, and one that is no longer the
  // exchange's (replaced by a newer send, or dropped by leaving) changes nothing.
  if (state === null || state.send !== action.send) return state
  switch (action.type) {
    case "created":
      return { ...state, send: action.next }
    case "rebased":
      return { ...state, baseCount: action.baseCount }
    case "event":
      return {
        ...state,
        replyText:
          action.event.type === "text"
            ? state.replyText + action.event.text
            : state.replyText,
        activity: activityReducer(state.activity, action.event, action.now),
      }
    case "stopped":
      return {
        ...state,
        status: "stopped",
        activity: closeActivity(state.activity, action.now, true),
      }
    case "failed":
      return {
        ...state,
        status: "error",
        activity: closeActivity(state.activity, action.now, false),
      }
    case "cleared":
      return null
  }
}

/**
 * Whether the exchange shows on this screen: on its own conversation, and on
 * /chat, where a first send's reply can end before the URL names the
 * conversation it created.
 */
export function showsExchange(
  exchange: Exchange,
  activeId: string | null,
): boolean {
  return exchange.send.conversationId === activeId || activeId === null
}

/**
 * The thread: the saved history, then the exchange in flight if it shows here.
 *
 * A message's id is its position in the history, the exchange's included: when
 * the history refetched at the end of a send replaces the exchange, its copy
 * keeps the id, so the reply is not remounted and a block the user opened stays
 * open. `timings` (by history position) are the replies finished on this visit,
 * whose blocks keep their "Worked for" header (spec §7 drops it on reopening).
 */
export function toThreadMessages(
  saved: ChatMessage[],
  exchange: Exchange | null,
  activeId: string | null,
  historyId: string | null,
  timings?: ReadonlyMap<number, Timing>,
): ThreadMessageLike[] {
  const visible =
    exchange && showsExchange(exchange, activeId) ? exchange : null
  const base = visible ? saved.slice(0, visible.baseCount) : saved
  const converted: ThreadMessageLike[] = base.map((m, i) => ({
    id: `${historyId}-${i}`,
    role: m.role === "user" ? "user" : "assistant",
    content: m.content,
    ...(m.activity && {
      metadata: {
        custom: { activity: fromHistory(m.activity, timings?.get(i)) },
      },
    }),
  }))
  if (!visible) return converted
  return [
    ...converted,
    {
      id: `${historyId}-${visible.baseCount}`,
      role: "user",
      content: visible.userText,
    },
    {
      id: `${historyId}-${visible.baseCount + 1}`,
      role: "assistant",
      content: visible.replyText,
      metadata: { custom: { activity: visible.activity } },
      status:
        visible.status === "running"
          ? { type: "running" }
          : {
              type: "incomplete",
              reason: visible.status === "stopped" ? "cancelled" : "error",
            },
    },
  ]
}
