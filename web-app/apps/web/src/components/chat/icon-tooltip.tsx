"use client"

import { Tooltip, TooltipContent, TooltipTrigger } from "@app/ui/tooltip"
import type { ReactElement } from "react"

/**
 * Names an icon-only button on hover and focus. The child is the trigger
 * itself (Base UI's render prop), so an assistant-ui `asChild` primitive or a
 * menu trigger keeps its own behaviour underneath.
 */
export function IconTooltip({
  label,
  children,
}: {
  label: string
  children: ReactElement
}) {
  return (
    <Tooltip>
      <TooltipTrigger render={children} />
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}
