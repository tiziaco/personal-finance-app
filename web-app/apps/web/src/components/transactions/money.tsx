import type { ComponentProps } from "react"
import { cn } from "@app/core/lib/utils"

import { amountClass, formatMoney, type AmountKind } from "./format"

/** An amount on screen, signed and coloured by what it is (see AmountKind). */
export function Money({
  amount,
  kind,
  className,
  ...props
}: { amount: string; kind: AmountKind } & Omit<
  ComponentProps<"span">,
  "children"
>) {
  return (
    <span
      className={cn("tabular-nums", amountClass(amount, kind), className)}
      {...props}
    >
      {formatMoney(amount, kind)}
    </span>
  )
}
