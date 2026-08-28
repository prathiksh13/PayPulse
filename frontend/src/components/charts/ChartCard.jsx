import { ErrorState } from '../ui/ErrorState';
import { WaitingState } from '../ui/EmptyState';
import { Skeleton } from '../ui/Skeleton';

export function ChartCard({
  title,
  subtitle,
  actions,
  loading = false,
  unavailable = false,
  waiting = false,
  networkError = false,
  errorText,
  onRetry,
  data,
  hasData,
  emptyMessage = 'No data available',
  children,
  height = 220,
  className = '',
}) {
  const showsEmpty = !loading && !networkError && !unavailable && !hasData;

  return (
    <div className="panel pad chart-card">
      <div className="panel-head">
        <div className="panel-title">
          <h2>{title}</h2>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
        {actions ? <div className="panel-actions">{actions}</div> : null}
      </div>
      <div className="chart-body" style={{ height }}>
        {loading ? (
          <div className="chart-skeleton">
            <Skeleton height={180} />
          </div>
        ) : networkError ? (
          <ErrorState error={errorText} onRetry={onRetry} />
        ) : unavailable ? (
          <WaitingState description={`This chart renders once the ${title.toLowerCase()} data source is wired to the API.`} />
        ) : !hasData && !data ? (
          <WaitingState />
        ) : (
          children
        )}
      </div>
    </div>
  );
}