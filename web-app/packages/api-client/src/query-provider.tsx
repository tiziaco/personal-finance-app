"use client"

import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query"
import { ReactQueryDevtools } from "@tanstack/react-query-devtools"
import { useState } from "react"
import { ApiError } from "./errors"
import { isDevelopment } from "@app/core/lib/env"
import { toastForError } from "./toast-for-error"

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        queryCache: new QueryCache({
          onError: (error, query) => {
            // onError fires for background refetches too. A polling query that
            // fails every 30s would otherwise toast every 30s, behind data the
            // user can already see. Only a query that has never resolved
            // toasts, and a query can opt out entirely.
            if (query.meta?.silentError === true) return
            if (query.state.data !== undefined) return
            toastForError(error)
          },
        }),
        // Mutations always toast: the user just acted and is waiting for a result.
        mutationCache: new MutationCache({ onError: toastForError }),
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            gcTime: 5 * 60 * 1000,
            refetchOnWindowFocus: false,
            // Retrying a 4xx burns a request for an answer that will not change.
            retry: (failureCount, error) =>
              failureCount < 1 &&
              !(error instanceof ApiError && error.status < 500),
          },
        },
      }),
  )

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {isDevelopment && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  )
}
