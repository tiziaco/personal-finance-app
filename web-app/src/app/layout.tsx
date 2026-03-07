import { Public_Sans } from "next/font/google";
import { ThemeProvider } from "@/components/ui/theme-provider";
import { Toaster } from "@/components/ui/sonner";
import { ClerkProvider } from '@clerk/nextjs'
import { QueryProvider } from "@/providers/query-provider";
import { DateFormatProvider } from "@/providers/date-format-provider";
import { CurrencyProvider } from "@/providers/currency-provider";

import type { Metadata } from "next";
import "@/styles/globals.css";

const publicSans = Public_Sans({subsets:['latin'],variable:'--font-sans'});


export const metadata: Metadata = {
  title: "Personal Finance App",
  description: "Personal finance management app. Track your expenses, set budgets, and achieve your financial goals with ease.",
  icons: {
    icon: [
      { url: "/icons/favicon.ico", sizes: "any", type: "image/x-icon" },
      { url: "/icons/favicon-16x16.ico", sizes: "16x16", type: "image/x-icon" },
      { url: "/icons/favicon-32x32.ico", sizes: "32x32", type: "image/x-icon" },
    ],
    apple: [{ url: "/icons/favicon-ios-57x57.ico", sizes: "57x57" }],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider>
      <html lang="en" suppressHydrationWarning className={publicSans.variable}>
        <body
          className={`antialiased min-h-screen bg-background`}
        >
          <QueryProvider>
            <ThemeProvider
                attribute="class"
                defaultTheme="system"
                enableSystem
              disableTransitionOnChange
          >
            <DateFormatProvider>
              <CurrencyProvider>
                {children}
                <Toaster position="bottom-right" />
              </CurrencyProvider>
            </DateFormatProvider>
          </ThemeProvider>
          </QueryProvider>
        </body>
      </html>
    </ClerkProvider>
  );
}
