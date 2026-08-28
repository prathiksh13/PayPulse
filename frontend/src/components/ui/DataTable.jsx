import { useMemo, useState } from 'react';
import { ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';
import { SkeletonRows } from './Skeleton';
import { WaitingState, EmptyState } from './EmptyState';

function getCell(col, row) {
  if (col.render) return col.render(row);
  return row?.[col.key];
}

function sortValueOf(col, row) {
  if (col.sortValue) return col.sortValue(row);
  return row?.[col.key];
}

export function DataTable({
  columns,
  rows = [],
  rowKey = 'id',
  onRowClick,
  defaultSort,
  emptyTitle = 'No data available',
  emptyDescription,
  waiting = false,
  loading = false,
  minWidth = 720,
  className = '',
}) {
  const [sort, setSort] = useState(defaultSort || { key: columns[0]?.key, dir: 'asc' });

  const sorted = useMemo(() => {
    if (!sort || !sort.key) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col) return rows;
    return [...rows].sort((a, b) => {
      const av = sortValueOf(col, a);
      const bv = sortValueOf(col, b);
      if (typeof av === 'number' && typeof bv === 'number') return sort.dir === 'asc' ? av - bv : bv - av;
      const sa = String(av ?? '').toLowerCase();
      const sb = String(bv ?? '').toLowerCase();
      return sort.dir === 'asc' ? sa.localeCompare(sb) : sb.localeCompare(sa);
    });
  }, [rows, sort, columns]);

  const toggleSort = (col) => {
    if (!col.sortable) return;
    setSort((s) => {
      if (s.key === col.key) return { key: col.key, dir: s.dir === 'asc' ? 'desc' : 'asc' };
      return { key: col.key, dir: 'asc' };
    });
  };

  const SortIcon = ({ col }) => {
    if (!col.sortable) return null;
    if (sort.key === col.key) {
      return sort.dir === 'asc' ? <ArrowUp size={12} /> : <ArrowDown size={12} />;
    }
    return <ArrowUpDown size={12} className="sort-idle" />;
  };

  return (
    <div className={`table-wrap ${className}`}>
      <div className="table-scroll" style={{ ['--table-minw']: `${minWidth}px` }}>
        <table className="data-table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={col.align === 'right' ? 'ta-right' : ''}
                  onClick={() => col.sortable && toggleSort(col)}
                  style={{ cursor: col.sortable ? 'pointer' : 'default' }}
                >
                  <span className="th-inner">
                    {col.label}
                    {col.sortable ? <SortIcon col={col} /> : null}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={columns.length}>
                  <SkeletonRows rows={5} columns={columns.length} />
                </td>
              </tr>
            ) : (
              sorted.map((row) => (
                <tr
                  key={row?.[rowKey] ?? JSON.stringify(row)}
                  className={onRowClick ? 'clickable' : ''}
                  onClick={() => onRowClick?.(row)}
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={[col.className, col.align === 'right' ? 'ta-right' : ''].filter(Boolean).join(' ')}
                    >
                      {getCell(col, row)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {!loading && !waiting && sorted.length === 0 ? (
        <EmptyState title={emptyTitle} description={emptyDescription} />
      ) : null}
      {!loading && waiting ? (
        <WaitingState title="Waiting for payment events" description="This list populates as the backend streams payment events into the API." />
      ) : null}
    </div>
  );
}