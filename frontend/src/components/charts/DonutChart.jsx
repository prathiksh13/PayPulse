import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import { ChartCard } from './ChartCard';

const TOOLTIP_STYLE = {
  background: '#ffffff',
  border: '1px solid #e7eaf0',
  borderRadius: 10,
  fontSize: 11,
  boxShadow: '0 8px 24px rgba(32,37,50,.08)',
};

const PALETTE = ['#6366f1', '#8b5cf6', '#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#64748b', '#a78bfa'];

export function DonutChart({
  title, subtitle, loading, unavailable, networkError, errorText, onRetry,
  data = [], nameKey = 'name', valueKey = 'value', height = 220, innerRadius = 55, outerRadius = 78,
}) {
  return (
    <ChartCard
      title={title}
      subtitle={subtitle}
      loading={loading}
      unavailable={unavailable}
      networkError={networkError}
      errorText={errorText}
      onRetry={onRetry}
      hasData={data.length > 0}
      height={height}
    >
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey={valueKey}
            nameKey={nameKey}
            innerRadius={innerRadius}
            outerRadius={outerRadius}
            paddingAngle={2}
            strokeWidth={0}
          >
            {data.map((_, i) => (
              <Cell key={i} fill={data[i]?.color || PALETTE[i % PALETTE.length]} />
            ))}
          </Pie>
          <Tooltip contentStyle={TOOLTIP_STYLE} />
          <Legend wrapperStyle={{ fontSize: 10 }} iconType="circle" iconSize={7} />
        </PieChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}