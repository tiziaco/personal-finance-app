/**
 * The package's public runtime surface is deliberately tiny. Everything else is
 * reached through the subpath exports, so importing one tag does not pull in
 * the whole client.
 *
 * `resolveBaseUrl` and `toastForError` are here for the one hand-written call
 * site: the chat stream, which orval does not generate (streaming routes are
 * excluded) but which must resolve the API and report errors the same way.
 */
export { ApiError } from "./errors"
export { useApiFetch, resolveBaseUrl } from "./use-api-fetch"
export { toastForError } from "./toast-for-error"
