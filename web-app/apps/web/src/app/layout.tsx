import { Onest } from "next/font/google"
import { ThemeProvider } from "@app/ui/theme-provider"
import { Toaster } from "@app/ui/sonner"
import { ClerkProvider } from "@clerk/nextjs"
import { AuthProvider } from "@app/auth"

import type { Metadata } from "next"
import "@/styles/globals.css"

const onest = Onest({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans",
})

// The tab icon is app/icon.svg, the Finsight app tile.
export const metadata: Metadata = {
  title: "Finsight",
  description:
    "Finsight shows where your money goes, month by month, so you can decide what to change.",
}

// Clerk's sign-in and sign-up cards in the Finsight tokens; they follow the theme.
// No colorBorder: Clerk draws borders at ~11% of it, so the already-pale
// --border vanishes. Left unset it falls back to colorNeutral, the foreground,
// which also lifts the social buttons' labels in dark mode.
const CLERK_APPEARANCE = {
  variables: {
    colorPrimary: "var(--primary)",
    colorForeground: "var(--foreground)",
    colorMutedForeground: "var(--muted-foreground)",
    colorBackground: "var(--card)",
    colorInput: "var(--card)",
    colorInputForeground: "var(--foreground)",
    colorNeutral: "var(--foreground)",
    colorDanger: "var(--negative)",
    fontFamily: "var(--font-sans)",
    borderRadius: "0.75rem",
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <ClerkProvider appearance={CLERK_APPEARANCE}>
      <html lang="en" suppressHydrationWarning className={onest.variable}>
        <body className="antialiased min-h-screen bg-background">
          <AuthProvider signOutUrl="/sign-in">
            <ThemeProvider
              attribute="class"
              defaultTheme="system"
              enableSystem
              disableTransitionOnChange
            >
              {children}
              <Toaster position="bottom-right" />
            </ThemeProvider>
          </AuthProvider>
        </body>
      </html>
    </ClerkProvider>
  )
}
