import { ChatThreadSkeleton } from "@/components/chat/chat-shell"

/**
 * Next renders a segment's loading.tsx inside its layout.tsx, so this is the
 * fallback for the thread pane only: ChatShell (and its conversation list)
 * is already on screen around it. A list column here would sit beside the
 * real one.
 */
export default function ChatLoading() {
  return <ChatThreadSkeleton />
}
