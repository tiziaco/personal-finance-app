"use client"

import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from "@assistant-ui/react"
import { ApiError, toastForError, useApiRequest } from "@app/api-client"
import { useListChatMessages } from "@app/api-client/endpoints/chatbot"
import {
  getListConversationsQueryKey,
  useCreateConversation,
  useGenerateConversationTitle,
} from "@app/api-client/endpoints/conversation"
import type { ConversationResponse } from "@app/api-client/types"
import { useQueryClient } from "@tanstack/react-query"
import { useParams, useRouter } from "next/navigation"
import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react"

import {
  cachedHistory,
  historyNeedsRefetch,
  markHistoryStale,
  NO_MESSAGES,
  prependConversation,
  refetchHistory,
  replaceConversation,
  seedEmptyHistory,
} from "@/lib/chat/chat-cache"
import {
  exchangeReducer,
  toThreadMessages,
  type Send,
} from "@/lib/chat/exchange"
import { streamChat } from "@/lib/chat/stream-chat"

export function useActiveConversationId(): string | null {
  const params = useParams<{ conversationId?: string }>()
  return params.conversationId ?? null
}

/**
 * A malformed id is answered 422 by the path's UUID validation: to the user it
 * is a conversation that doesn't exist, the same as a 404.
 */
export function isConversationNotFound(error: unknown): boolean {
  return (
    error instanceof ApiError && (error.status === 404 || error.status === 422)
  )
}

/**
 * A conversation's saved messages. Every observer of this query goes through
 * here, because a query's meta is whichever observer set its options last.
 * Not-found is silenced: ConversationPage renders it as a screen, which a
 * toast would only repeat. Every other error toasts by QueryProvider's rule.
 */
export function useChatHistory(conversationId: string | null) {
  return useListChatMessages(conversationId ?? "", {
    query: {
      enabled: conversationId !== null,
      meta: { silentError: isConversationNotFound },
    },
  })
}

/**
 * Whether `send` is still the one in flight. Leaving (or unmounting) drops it
 * from the ref; Stop aborts it but leaves it there. So ownership, not the
 * abort, is what says the user is still on this send's screen.
 */
function owns(ref: RefObject<Send | null>, send: Send): boolean {
  return ref.current === send
}

/** End a send's hold on the ref, unless the user already left it. */
function release(ref: RefObject<Send | null>, send: Send): void {
  if (ref.current === send) ref.current = null
}

