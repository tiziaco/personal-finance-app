import type { ChartConfig } from "@app/ui/chart"

/** A swatch and name per series, so a colour is never the only key. */
export function ChartLegend({ config }: { config: ChartConfig }) {
  return (
    <ul className="flex gap-4 text-xs text-muted-foreground">
      {Object.keys(config).map((key) => (
        <li key={key} className="flex items-center gap-1.5">
          <span
            aria-hidden
            className="size-2.5 rounded-sm"
            style={{ backgroundColor: config[key].color }}
          />
          {config[key].label}
        </li>
      ))}
    </ul>
  )
}
