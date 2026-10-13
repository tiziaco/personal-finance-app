"use client"

import {
  getListConversationsQueryKey,
  useDeleteConversation,
  useListConversations,
  useRenameConversation,
} from "@app/api-client/endpoints/conversation"
import type { ConversationResponse } from "@app/api-client/types"
import { Skeleton } from "@app/ui/skeleton"
import { useQueryClient } from "@tanstack/react-query"
import { SquarePenIcon } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"

import { ConversationRow } from "./conversation-row"
import { CHAT_COPY } from "./copy"

export function ConversationList({
  activeId,
  onNavigate,
}: {
  activeId: string | null
  onNavigate?: () => void
}) {
  const router = useRouter()
  const queryClient = useQueryClient()
  const listKey = getListConversationsQueryKey()
  const { data, isPending } = useListConversations()
  const rename = useRenameConversation()
  const remove = useDeleteConversation()

  const replaceRow = (updated: ConversationResponse) =>
    queryClient.setQueryData<ConversationResponse[]>(listKey, (rows) =>
      rows?.map((r) =>
        r.conversation_id === updated.conversation_id ? updated : r,
      ),
    )

  return (
    <nav
      aria-label={CHAT_COPY.conversations}
      className="flex min-h-0 flex-col gap-1"
    >
      <Link
        href="/chat"
        onClick={onNavigate}
        className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium hover:bg-muted"
      >
        <SquarePenIcon className="size-4" /> {CHAT_COPY.newChat}
      </Link>

      <div className="flex min-h-0 flex-col gap-0.5 overflow-y-auto">
        {isPending &&
          Array.from({ length: 5 }, (_, i) => (
            <Skeleton key={i} className="mx-3 my-2 h-5" />
          ))}
        {data?.length === 0 && (
          <p className="px-3 py-2 text-sm text-muted-foreground">
            {CHAT_COPY.noConversations}
          </p>
        )}
        {data?.map((conversation) => (
          <ConversationRow
            key={conversation.conversation_id}
            conversation={conversation}
            active={conversation.conversation_id === activeId}
            onNavigate={onNavigate}
            onRename={(name) =>
              rename.mutate(
                {
                  conversationId: conversation.conversation_id,
                  data: { name },
                },
                { onSuccess: replaceRow },
              )
            }
            onDelete={() =>
              remove.mutate(
                { conversationId: conversation.conversation_id },
                {
                  onSuccess: () => {
                    queryClient.setQueryData<ConversationResponse[]>(
                      listKey,
                      (rows) =>
                        rows?.filter(
                          (r) =>
                            r.conversation_id !== conversation.conversation_id,
                        ),
                    )
                    if (conversation.conversation_id === activeId)
                      router.push("/chat")
                  },
                },
              )
            }
          />
        ))}
      </div>
    </nav>
  )
}
