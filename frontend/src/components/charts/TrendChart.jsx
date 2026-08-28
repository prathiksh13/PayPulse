import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from 'recharts';
import { ChartCard } from './ChartCard';
import { fmtINR } from '../../utils/format';

const TOOLTIP_STYLE = {
  background: '#ffffff',
  border: '1px solid #e7eaf0',
  borderRadius: 10,
  fontSize: 11,
  boxShadow: '0 8px 24px rgba(32,37,50,.08)',
};

export function TrendChart({
  title, subtitle, loading, unavailable, networkError, errorText, onRetry,
  data = [], xKey = 'time', series = [], height = 220, formatValue,
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
        <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            {series.map((s) => (
              <linearGradient key={s.key} id={`fill-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={s.color} stopOpacity={0.16} />
                <stop offset="100%" stopColor={s.color} stopOpacity={0} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid vertical={false} stroke="#edf0f4" />
          <XAxis dataKey={xKey} axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#8a92a3' }} />
          <YAxis
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 10, fill: '#8a92a3' }}
            width={46}
            tickFormatter={(v) => (formatValue ? formatValue(v) : String(v))}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            formatter={(value, name) => (formatValue ? [formatValue(value), name] : [value, name])}
          />
          {series.length > 1 ? <Legend wrapperStyle={{ fontSize: 10 }} /> : null}
          {series.map((s) => (
            <Area
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.name}
              stroke={s.color}
              strokeWidth={2.2}
              fill={`url(#fill-${s.key})`}
              dot={false}
              activeDot={{ r: 4 }}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}