import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell } from 'recharts';
import { ChartCard } from './ChartCard';

const TOOLTIP_STYLE = {
  background: '#ffffff',
  border: '1px solid #e7eaf0',
  borderRadius: 10,
  fontSize: 11,
  boxShadow: '0 8px 24px rgba(32,37,50,.08)',
};

export function BarChartView({
  title, subtitle, loading, unavailable, networkError, errorText, onRetry,
  data = [], xKey = 'name', barKey = 'value', layout = 'vertical',
  color = '#6366f1', formatValue, percent = false, height = 220,
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
        <BarChart data={data} layout={layout} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid vertical={layout === 'horizontal'} horizontal={layout === 'vertical'} stroke="#edf0f4" />
          {layout === 'vertical' ? (
            <>
              <XAxis type="number" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#8a92a3' }} tickFormatter={(v) => (percent ? `${v}%` : String(v))} />
              <YAxis type="category" dataKey={xKey} axisLine={false} tickLine={false} width={130} tick={{ fontSize: 10, fill: '#687184' }} />
            </>
          ) : (
            <>
              <XAxis dataKey={xKey} axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#8a92a3' }} />
              <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#8a92a3' }} tickFormatter={(v) => (percent ? `${v}%` : String(v))} width={40} />
            </>
          )}
          <Tooltip
            cursor={{ fill: 'rgba(79,70,229,.05)' }}
            contentStyle={TOOLTIP_STYLE}
            formatter={(value) => (formatValue ? [formatValue(value), barKey] : percent ? [`${value}%`, barKey] : [value, barKey])}
          />
          <Bar dataKey={barKey} radius={layout === 'vertical' ? [0, 5, 5, 0] : [5, 5, 0, 0]} barSize={18} fill={color}>
            {data.map((d, i) =>
              (d.color ? <Cell key={i} fill={d.color} /> : null),
            )}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}