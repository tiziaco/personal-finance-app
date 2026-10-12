import { Inter } from "next/font/google"
import { ThemeProvider } from "@app/ui/theme-provider"
import { Toaster } from "@app/ui/sonner"
import { ClerkProvider } from "@clerk/nextjs"
import { AuthProvider } from "@app/auth"

import type { Metadata } from "next"
import "@/styles/globals.css"

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" })

export const metadata: Metadata = {
  title: "Personal Finance",
  description:
    "Personal Finance — track your spending, understand where it goes, and save more.",
  icons: {
    icon: [{ url: "/icons/favicon.ico", sizes: "any", type: "image/x-icon" }],
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <ClerkProvider>
      <html lang="en" suppressHydrationWarning className={inter.variable}>
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
