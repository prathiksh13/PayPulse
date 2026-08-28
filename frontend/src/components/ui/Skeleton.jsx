export function Skeleton({ width = '100%', height = 12, rounded = 6, className = '' }) {
  return (
    <span
      className={`skeleton ${className}`}
      style={{ width, height, borderRadius: rounded, display: 'inline-block' }}
    />
  );
}

export function SkeletonRows({ rows = 5, columns = 5 }) {
  return (
    <div className="skeleton-table">
      {Array.from({ length: rows }).map((_, r) => (
        <div className="skeleton-row" key={r}>
          {Array.from({ length: columns }).map((__, c) => (
            <Skeleton key={c} width={`${70 + ((r * 7 + c * 13) % 26)}%`} height={11} />
          ))}
        </div>
      ))}
    </div>
  );
}