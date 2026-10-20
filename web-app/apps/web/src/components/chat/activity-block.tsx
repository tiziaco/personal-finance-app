"use client"

import { useEffect, useState } from "react"
import type {
  SummaryItem,
  TableColumn,
  ToolDisplay,
} from "@app/api-client/types"
import { cn } from "@app/core/lib/utils"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@app/ui/collapsible"
import { ChevronRightIcon, Loader2Icon } from "lucide-react"

import {
  currentLabel,
  type ActivityPart,
  type ActivityState,
} from "@/lib/chat/activity"
import {
  amountSign,
  formatAmount,
  formatDate,
  formatSignedAmount,
} from "@/components/transactions/format"

import { CHAT_COPY } from "./copy"

type ToolPart = Extract<ActivityPart, { kind: "tool" }>
type Cell = string | number | null | undefined

/** A money figure: a plain total, or a signed amount when it is negative. */
const money = (value: string | number) => {
  const text = String(value)
  return amountSign(text) < 0 ? formatSignedAmount(text) : formatAmount(text)
}

const percent = (value: string | number) =>
  `${Number(Number(value).toFixed(1))}%`

function formatSummaryItem(item: SummaryItem): string {
  switch (item.kind) {
    case "money":
      return money(item.value)
    case "percent":
      return percent(item.value)
    case "count":
      return item.label ? `${item.value} ${item.label}` : String(item.value)
    case "text":
      return String(item.value)
  }
}

export const formatSummary = (items: SummaryItem[]) =>
  items.map(formatSummaryItem).join(" · ")

function formatCell(column: TableColumn, value: Cell): string {
  if (value === null || value === undefined || value === "") return "–"
  switch (column.kind) {
    case "money":
      return money(value)
    case "percent":
      return percent(value)
    case "date":
      return formatDate(String(value)) || String(value)
    default:
      return String(value)
  }
}

const clock = (ms: number) => {
  const total = Math.max(0, Math.floor(ms / 1000))
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`
}

/** The wall clock, ticking once a second while `active`. */
function useNow(active: boolean) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!active) return
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [active])
  return now
}

function ResultTable({ table }: { table: NonNullable<ToolDisplay["table"]> }) {
  return (
    <table className="mt-2 w-full border-collapse text-xs">
      <thead className="sr-only">
        <tr>
          {table.columns.map((column) => (
            <th key={column.key}>{column.label}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {table.rows.map((row, i) => (
          <tr key={i} className="border-t border-border/60">
            {table.columns.map((column) => (
              <td
                key={column.key}
                className={cn(
                  "py-0.5 pr-2 last:pr-0",
                  column.kind !== "text" &&
                    column.kind !== "date" &&
                    "text-right tabular-nums",
                )}
              >
                {formatCell(column, row[column.key])}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function ToolRow({ part }: { part: ToolPart }) {
  const [open, setOpen] = useState(false)
  const { display } = part
  const failed = part.status === "error"
  const period = display?.period
  const hasTable = part.status === "ok" && !!display?.table
  const summary =
    part.status === "ok" && display ? formatSummary(display.summary) : ""

  return (
    <Collapsible
      open={hasTable && open}
      onOpenChange={setOpen}
      className={cn(
        "rounded-lg border border-border px-2.5 py-1.5",
        failed && "text-muted-foreground",
      )}
    >
      <CollapsibleTrigger
        disabled={!hasTable}
        className="flex w-full items-center justify-between gap-2 text-left disabled:cursor-default"
      >
        <span className="min-w-0">
          <span className="mr-1.5 rounded bg-primary/10 px-1.5 py-px text-[10.5px] tracking-wide text-primary uppercase">
            {CHAT_COPY.toolTag}
          </span>
          <span className={cn("font-semibold", failed && "line-through")}>
            {part.title}
          </span>
          {period && <span className="text-muted-foreground"> · {period}</span>}
        </span>
        <span className="flex shrink-0 items-center gap-1 text-muted-foreground">
          {part.status === "running" && (
            <Loader2Icon className="size-3 animate-spin" aria-hidden />
          )}
          {failed && CHAT_COPY.lookupFailed}
          {summary}
          {hasTable && (
            <ChevronRightIcon
              className={cn("size-3 transition-transform", open && "rotate-90")}
              aria-hidden
            />
          )}
        </span>
      </CollapsibleTrigger>
      <CollapsibleContent>
        {display?.table && <ResultTable table={display.table} />}
      </CollapsibleContent>
    </Collapsible>
  )
}

/**
 * What the assistant did on the way to a reply: its thinking and each lookup.
 * Open and timed while it works, one line once the answer starts, and the
 * same line (minus timing) when reopened from history.
 */
export function ActivityBlock({ activity }: { activity: ActivityState }) {
  const { parts, startedAt, endedAt, stopped, answerStarted } = activity
  const working = endedAt === null && !answerStarted
  const now = useNow(working)

  // The moment the answer began (the last tick), for a reply still streaming
  // with no `done` yet. Set during render, from state, as React advises.
  const [answerAt, setAnswerAt] = useState<number | null>(null)
  if (answerStarted && answerAt === null) setAnswerAt(now)

  // Open while working, collapsed after; the user's toggle holds until the
  // block next changes between the two.
  const [manual, setManual] = useState<{
    working: boolean
    open: boolean
  } | null>(null)
  const open = manual && manual.working === working ? manual.open : working

  if (parts.length === 0) return null

  const lookups = parts.filter((part) => part.kind === "tool").length
  const seconds =
    startedAt === null
      ? null
      : Math.max(
          0,
          Math.round(((endedAt ?? answerAt ?? now) - startedAt) / 1000),
        )

  let label: string
  if (working) {
    const live = currentLabel(activity)
    label = live === "Thinking…" ? CHAT_COPY.thinking : live
  } else if (stopped) {
    label =
      seconds === null
        ? CHAT_COPY.stoppedLookups(lookups)
        : CHAT_COPY.stoppedAfter(seconds)
  } else {
    label =
      seconds === null
        ? CHAT_COPY.lookups(lookups)
        : CHAT_COPY.workedFor(seconds, lookups)
  }

  return (
    <Collapsible
      open={open}
      onOpenChange={(next) => setManual({ working, open: next })}
      className="mb-2 text-[12.5px]"
    >
      <CollapsibleTrigger className="flex items-center gap-1.5 text-muted-foreground">
        <ChevronRightIcon
          className={cn("size-3.5 transition-transform", open && "rotate-90")}
          aria-hidden
        />
        <span
          aria-live="polite"
          className={cn(
            working &&
              "animate-[activity-shimmer_1.6s_linear_infinite] bg-[linear-gradient(90deg,var(--muted-foreground)_0%,var(--foreground)_50%,var(--muted-foreground)_100%)] bg-[length:200%_100%] bg-clip-text font-medium text-transparent motion-reduce:animate-none",
          )}
        >
          {label}
        </span>
        {working && startedAt !== null && (
          <span className="tabular-nums opacity-70">
            {clock(now - startedAt)}
          </span>
        )}
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="mt-1.5 ml-1.5 flex flex-col gap-1.5 border-l-2 border-border pl-2.5">
          {parts.map((part, i) =>
            part.kind === "reasoning" ? (
              <p key={i} className="text-muted-foreground italic">
                {part.text}
              </p>
            ) : (
              <ToolRow key={part.id} part={part} />
            ),
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}
