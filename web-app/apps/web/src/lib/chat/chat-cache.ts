import { getListChatMessagesQueryKey } from "@app/api-client/endpoints/chatbot"
import { getListConversationsQueryKey } from "@app/api-client/endpoints/conversation"
import type {
  ConversationHistory,
  ConversationResponse,
  Message,
} from "@app/api-client/types"
import type { QueryClient } from "@tanstack/react-query"

/** One empty list, so a memo over "no messages" keeps its identity. */
export const NO_MESSAGES: Message[] = []

/** Write a conversation's new row (a rename, a generated title) into the loaded list. */
export function replaceConversation(
  client: QueryClient,
  updated: ConversationResponse,
): void {
  client.setQueryData<ConversationResponse[]>(
    getListConversationsQueryKey(),
    (rows) =>
      rows?.map((r) =>
        r.conversation_id === updated.conversation_id ? updated : r,
      ),
  )
}

/**
 * Put a new conversation at the top of the list, then refetch it. Only into a
 * list already loaded: its cache can be empty here (its first fetch failed or
 * is still in flight), and seeding it would show a one-row list until it went
 * stale. The refetch also covers a list whose first fetch was in flight.
 */
export function prependConversation(
  client: QueryClient,
  created: ConversationResponse,
): void {
  const key = getListConversationsQueryKey()
  client.setQueryData<ConversationResponse[]>(
    key,
    (rows) => rows && [created, ...rows],
  )
  void client.invalidateQueries({ queryKey: key })
}

export function removeConversation(
  client: QueryClient,
  conversationId: string,
): void {
  client.setQueryData<ConversationResponse[]>(
    getListConversationsQueryKey(),
    (rows) => rows?.filter((r) => r.conversation_id !== conversationId),
  )
}

/** The conversation's saved messages in the cache; none for /chat or an unloaded history. */
export function cachedHistory(
  client: QueryClient,
  conversationId: string | null,
): Message[] {
  if (conversationId === null) return NO_MESSAGES
  return (
    client.getQueryData<ConversationHistory>(
      getListChatMessagesQueryKey(conversationId),
    )?.messages ?? NO_MESSAGES
  )
}

/**
 * A new conversation's history is known to be empty. Seeding it means
 * /chat/[id] renders the thread at once instead of a loading skeleton that
 * would hide the reply as it starts streaming.
 */
export function seedEmptyHistory(
  client: QueryClient,
  conversationId: string,
): void {
  client.setQueryData<ConversationHistory>(
    getListChatMessagesQueryKey(conversationId),
    { messages: [] },
  )
}

export function refetchHistory(
  client: QueryClient,
  conversationId: string,
): Promise<void> {
  return client.refetchQueries({
    queryKey: getListChatMessagesQueryKey(conversationId),
  })
}

/**
 * Mark a history stale after a Stop or a failure, without refetching: the
 * server may still be saving the stopped turn. The next send (see
 * historyNeedsRefetch) or the conversation's next mount fetches it.
 */
export function markHistoryStale(
  client: QueryClient,
  conversationId: string,
): void {
  void client.invalidateQueries({
    queryKey: getListChatMessagesQueryKey(conversationId),
    refetchType: "none",
  })
}

/** Whether a Stop or failure has left this history stale since it was last fetched. */
export function historyNeedsRefetch(
  client: QueryClient,
  conversationId: string,
): boolean {
  return (
    client.getQueryState(getListChatMessagesQueryKey(conversationId))
      ?.isInvalidated ?? false
  )
}
