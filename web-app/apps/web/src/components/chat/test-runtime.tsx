"use client"

import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  type ThreadMessageLike,
} from "@assistant-ui/react"
import type { ReactNode } from "react"

/** Test helper: render chat components over a fixed list of messages. */
export function TestRuntime({
  messages,
  isRunning = false,
  onNew = async () => {},
  onCancel,
  children,
}: {
  messages: ThreadMessageLike[]
  isRunning?: boolean
  onNew?: () => Promise<void>
  onCancel?: () => Promise<void>
  children: ReactNode
}) {
  const runtime = useExternalStoreRuntime<ThreadMessageLike>({
    messages,
    isRunning,
    convertMessage: (m) => m,
    onNew,
    onCancel,
  })
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  )
}
