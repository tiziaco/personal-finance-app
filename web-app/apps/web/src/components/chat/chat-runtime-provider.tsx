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
 * The exchange being streamed, kept beside the saved history until the server
 * has it. `baseCount` is how many history messages preceded it: the history
 * query can refetch mid-stream (it gains the user's message as soon as the
 * graph starts), and slicing at baseCount is what keeps that message from
 * showing twice.
 */
type Exchange = {
  conversationId: string
  baseCount: number
  userText: string
  replyText: string
  status: "running" | "stopped" | "error"
}

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
  const history = useListChatMessages(activeId ?? "", {
    query: { enabled: activeId !== null },
  })

  const [exchange, setExchange] = useState<Exchange | null>(null)
  const controllerRef = useRef<AbortController | null>(null)
  const inflightIdRef = useRef<string | null>(null)
  const restoreTextRef = useRef<(text: string) => void>(() => {})

  // Leaving a conversation abandons its stream, and with WS7 the server stops
  // the model call. The first send on /chat moves the URL to the new
  // conversation's id: that move is not leaving, hence inflightIdRef.
  useEffect(() => {
    if (inflightIdRef.current !== null && inflightIdRef.current !== activeId) {
      controllerRef.current?.abort()
      controllerRef.current = null
      inflightIdRef.current = null
    }
    setExchange((e) => (e && e.conversationId !== activeId ? null : e))
  }, [activeId])

  useEffect(() => () => controllerRef.current?.abort(), [])

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

      let conversationId = activeId
      if (conversationId === null) {
        let created: ConversationResponse
        try {
          created = await createConversation.mutateAsync()
        } catch {
          // The mutation cache has already toasted.
          restoreTextRef.current(text)
          return
        }
        conversationId = created.conversation_id
        queryClient.setQueryData<ConversationResponse[]>(
          getListConversationsQueryKey(),
          (rows) => [created, ...(rows ?? [])],
        )
        // A new conversation's history is known to be empty. Seeding it means
        // /chat/[id] renders the thread at once instead of a loading skeleton
        // that would hide the reply as it starts streaming.
        queryClient.setQueryData<ConversationHistory>(
          getListChatMessagesQueryKey(conversationId),
          { messages: [] },
        )
        inflightIdRef.current = conversationId
        router.replace(`/chat/${conversationId}`)
      }

      // After a stop or failure the saved history may have moved on (it holds
      // the stopped turn's user message), so count from fresh data.
      const historyKey = getListChatMessagesQueryKey(conversationId)
      if (activeId !== null)
        await queryClient.refetchQueries({ queryKey: historyKey })
      const saved =
        queryClient.getQueryData<ConversationHistory>(historyKey)?.messages ??
        EMPTY

      const controller = new AbortController()
      controllerRef.current = controller
      inflightIdRef.current = conversationId
      setExchange({
        conversationId,
        baseCount: saved.length,
        userText: text,
        replyText: "",
        status: "running",
      })

      try {
        const token = await getToken()
        for await (const chunk of streamChat({
          conversationId,
          message: text,
          token,
          signal: controller.signal,
        })) {
          setExchange((e) =>
            e && e.conversationId === conversationId
              ? { ...e, replyText: e.replyText + chunk }
              : e,
          )
        }
        await queryClient.refetchQueries({ queryKey: historyKey })
        setExchange((e) => (e?.conversationId === conversationId ? null : e))
        requestTitle(conversationId)
      } catch (error) {
        if (controller.signal.aborted) {
          setExchange((e) =>
            e?.conversationId === conversationId
              ? { ...e, status: "stopped" }
              : e,
          )
        } else if (error instanceof ApiError) {
          // Refused before anything streamed: nothing to show but the toast,
          // and the user's text goes back in the composer.
          toastForError(error)
          setExchange((e) => (e?.conversationId === conversationId ? null : e))
          restoreTextRef.current(text)
        } else {
          setExchange((e) =>
            e?.conversationId === conversationId
              ? { ...e, status: "error" }
              : e,
          )
        }
      } finally {
        if (controllerRef.current === controller) controllerRef.current = null
        if (inflightIdRef.current === conversationId)
          inflightIdRef.current = null
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