export function ChatRuntimeProvider({ children }: { children: ReactNode }) {
  const activeId = useActiveConversationId()
  const router = useRouter()
  const queryClient = useQueryClient()
  const request = useApiRequest()
  const createConversation = useCreateConversation()
  // The cache update is in the hook's options, not the mutate call: a call's
  // own callbacks run only for the latest call, so a title for one
  // conversation would be lost if another's was asked for before it landed.
  // Silent: the title is asked for in the background, and the server
  // already treats a failed one as cosmetic.
  const generateTitle = useGenerateConversationTitle({
    mutation: {
      meta: { silentError: true },
      onSuccess: (updated) => replaceConversation(queryClient, updated),
    },
  })
  // A conversation created by a send from /chat, until the URL names it. The
  // reply can end before router.replace commits (a route compiling in dev):
  // the thread then shows this conversation's history, not an empty /chat,
  // and the history refetch at the end of the send has an observer to run.
  const [createdId, setCreatedId] = useState<string | null>(null)
  const historyId = activeId ?? createdId
  const history = useChatHistory(historyId)

  const [exchange, dispatch] = useReducer(exchangeReducer, null)
  const sendRef = useRef<Send | null>(null)
  const restoreTextRef = useRef<(text: string) => void>(() => {})

  // Leaving a conversation abandons its send, and the server then stops the
  // model call. A first send on /chat names its new conversation before
  // moving the URL there: that move is not leaving.
  useEffect(() => {
    const send = sendRef.current
    if (send !== null && send.conversationId !== activeId) {
      send.controller.abort()
      sendRef.current = null
    }
    dispatch({ type: "left", activeId })
    setCreatedId(null)
  }, [activeId])

  useEffect(
    () => () => {
      sendRef.current?.controller.abort()
      sendRef.current = null
    },
    [],
  )

  const requestTitle = useCallback(
    (conversationId: string) => {
      const rows = queryClient.getQueryData<ConversationResponse[]>(
        getListConversationsQueryKey(),
      )
      const row = rows?.find((r) => r.conversation_id === conversationId)
      // `name` is optional in the contract: absent and "" both mean untitled.
      // No list in the cache (its fetch failed or is still in flight) asks
      // too: the server answers a named conversation unchanged.
      if (row?.name) return
      generateTitle.mutate({ conversationId })
    },
    [generateTitle, queryClient],
  )

  // A send from /chat creates its conversation first. Resolves to the send
  // naming its conversation, or null when the send ended here: the create
  // failed (the mutation cache has toasted) or the user left while it ran.
  const ensureConversation = useCallback(
    async (
      send: Send,
      text: string,
    ): Promise<{ send: Send; conversationId: string } | null> => {
      if (send.conversationId !== null) {
        return { send, conversationId: send.conversationId }
      }
      let created: ConversationResponse
      try {
        created = await createConversation.mutateAsync()
      } catch {
        const stillHere = owns(sendRef, send)
        dispatch({ type: "cleared", send })
        release(sendRef, send)
        if (stillHere) restoreTextRef.current(text)
        return null
      }
      prependConversation(queryClient, created)
      // Left for another conversation while this one was being created (a
      // Stop first included): it exists, but the user is elsewhere now.
      if (!owns(sendRef, send)) return null
      const conversationId = created.conversation_id
      const next: Send = { ...send, conversationId }
      seedEmptyHistory(queryClient, conversationId)
      // Named before the URL moves, so the move is not taken for leaving.
      sendRef.current = next
      dispatch({ type: "created", send, next })
      setCreatedId(conversationId)
      router.replace(`/chat/${conversationId}`)
      return { send: next, conversationId }
    },
    [createConversation, queryClient, router],
  )

  // A Stop or failure leaves the history stale: the saved history may have
  // moved on (it holds the stopped turn's user message), so count from fresh
  // data. Until then the slice at the cached length keeps the thread steady.
  // A completed send already ended with a refetch.
  const rebaseIfStale = useCallback(
    async (send: Send, conversationId: string) => {
      if (!historyNeedsRefetch(queryClient, conversationId)) return
      await refetchHistory(queryClient, conversationId)
      dispatch({
        type: "rebased",
        send,
        baseCount: cachedHistory(queryClient, conversationId).length,
      })
    },
    [queryClient],
  )

  // How a send that threw ends: a Stop (or leaving) aborted it; a refused
  // stream start is an ApiError with nothing streamed; anything else failed
  // mid-reply.
  const settle = useCallback(
    (send: Send, conversationId: string, text: string, error: unknown) => {
      if (send.controller.signal.aborted) {
        dispatch({ type: "stopped", send })
        markHistoryStale(queryClient, conversationId)
      } else if (error instanceof ApiError) {
        // Refused before anything streamed: nothing to show but the toast,
        // and the user's text goes back in the composer.
        toastForError(error)
        dispatch({ type: "cleared", send })
        restoreTextRef.current(text)
      } else {
        dispatch({ type: "failed", send })
        markHistoryStale(queryClient, conversationId)
      }
    },
    [queryClient],
  )

  const onNew = useCallback(
    async (message: AppendMessage) => {
      const part = message.content[0]
      if (part?.type !== "text") return
      const text = part.text

      // Open the exchange before anything is awaited: from here the thread
      // shows the message, isRunning is true and Stop reaches this send.
      const opened: Send = {
        controller: new AbortController(),
        conversationId: activeId,
      }
      sendRef.current = opened
      dispatch({
        type: "start",
        send: opened,
        userText: text,
        baseCount: cachedHistory(queryClient, activeId).length,
      })

      const ready = await ensureConversation(opened, text)
      if (ready === null) return
      const { send, conversationId } = ready
      await rebaseIfStale(send, conversationId)

      // Stopped before the stream started: nothing was sent, nothing to stream.
      if (send.controller.signal.aborted) {
        dispatch({ type: "stopped", send })
        release(sendRef, send)
        return
      }

      try {
        for await (const chunk of streamChat({
          conversationId,
          message: text,
          request,
          signal: send.controller.signal,
        })) {
          dispatch({ type: "chunk", send, text: chunk })
        }
        await refetchHistory(queryClient, conversationId)
        dispatch({ type: "cleared", send })
        requestTitle(conversationId)
      } catch (error) {
        settle(send, conversationId, text, error)
      } finally {
        release(sendRef, send)
      }
    },
    [
      activeId,
      ensureConversation,
      queryClient,
      rebaseIfStale,
      request,
      requestTitle,
      settle,
    ],
  )

  const onCancel = useCallback(async () => {
    sendRef.current?.controller.abort()
  }, [])

  const savedMessages = history.data?.messages ?? NO_MESSAGES
  const messages = useMemo(
    () => toThreadMessages(savedMessages, exchange, activeId, historyId),
    [activeId, exchange, historyId, savedMessages],
  )

  const runtime = useExternalStoreRuntime<ThreadMessageLike>({
    messages,
    isRunning: exchange?.status === "running",
    convertMessage: (m) => m,
    onNew,
    onCancel,
  })

  // Set in an effect, not during render: React 19's lint rules forbid writing refs while rendering.
  useEffect(() => {
    restoreTextRef.current = (text: string) =>
      runtime.thread.composer.setText(text)
  }, [runtime])

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  )
}
