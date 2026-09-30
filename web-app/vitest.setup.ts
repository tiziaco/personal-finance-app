import { afterEach } from "vitest"
import { cleanup } from "@testing-library/react"
import "@testing-library/jest-dom/vitest"

// Testing Library auto-cleans only with globals on.
afterEach(() => {
  cleanup()
})

// jsdom has no matchMedia, and SidebarProvider reaches it through
// useIsMobile(): every test that renders a sidebar primitive needs this.
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
    addListener: () => {},
    removeListener: () => {},
  }),
})

// resolveBaseUrl() throws when unset; Next inlines it at build time, Vitest
// does not. Tests of the unset branch delete it themselves.
process.env.NEXT_PUBLIC_API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8100"

// jsdom has no ResizeObserver; DataTableCore measures frozen columns with it.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
} as unknown as typeof ResizeObserver
