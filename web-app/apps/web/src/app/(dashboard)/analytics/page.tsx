import { Suspense } from "react"

import { AnalyticsPage } from "@/components/analytics/analytics-page"

import AnalyticsLoading from "./loading"

/** `AnalyticsPage` reads `useSearchParams`, which needs a Suspense boundary. */
export default function Analytics() {
  return (
    <Suspense fallback={<AnalyticsLoading />}>
      <AnalyticsPage />
    </Suspense>
  )
}
