export interface StatCardProps { label: string; value: string; delta?: string; /** Good/bad, not direction: 'up' = favourable (green), 'down' = unfavourable (red). */
  trend?: 'up' | 'down'; hero?: boolean; }
export declare function StatCard(props: StatCardProps): JSX.Element;