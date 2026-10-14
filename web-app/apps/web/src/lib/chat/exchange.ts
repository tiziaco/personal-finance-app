import type { ThreadMessageLike } from "@assistant-ui/react"
import type { Message } from "@app/api-client/types"

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
  status: "running" | "stopped" | "error"
}

export type ExchangeAction =
  | { type: "start"; send: Send; userText: string; baseCount: number }
  | { type: "created"; send: Send; next: Send }
  | { type: "rebased"; send: Send; baseCount: number }
  | { type: "chunk"; send: Send; text: string }
  | { type: "stopped"; send: Send }
  | { type: "failed"; send: Send }
  | { type: "cleared"; send: Send }
  | { type: "left"; activeId: string | null }

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
    case "chunk":
      return { ...state, replyText: state.replyText + action.text }
    case "stopped":
      return { ...state, status: "stopped" }
    case "failed":
      return { ...state, status: "error" }
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

/** The thread: the saved history, then the exchange in flight if it shows here. */
export function toThreadMessages(
  saved: Message[],
  exchange: Exchange | null,
  activeId: string | null,
  historyId: string | null,
): ThreadMessageLike[] {
  const visible =
    exchange && showsExchange(exchange, activeId) ? exchange : null
  const base = visible ? saved.slice(0, visible.baseCount) : saved
  const converted: ThreadMessageLike[] = base.map((m, i) => ({
    id: `${historyId}-${i}`,
    role: m.role === "user" ? "user" : "assistant",
    content: m.content,
  }))
  if (!visible) return converted
  return [
    ...converted,
    { id: "inflight-user", role: "user", content: visible.userText },
    {
      id: "inflight-assistant",
      role: "assistant",
      content: visible.replyText,
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
