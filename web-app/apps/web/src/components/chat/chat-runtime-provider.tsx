"use client"

import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from "@assistant-ui/react"
import { ApiError, toastForError } from "@app/api-client"
import {
  getListChatMessagesQueryKey,
  useListChatMessages,
} from "@app/api-client/endpoints/chatbot"
import {
  getListConversationsQueryKey,
  useCreateConversation,
  useGenerateConversationTitle,
} from "@app/api-client/endpoints/conversation"
import type {
  ConversationHistory,
  ConversationResponse,
  Message,
} from "@app/api-client/types"
import { useAppAuth } from "@app/auth"
import { useQueryClient } from "@tanstack/react-query"
import { useParams, useRouter } from "next/navigation"
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"

import { streamChat } from "@/lib/chat/stream-chat"

/**
 * The exchange being sent, kept beside the saved history until the server has
 * it. It opens before the first await of a send, so the user's message shows
 * and the composer is in its running state (a second send is refused) while
 * the conversation is created or the history refetched.
 *
 * `key` identifies the send; `conversationId` is null until a send from /chat
 * has created its conversation. `baseCount` is how many history messages
 * preceded it: the history query can refetch mid-stream (it gains the user's
 * message as soon as the graph starts), and slicing at baseCount is what keeps
 * that message from showing twice.
 */
type Exchange = {
  key: number
  conversationId: string | null
  baseCount: number
  userText: string
  replyText: string
  status: "running" | "stopped" | "error"
}

/** Abort reason when the user leaves the conversation (or the screen) mid-send. */
const LEFT = "left"

const EMPTY: Message[] = []

export function useActiveConversationId(): string | null {
  const params = useParams<{ conversationId?: string }>()
  return params.conversationId ?? null
}

