"use client"

import { ChatThreadSkeleton } from "./chat-thread-skeleton"
import {
  isConversationNotFound,
  useActiveConversationId,
  useChatHistory,
} from "./chat-runtime-provider"
import { ConversationNotFound } from "./conversation-not-found"
import { Thread } from "./thread"

/** /chat/[conversationId] — one conversation, or not-found for an unknown, foreign or malformed id. */
export function ConversationPage() {
  const activeId = useActiveConversationId()
  const history = useChatHistory(activeId)

  if (isConversationNotFound(history.error)) return <ConversationNotFound />
  if (history.isPending) return <ChatThreadSkeleton />
  return <Thread />
}
