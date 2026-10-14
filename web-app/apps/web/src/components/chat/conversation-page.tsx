"use client"

import { ApiError, toastForError } from "@app/api-client"
import { useEffect } from "react"

import { ChatThreadSkeleton } from "./chat-thread-skeleton"
import {
  useActiveConversationId,
  useChatHistory,
} from "./chat-runtime-provider"
import { ConversationNotFound } from "./conversation-not-found"
import { Thread } from "./thread"

/** /chat/[conversationId] — one conversation, or not-found for an unknown, foreign or malformed id. */
export function ConversationPage() {
  const activeId = useActiveConversationId()
  const history = useChatHistory(activeId)
  // A malformed id is answered 422 by the path's UUID validation: to the user
  // it is a conversation that doesn't exist, the same as a 404.
  const notFound =
    history.error instanceof ApiError &&
    (history.error.status === 404 || history.error.status === 422)

  // useChatHistory's silentError keeps QueryProvider from toasting, and a
  // query's meta can't depend on the status. So the toast it would have shown
  // is raised here, for every error but the not-found below.
  const hasData = history.data !== undefined
  useEffect(() => {
    // Mirrors QueryProvider's rule: a failed refetch behind shown data stays silent.
    if (history.error && !notFound && !hasData) toastForError(history.error)
  }, [history.error, notFound, hasData])

  if (notFound) return <ConversationNotFound />
  if (history.isPending) return <ChatThreadSkeleton />
  return <Thread />
}
