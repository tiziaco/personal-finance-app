/**
 * Curated user-facing copy.
 *
 * SECURITY: error toasts map an HTTP status to a string from this file. Never
 * surface ApiError.message or ApiError.body — server payloads can carry stack
 * traces and internal route names.
 */
export const messages = {
  toasts: {
    sessionExpired: "Sessione scaduta. Effettua di nuovo l'accesso.",
    forbidden: "Non hai i permessi per questa operazione.",
    notFound: "Risorsa non trovata.",
    conflictError: "Operazione in conflitto con lo stato attuale.",
    validationError: "Dati non validi.",
    genericError: "Si è verificato un errore. Riprova.",
  },
} as const
