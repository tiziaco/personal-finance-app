import { fileURLToPath } from "node:url"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"

// Vitest defaults NODE_ENV only when it is unset, so an exported
// NODE_ENV=production would load React's production build and fail every
// render test far from the cause. Pinned for every entry point.
process.env.NODE_ENV = "test"

const TEST_FILES = "src/**/*.test.?(c|m)[jt]s?(x)"

/** A portal's project: its own tests, and `@/` resolved to its own src/. */
function portal(app: string) {
  return {
    extends: true,
    resolve: {
      alias: {
        "@/": fileURLToPath(new URL(`./apps/${app}/src/`, import.meta.url)),
      },
    },
    test: { name: app, include: [`apps/${app}/${TEST_FILES}`] },
  }
}

export default defineConfig({
  plugins: [react()],
  // Every package has its own react symlink; two copies would surface as
  // "invalid hook call" from inside a primitive.
  resolve: { dedupe: ["react", "react-dom"] },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    exclude: ["**/node_modules/**", "**/.next/**", "**/dist/**", "e2e/**"],
    // Explicit imports from "vitest": globals would need a `types` entry in
    // every standalone tsconfig.
    globals: false,
    // Two portals each own `@/`, so one alias cannot serve both.
    // `.test.` only: `.spec.` is reserved for Playwright.
    projects: [
      {
        extends: true,
        test: { name: "packages", include: [`packages/*/${TEST_FILES}`] },
      },
      portal("internal-portal"),
      portal("supplier-portal"),
    ],
  },
})
