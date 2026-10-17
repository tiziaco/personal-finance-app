"use client"

import { useMemo } from "react"
import type { InsightResponse } from "@app/api-client/types"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@app/ui/tabs"
import { InsightCard } from "./insight-card"
import { SECTION_LABEL, SECTIONS } from "./labels"
import { sortBySeverity } from "./severity"

/** "All" first, sorted by severity, then one tab per section with its count. */
export function InsightTabs({
  insights,
  referenceMonth,
  monthToDateThrough,
}: {
  insights: InsightResponse[]
  referenceMonth: string | null | undefined
  monthToDateThrough: string | null | undefined
}) {
  const sorted = useMemo(() => sortBySeverity(insights), [insights])
  const bySection = useMemo(() => {
    const groups = Object.fromEntries(
      SECTIONS.map((section) => [section, [] as InsightResponse[]]),
    ) as Record<InsightResponse["section"], InsightResponse[]>
    for (const insight of sorted) groups[insight.section].push(insight)
    return groups
  }, [sorted])
  const cards = (list: InsightResponse[], showSection: boolean) => (
    <div className="space-y-3">
      {list.map((insight, i) => (
        <InsightCard
          key={i}
          insight={insight}
          showSection={showSection}
          referenceMonth={referenceMonth}
          monthToDateThrough={monthToDateThrough}
        />
      ))}
    </div>
  )

  return (
    <Tabs defaultValue="all">
      <TabsList className="h-auto flex-wrap">
        <TabsTrigger value="all">
          All <span className="text-muted-foreground">{sorted.length}</span>
        </TabsTrigger>
        {SECTIONS.map((section) => (
          <TabsTrigger key={section} value={section}>
            {SECTION_LABEL[section]}{" "}
            <span className="text-muted-foreground">
              {bySection[section].length}
            </span>
          </TabsTrigger>
        ))}
      </TabsList>
      <TabsContent value="all">{cards(sorted, true)}</TabsContent>
      {SECTIONS.map((section) => {
        const inSection = bySection[section]
        return (
          <TabsContent key={section} value={section}>
            {inSection.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {`No ${SECTION_LABEL[section]} insights this time.`}
              </p>
            ) : (
              cards(inSection, false)
            )}
          </TabsContent>
        )
      })}
    </Tabs>
  )
}