export function ChatRuntimeProvider({ children }: { children: ReactNode }) {
  const activeId = useActiveConversationId()
  const router = useRouter()
  const queryClient = useQueryClient()
  const { getToken } = useAppAuth()
  const createConversation = useCreateConversation()
  const generateTitle = useGenerateConversationTitle()
  // silentError on both observers of this query: a query's meta is whichever
  // observer set its options last, and ConversationPage renders the 404 as a
  // not-found screen, which a "Not found." toast would only repeat.
  const history = useListChatMessages(activeId ?? "", {
    query: { enabled: activeId !== null, meta: { silentError: true } },
  })

  const [exchange, setExchange] = useState<Exchange | null>(null)
  const controllerRef = useRef<AbortController | null>(null)
  const inflightIdRef = useRef<string | null>(null)
  const sendKeyRef = useRef(0)
  const restoreTextRef = useRef<(text: string) => void>(() => {})

  // Leaving a conversation abandons its send, and with WS7 the server stops
  // the model call. inflightIdRef is the conversation the send belongs to
  // (null while a send from /chat creates it). The first send on /chat moves
  // the URL to the new conversation's id, after setting inflightIdRef to it:
  // that move is not leaving.
  useEffect(() => {
    if (controllerRef.current !== null && inflightIdRef.current !== activeId) {
      controllerRef.current.abort(LEFT)
      controllerRef.current = null
      inflightIdRef.current = null
    }
    setExchange((e) => (e && e.conversationId !== activeId ? null : e))
  }, [activeId])

  useEffect(
    () => () => {
      controllerRef.current?.abort(LEFT)
      controllerRef.current = null
    },
    [],
  )

  const requestTitle = useCallback(
    (conversationId: string) => {
      const listKey = getListConversationsQueryKey()
      const rows = queryClient.getQueryData<ConversationResponse[]>(listKey)
      const row = rows?.find((r) => r.conversation_id === conversationId)
      // `name` is optional in the contract: absent and "" both mean untitled.
      if (row?.name) return
      generateTitle.mutate(
        { conversationId },
        {
          onSuccess: (updated) =>
            queryClient.setQueryData<ConversationResponse[]>(
              listKey,
              (current) =>
                current?.map((r) =>
                  r.conversation_id === updated.conversation_id ? updated : r,
                ),
            ),
        },
      )
    },
    [generateTitle, queryClient],
  )

  const onNew = useCallback(
    async (message: AppendMessage) => {
      const part = message.content[0]
      if (part?.type !== "text") return
      const text = part.text

      // Open the exchange before anything is awaited: from here the thread
      // shows the message, isRunning is true and Stop reaches this send.
      const key = ++sendKeyRef.current
      const controller = new AbortController()
      controllerRef.current = controller
      inflightIdRef.current = activeId
      const update = (change: (e: Exchange) => Exchange | null) =>
        setExchange((e) => (e?.key === key ? change(e) : e))
      const release = () => {
        if (controllerRef.current !== controller) return
        controllerRef.current = null
        inflightIdRef.current = null
      }
      const cached =
        activeId === null
          ? EMPTY
          : (queryClient.getQueryData<ConversationHistory>(
              getListChatMessagesQueryKey(activeId),
            )?.messages ?? EMPTY)
      setExchange({
        key,
        conversationId: activeId,
        baseCount: cached.length,
        userText: text,
        replyText: "",
        status: "running",
      })

      let conversationId: string
      if (activeId === null) {
        let created: ConversationResponse
        try {
          created = await createConversation.mutateAsync()
        } catch {
          // The mutation cache has already toasted.
          update(() => null)
          release()
          if (controller.signal.reason !== LEFT) restoreTextRef.current(text)
          return
        }
        queryClient.setQueryData<ConversationResponse[]>(
          getListConversationsQueryKey(),
          (rows) => [created, ...(rows ?? [])],
        )
        // Left for another conversation while this one was being created: it
        // exists (it is in the list), but the user is elsewhere now.
        if (controller.signal.reason === LEFT) return
        conversationId = created.conversation_id
        // A new conversation's history is known to be empty. Seeding it means
        // /chat/[id] renders the thread at once instead of a loading skeleton
        // that would hide the reply as it starts streaming.
        queryClient.setQueryData<ConversationHistory>(
          getListChatMessagesQueryKey(conversationId),
          { messages: [] },
        )
        inflightIdRef.current = conversationId
        update((e) => ({ ...e, conversationId }))
        router.replace(`/chat/${conversationId}`)
      } else {
        conversationId = activeId
        // After a stop or failure the saved history may have moved on (it
        // holds the stopped turn's user message), so count from fresh data.
        // Until then the slice at the cached length keeps the thread steady.
        const historyKey = getListChatMessagesQueryKey(conversationId)
        await queryClient.refetchQueries({ queryKey: historyKey })
        const saved =
          queryClient.getQueryData<ConversationHistory>(historyKey)?.messages ??
          EMPTY
        update((e) => ({ ...e, baseCount: saved.length }))
      }

      // Stopped before the stream started: nothing was sent, nothing to stream.
      if (controller.signal.aborted) {
        update((e) => ({ ...e, status: "stopped" }))
        release()
        return
      }

      const historyKey = getListChatMessagesQueryKey(conversationId)
      try {
        const token = await getToken()
        for await (const chunk of streamChat({
          conversationId,
          message: text,
          token,
          signal: controller.signal,
        })) {
          update((e) => ({ ...e, replyText: e.replyText + chunk }))
        }
        await queryClient.refetchQueries({ queryKey: historyKey })
        update(() => null)
        requestTitle(conversationId)
      } catch (error) {
        if (controller.signal.aborted) {
          update((e) => ({ ...e, status: "stopped" }))
        } else if (error instanceof ApiError) {
          // Refused before anything streamed: nothing to show but the toast,
          // and the user's text goes back in the composer.
          toastForError(error)
          update(() => null)
          restoreTextRef.current(text)
        } else {
          update((e) => ({ ...e, status: "error" }))
        }
      } finally {
        release()
      }
    },
    [activeId, createConversation, getToken, queryClient, requestTitle, router],
  )

  const onCancel = useCallback(async () => {
    controllerRef.current?.abort()
  }, [])

  const savedMessages = history.data?.messages ?? EMPTY
  const messages = useMemo<ThreadMessageLike[]>(() => {
    const visible =
      exchange && (exchange.conversationId === activeId || activeId === null)
        ? exchange
        : null
    const base = visible
      ? savedMessages.slice(0, visible.baseCount)
      : savedMessages
    const converted: ThreadMessageLike[] = base.map((m, i) => ({
      id: `${activeId}-${i}`,
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
  }, [activeId, exchange, savedMessages])

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
