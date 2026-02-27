'use client'

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart'
import {
  Bar,
  BarChart as RechartsBar,
  XAxis,
  YAxis,
  CartesianGrid,
} from 'recharts'
import type { ChartConfig } from '@/components/ui/chart'

export interface BarChartSeries {
  dataKey: string
  color?: string  // falls back to var(--chart-1)
  label?: string
}

interface BarChartProps {
  data: Record<string, unknown>[]
  series: BarChartSeries[]
  xAxisKey: string
  config: ChartConfig
  className?: string
  layout?: 'horizontal' | 'vertical'
}

export function BarChart({ data, series, xAxisKey, config, className, layout = 'horizontal' }: BarChartProps) {
  return (
    <ChartContainer config={config} className={className}>
      <RechartsBar data={data} layout={layout}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
        <XAxis
          dataKey={layout === 'horizontal' ? xAxisKey : undefined}
          type={layout === 'horizontal' ? 'category' : 'number'}
          className="text-xs text-muted-foreground"
        />
        <YAxis
          dataKey={layout === 'vertical' ? xAxisKey : undefined}
          type={layout === 'vertical' ? 'category' : 'number'}
          className="text-xs text-muted-foreground"
        />
        <ChartTooltip content={<ChartTooltipContent />} />
        {series.map((s, index) => (
          <Bar
            key={s.dataKey}
            dataKey={s.dataKey}
            fill={s.color ?? `var(--chart-${(index % 5) + 1})`}
            radius={[4, 4, 0, 0]}
          />
        ))}
      </RechartsBar>
    </ChartContainer>
  )
}
