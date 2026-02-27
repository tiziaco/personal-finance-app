'use client'

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart'
import {
  Line,
  LineChart as RechartsLine,
  XAxis,
  YAxis,
  CartesianGrid,
} from 'recharts'
import type { ChartConfig } from '@/components/ui/chart'

export interface LineChartSeries {
  dataKey: string
  color?: string  // falls back to var(--chart-1)
  label?: string
}

interface LineChartProps {
  data: Record<string, unknown>[]
  series: LineChartSeries[]
  xAxisKey: string
  config: ChartConfig
  className?: string
}

export function LineChart({ data, series, xAxisKey, config, className }: LineChartProps) {
  return (
    <ChartContainer config={config} className={className}>
      <RechartsLine data={data}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
        <XAxis dataKey={xAxisKey} className="text-xs text-muted-foreground" />
        <YAxis className="text-xs text-muted-foreground" />
        <ChartTooltip content={<ChartTooltipContent />} />
        {series.map((s, index) => (
          <Line
            key={s.dataKey}
            type="monotone"
            dataKey={s.dataKey}
            stroke={s.color ?? `var(--chart-${(index % 5) + 1})`}
            strokeWidth={2}
            dot={false}
          />
        ))}
      </RechartsLine>
    </ChartContainer>
  )
}
