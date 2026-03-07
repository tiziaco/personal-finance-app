'use client'

import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { Pie, PieChart as RechartsPie, Cell, Legend } from 'recharts'
import type { ChartConfig } from '@/components/ui/chart'

export interface PieChartDatum {
  label: string
  value: number
  color?: string  // optional override; falls back to var(--chart-N)
}

interface PieChartProps {
  data: PieChartDatum[]
  config: ChartConfig
  className?: string
  showLegend?: boolean
}

export function PieChart({ data, config, className, showLegend = true }: PieChartProps) {
  return (
    <ChartContainer config={config} className={className}>
      <RechartsPie>
        <Pie data={data} dataKey="value" nameKey="label" cx="50%" cy="50%" outerRadius={80}>
          {data.map((entry, index) => (
            <Cell
              key={entry.label}
              fill={entry.color ?? `var(--chart-${(index % 5) + 1})`}
            />
          ))}
        </Pie>
        <ChartTooltip content={<ChartTooltipContent />} />
        {showLegend && <Legend />}
      </RechartsPie>
    </ChartContainer>
  )
}
