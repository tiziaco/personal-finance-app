/**
 * What a query or mutation may carry in `meta`, typed for every hook through
 * TanStack Query's Register.
 *
 * `silentError` keeps a failure out of QueryProvider's toast: `true` for every
 * error, or a predicate for the errors the caller shows another way (the chat
 * page renders a 404 as its not-found screen).
 */
export type SilentError = boolean | ((error: unknown) => boolean)

export interface AppMeta extends Record<string, unknown> {
  silentError?: SilentError
}

declare module "@tanstack/react-query" {
  interface Register {
    queryMeta: AppMeta
    mutationMeta: AppMeta
  }
}

/** Whether `meta` keeps this error out of the toast. */
export function isSilenced(meta: AppMeta | undefined, error: unknown): boolean {
  const silent = meta?.silentError
  return typeof silent === "function" ? silent(error) : silent === true
}
