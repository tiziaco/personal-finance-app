import { cn } from "@app/core/lib/utils"

/**
 * The Finsight wallet mark: body, folded flap at 45%, gold clasp with a dot.
 * Its fills read the --logo-* tokens, so it follows the theme on its own.
 */
export function FinsightMark({ className }: { className?: string }) {
  return (
    <svg
      role="img"
      aria-label="Finsight"
      viewBox="6 8 56 48"
      className={cn("h-auto shrink-0", className)}
    >
      <rect
        x="19"
        y="10"
        width="26"
        height="12"
        rx="4"
        fill="var(--logo-body)"
        fillOpacity=".45"
      />
      <rect
        x="8"
        y="17"
        width="48"
        height="36"
        rx="10"
        fill="var(--logo-body)"
      />
      <rect
        x="33"
        y="29"
        width="26"
        height="14"
        rx="7"
        fill="var(--logo-clasp)"
      />
      <circle cx="46" cy="36" r="3" fill="var(--logo-dot)" />
    </svg>
  )
}
